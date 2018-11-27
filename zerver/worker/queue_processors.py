# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
from typing import Any, Callable, Dict, List, Mapping, Optional, cast, TypeVar, Type

import copy
import signal
from functools import wraps
from threading import Timer

import smtplib
import socket

from django.conf import settings
from django.db import connection
from django.core.handlers.wsgi import WSGIRequest
from django.core.handlers.base import BaseHandler
from zerver.models import \
    get_client, get_system_bot, ScheduledEmail, PreregistrationUser, \
    get_user_profile_by_id, Message, Realm, Service, UserMessage, UserProfile, \
    Client
from zerver.lib.context_managers import lockfile
from zerver.lib.error_notify import do_report_error
from zerver.lib.feedback import handle_feedback
from zerver.lib.queue import SimpleQueueClient, queue_json_publish, retry_event
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.notifications import handle_missedmessage_emails
from zerver.lib.push_notifications import handle_push_notification, handle_remove_push_notification
from zerver.lib.actions import do_send_confirmation_email, \
    do_update_user_activity, do_update_user_activity_interval, do_update_user_presence, \
    internal_send_message, check_send_message, extract_recipients, \
    render_incoming_message, do_update_embedded_data, do_mark_stream_messages_as_read
from zerver.lib.url_preview import preview as url_preview
from zerver.lib.digest import handle_digest_email
from zerver.lib.send_email import send_future_email, send_email_from_dict, \
    FromAddress, EmailNotDeliveredException
from zerver.lib.email_mirror import process_message as mirror_email
from zerver.lib.streams import access_stream_by_id
from zerver.decorator import JsonableError
from zerver.tornado.socket import req_redis_key, respond_send_message
from confirmation.models import Confirmation, create_confirmation_link
from zerver.lib.db import reset_queries
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.str_utils import force_str
from zerver.context_processors import common_context
from zerver.lib.outgoing_webhook import do_rest_call, get_outgoing_webhook_service_handler
from zerver.models import get_bot_services
from zulip_bots.lib import extract_query_without_mention
from zerver.lib.bot_lib import EmbeddedBotHandler, get_bot_handler, EmbeddedBotQuitException

import os
import sys
import ujson
from collections import defaultdict
import email
import time
import datetime
import logging
import requests
from io import StringIO
import re
import importlib

logger = logging.getLogger(__name__)

class WorkerDeclarationException(Exception):
    pass

ConcreteQueueWorker = TypeVar('ConcreteQueueWorker', bound='QueueProcessingWorker')

def assign_queue(
        queue_name: str, enabled: bool=True, queue_type: str="consumer"
) -> Callable[[Type[ConcreteQueueWorker]], Type[ConcreteQueueWorker]]:
    def decorate(clazz: Type[ConcreteQueueWorker]) -> Type[ConcreteQueueWorker]:
        clazz.queue_name = queue_name
        if enabled:
            register_worker(queue_name, clazz, queue_type)
        return clazz
    return decorate

worker_classes = {}  # type: Dict[str, Type[QueueProcessingWorker]]
queues = {}  # type: Dict[str, Dict[str, Type[QueueProcessingWorker]]]
def register_worker(queue_name: str, clazz: Type['QueueProcessingWorker'], queue_type: str) -> None:
    if queue_type not in queues:
        queues[queue_type] = {}
    queues[queue_type][queue_name] = clazz
    worker_classes[queue_name] = clazz

def get_worker(queue_name: str) -> 'QueueProcessingWorker':
    return worker_classes[queue_name]()

def get_active_worker_queues(queue_type: Optional[str]=None) -> List[str]:
    """Returns all the non-test worker queues."""
    if queue_type is None:
        return list(worker_classes.keys())
    return list(queues[queue_type].keys())

def check_and_send_restart_signal() -> None:
    try:
        if not connection.is_usable():
            logging.warning("*** Sending self SIGUSR1 to trigger a restart.")
            os.kill(os.getpid(), signal.SIGUSR1)
    except Exception:
        pass

def retry_send_email_failures(
        func: Callable[[ConcreteQueueWorker, Dict[str, Any]], None]
) -> Callable[['QueueProcessingWorker', Dict[str, Any]], None]:

    @wraps(func)
    def wrapper(worker: ConcreteQueueWorker, data: Dict[str, Any]) -> None:
        try:
            func(worker, data)
        except (smtplib.SMTPServerDisconnected, socket.gaierror, EmailNotDeliveredException):
            def on_failure(event: Dict[str, Any]) -> None:
                logging.exception("Event {} failed".format(event))

            retry_event(worker.queue_name, data, on_failure)

    return wrapper

class QueueProcessingWorker:
    queue_name = None  # type: str

    def __init__(self) -> None:
        self.q = None  # type: SimpleQueueClient
        if self.queue_name is None:
            raise WorkerDeclarationException("Queue worker declared without queue_name")

    def consume(self, data: Dict[str, Any]) -> None:
        raise WorkerDeclarationException("No consumer defined!")

    def consume_wrapper(self, data: Dict[str, Any]) -> None:
        try:
            self.consume(data)
        except Exception:
            self._log_problem()
            if not os.path.exists(settings.QUEUE_ERROR_DIR):
                os.mkdir(settings.QUEUE_ERROR_DIR)  # nocoverage
            fname = '%s.errors' % (self.queue_name,)
            fn = os.path.join(settings.QUEUE_ERROR_DIR, fname)
            line = '%s\t%s\n' % (time.asctime(), ujson.dumps(data))
            lock_fn = fn + '.lock'
            with lockfile(lock_fn):
                with open(fn, 'ab') as f:
                    f.write(line.encode('utf-8'))
            check_and_send_restart_signal()
        finally:
            reset_queries()

    def _log_problem(self) -> None:
        logging.exception("Problem handling data on queue %s" % (self.queue_name,))

    def setup(self) -> None:
        self.q = SimpleQueueClient()

    def start(self) -> None:
        self.q.register_json_consumer(self.queue_name, self.consume_wrapper)
        self.q.start_consuming()

    def stop(self) -> None:  # nocoverage
        self.q.stop_consuming()

class LoopQueueProcessingWorker(QueueProcessingWorker):
    sleep_delay = 0

    def start(self) -> None:  # nocoverage
        while True:
            # TODO: Probably it'd be better to share code with consume_wrapper()
            events = self.q.drain_queue(self.queue_name, json=True)
            try:
                self.consume_batch(events)
            finally:
                reset_queries()
            time.sleep(self.sleep_delay)

    def consume_batch(self, event: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def consume(self, event: Dict[str, Any]) -> None:
        """In LoopQueueProcessingWorker, consume is used just for automated tests"""
        self.consume_batch([event])

@assign_queue('signups')
class SignupWorker(QueueProcessingWorker):
    def consume(self, data: Dict[str, Any]) -> None:
        # TODO: This is the only implementation with Dict cf Mapping; should we simplify?
        user_profile = get_user_profile_by_id(data['user_id'])
        logging.info("Processing signup for user %s in realm %s" % (
            user_profile.email, user_profile.realm.string_id))
        if settings.MAILCHIMP_API_KEY and settings.PRODUCTION:
            endpoint = "https://%s.api.mailchimp.com/3.0/lists/%s/members" % \
                       (settings.MAILCHIMP_API_KEY.split('-')[1], settings.ZULIP_FRIENDS_LIST_ID)
            params = dict(data)
            del params['user_id']
            params['list_id'] = settings.ZULIP_FRIENDS_LIST_ID
            params['status'] = 'subscribed'
            r = requests.post(endpoint, auth=('apikey', settings.MAILCHIMP_API_KEY), json=params, timeout=10)
            if r.status_code == 400 and ujson.loads(r.text)['title'] == 'Member Exists':
                logging.warning("Attempted to sign up already existing email to list: %s" %
                                (data['email_address'],))
            elif r.status_code == 400:
                retry_event('signups', data, lambda e: r.raise_for_status())
            else:
                r.raise_for_status()

@assign_queue('invites')
class ConfirmationEmailWorker(QueueProcessingWorker):
    def consume(self, data: Mapping[str, Any]) -> None:
        if "email" in data:
            # When upgrading from a version up through 1.7.1, there may be
            # existing items in the queue with `email` instead of `prereg_id`.
            invitee = PreregistrationUser.objects.filter(
                email__iexact=data["email"].strip()).latest("invited_at")
        else:
            invitee = PreregistrationUser.objects.filter(id=data["prereg_id"]).first()
            if invitee is None:
                # The invitation could have been revoked
                return

        referrer = get_user_profile_by_id(data["referrer_id"])
        logger.info("Sending invitation for realm %s to %s" % (referrer.realm.string_id, invitee.email))
        do_send_confirmation_email(invitee, referrer)

        # queue invitation reminder for two days from now.
        link = create_confirmation_link(invitee, referrer.realm.host, Confirmation.INVITATION)
        context = common_context(referrer)
        context.update({
            'activate_url': link,
            'referrer_name': referrer.full_name,
            'referrer_email': referrer.email,
            'referrer_realm_name': referrer.realm.name,
        })
        send_future_email(
            "zerver/emails/invitation_reminder",
            referrer.realm,
            to_email=invitee.email,
            from_address=FromAddress.tokenized_no_reply_address(),
            context=context,
            delay=datetime.timedelta(days=2))

@assign_queue('user_activity')
class UserActivityWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        query = event["query"]
        do_update_user_activity(user_profile, client, query, log_time)

@assign_queue('user_activity_interval')
class UserActivityIntervalWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        log_time = timestamp_to_datetime(event["time"])
        do_update_user_activity_interval(user_profile, log_time)

@assign_queue('user_presence')
class UserPresenceWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.debug("Received presence event: %s" % (event),)
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        status = event["status"]
        do_update_user_presence(user_profile, client, log_time, status)

@assign_queue('missedmessage_emails', queue_type="loop")
class MissedMessageWorker(QueueProcessingWorker):
    # Aggregate all messages received over the last BATCH_DURATION
    # seconds to let someone finish sending a batch of messages and/or
    # editing them before they are sent out as emails to recipients.
    #
    # The timer is running whenever; we poll at most every TIMER_FREQUENCY
    # seconds, to avoid excessive activity.
    #
    # TODO: Since this process keeps events in memory for up to 2
    # minutes, it now will lose approximately BATCH_DURATION worth of
    # missed_message emails whenever it is restarted as part of a
    # server restart.  We should probably add some sort of save/reload
    # mechanism for that case.
    TIMER_FREQUENCY = 5
    BATCH_DURATION = 120
    timer_event = None  # type: Optional[Timer]
    events_by_recipient = defaultdict(list)  # type: Dict[int, List[Dict[str, Any]]]
    batch_start_by_recipient = {}  # type: Dict[int, float]

    def consume(self, event: Dict[str, Any]) -> None:
        logging.debug("Received missedmessage_emails event: %s" % (event,))

        # When we process an event, just put it into the queue and ensure we have a timer going.
        user_profile_id = event['user_profile_id']
        if user_profile_id not in self.batch_start_by_recipient:
            self.batch_start_by_recipient[user_profile_id] = time.time()
        self.events_by_recipient[user_profile_id].append(event)

        self.ensure_timer()

    def ensure_timer(self) -> None:
        if self.timer_event is not None:
            return
        self.timer_event = Timer(self.TIMER_FREQUENCY, MissedMessageWorker.maybe_send_batched_emails, [self])
        self.timer_event.start()

    def stop_timer(self) -> None:
        if self.timer_event and self.timer_event.is_alive():  # type: ignore # Report mypy bug.
            self.timer_event.cancel()
            self.timer_event = None

    def maybe_send_batched_emails(self) -> None:
        self.stop_timer()

        current_time = time.time()
        for user_profile_id, timestamp in list(self.batch_start_by_recipient.items()):
            if current_time - timestamp < self.BATCH_DURATION:
                continue
            events = self.events_by_recipient[user_profile_id]
            logging.info("Batch-processing %s missedmessage_emails events for user %s" %
                         (len(events), user_profile_id))
            handle_missedmessage_emails(user_profile_id, events)
            del self.events_by_recipient[user_profile_id]
            del self.batch_start_by_recipient[user_profile_id]

        # By only restarting the timer if there are actually events in
        # the queue, we ensure this queue processor is idle when there
        # are no missed-message emails to process.
        if len(self.batch_start_by_recipient) > 0:
            self.ensure_timer()

@assign_queue('email_senders')
class EmailSendingWorker(QueueProcessingWorker):
    @retry_send_email_failures
    def consume(self, event: Dict[str, Any]) -> None:
        # Copy the event, so that we don't pass the `failed_tries'
        # data to send_email_from_dict (which neither takes that
        # argument nor needs that data).
        copied_event = copy.deepcopy(event)
        if 'failed_tries' in copied_event:
            del copied_event['failed_tries']
        send_email_from_dict(copied_event)

@assign_queue('missedmessage_email_senders')
class MissedMessageSendingWorker(EmailSendingWorker):  # nocoverage
    """
    Note: Class decorators are not inherited.

    The `missedmessage_email_senders` queue was used up through 1.7.1, so we
    keep consuming from it in case we've just upgraded from an old version.
    After the 1.8 release, we can delete it and tell admins to upgrade to 1.8
    first.
    """
    # TODO: zulip-1.8: Delete code related to missedmessage_email_senders queue.
    pass

@assign_queue('missedmessage_mobile_notifications')
class PushNotificationsWorker(QueueProcessingWorker):  # nocoverage
    def consume(self, data: Mapping[str, Any]) -> None:
        if data.get("type", "add") == "remove":
            handle_remove_push_notification(data['user_profile_id'], data['message_id'])
        else:
            handle_push_notification(data['user_profile_id'], data)

# We probably could stop running this queue worker at all if ENABLE_FEEDBACK is False
@assign_queue('feedback_messages')
class FeedbackBot(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.info("Received feedback from %s" % (event["sender_email"],))
        handle_feedback(event)

@assign_queue('error_reports')
class ErrorReporter(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.info("Processing traceback with type %s for %s" % (event['type'], event.get('user_email')))
        if settings.ERROR_REPORTING:
            do_report_error(event['report']['host'], event['type'], event['report'])

@assign_queue('slow_queries', queue_type="loop")
class SlowQueryWorker(LoopQueueProcessingWorker):
    # Sleep 1 minute between checking the queue
    sleep_delay = 60 * 1

    # TODO: The type annotation here should be List[str], but that
    # creates conflicts with other users in the file.
    def consume_batch(self, slow_queries: List[Any]) -> None:
        for query in slow_queries:
            logging.info("Slow query: %s" % (query))

        if settings.SLOW_QUERY_LOGS_STREAM is None:
            return

        if settings.ERROR_BOT is None:
            return

        if len(slow_queries) > 0:
            topic = "%s: slow queries" % (settings.EXTERNAL_HOST,)

            content = ""
            for query in slow_queries:
                content += "    %s\n" % (query,)

            error_bot_realm = get_system_bot(settings.ERROR_BOT).realm
            internal_send_message(error_bot_realm, settings.ERROR_BOT,
                                  "stream", settings.SLOW_QUERY_LOGS_STREAM, topic, content)

@assign_queue("message_sender")
class MessageSenderWorker(QueueProcessingWorker):
    def __init__(self) -> None:
        super().__init__()
        self.redis_client = get_redis_client()
        self.handler = BaseHandler()
        self.handler.load_middleware()

    def consume(self, event: Mapping[str, Any]) -> None:
        server_meta = event['server_meta']

        environ = {
            'REQUEST_METHOD': 'SOCKET',
            'SCRIPT_NAME': '',
            'PATH_INFO': '/json/messages',
            'SERVER_NAME': '127.0.0.1',
            'SERVER_PORT': 9993,
            'SERVER_PROTOCOL': 'ZULIP_SOCKET/1.0',
            'wsgi.version': (1, 0),
            'wsgi.input': StringIO(),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
            'zulip.emulated_method': 'POST'
        }

        if 'socket_user_agent' in event['request']:
            environ['HTTP_USER_AGENT'] = event['request']['socket_user_agent']
            del event['request']['socket_user_agent']

        # We're mostly using a WSGIRequest for convenience
        environ.update(server_meta['request_environ'])
        request = WSGIRequest(environ)
        # Note: If we ever support non-POST methods, we'll need to change this.
        request._post = event['request']
        request.csrf_processing_done = True

        user_profile = get_user_profile_by_id(server_meta['user_id'])
        request._cached_user = user_profile

        resp = self.handler.get_response(request)
        server_meta['time_request_finished'] = time.time()
        server_meta['worker_log_data'] = request._log_data

        resp_content = resp.content.decode('utf-8')
        response_data = ujson.loads(resp_content)
        if response_data['result'] == 'error':
            check_and_send_restart_signal()

        result = {'response': response_data, 'req_id': event['req_id'],
                  'server_meta': server_meta}

        redis_key = req_redis_key(event['req_id'])
        self.redis_client.hmset(redis_key, {'status': 'complete',
                                            'response': resp_content})

        queue_json_publish(server_meta['return_queue'], result,
                           respond_send_message)

@assign_queue('digest_emails')
class DigestWorker(QueueProcessingWorker):  # nocoverage
    # Who gets a digest is entirely determined by the enqueue_digest_emails
    # management command, not here.
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.info("Received digest event: %s" % (event,))
        handle_digest_email(event["user_profile_id"], event["cutoff"])

@assign_queue('email_mirror')
class MirrorWorker(QueueProcessingWorker):
    # who gets a digest is entirely determined by the enqueue_digest_emails
    # management command, not here.
    def consume(self, event: Mapping[str, Any]) -> None:
        message = force_str(event["message"])
        mirror_email(email.message_from_string(message),
                     rcpt_to=event["rcpt_to"], pre_checked=True)

@assign_queue('test', queue_type="test")
class TestWorker(QueueProcessingWorker):
    # This worker allows you to test the queue worker infrastructure without
    # creating significant side effects.  It can be useful in development or
    # for troubleshooting prod/staging.  It pulls a message off the test queue
    # and appends it to a file in /tmp.
    def consume(self, event: Mapping[str, Any]) -> None:  # nocoverage
        fn = settings.ZULIP_WORKER_TEST_FILE
        message = ujson.dumps(event)
        logging.info("TestWorker should append this message to %s: %s" % (fn, message))
        with open(fn, 'a') as f:
            f.write(message + '\n')

@assign_queue('embed_links')
class FetchLinksEmbedData(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        for url in event['urls']:
            url_preview.get_link_embed_data(url)

        message = Message.objects.get(id=event['message_id'])
        # If the message changed, we will run this task after updating the message
        # in zerver.views.messages.update_message_backend
        if message.content != event['message_content']:
            return
        if message.content is not None:
            query = UserMessage.objects.filter(
                message=message.id
            )
            message_user_ids = set(query.values_list('user_profile_id', flat=True))

            # Fetch the realm whose settings we're using for rendering
            realm = Realm.objects.get(id=event['message_realm_id'])

            # If rendering fails, the called code will raise a JsonableError.
            rendered_content = render_incoming_message(
                message,
                message.content,
                message_user_ids,
                realm)
            do_update_embedded_data(
                message.sender, message, message.content, rendered_content)

@assign_queue('outgoing_webhooks')
class OutgoingWebhookWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        message = event['message']
        dup_event = cast(Dict[str, Any], event)
        dup_event['command'] = message['content']

        services = get_bot_services(event['user_profile_id'])
        for service in services:
            dup_event['service_name'] = str(service.name)
            service_handler = get_outgoing_webhook_service_handler(service)
            request_data = service_handler.build_bot_request(dup_event)
            if request_data:
                do_rest_call(service.base_url,
                             request_data,
                             dup_event,
                             service_handler)

@assign_queue('embedded_bots')
class EmbeddedBotWorker(QueueProcessingWorker):

    def get_bot_api_client(self, user_profile: UserProfile) -> EmbeddedBotHandler:
        return EmbeddedBotHandler(user_profile)

    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile_id = event['user_profile_id']
        user_profile = get_user_profile_by_id(user_profile_id)

        message = cast(Dict[str, Any], event['message'])

        # TODO: Do we actually want to allow multiple Services per bot user?
        services = get_bot_services(user_profile_id)
        for service in services:
            bot_handler = get_bot_handler(str(service.name))
            if bot_handler is None:
                logging.error("Error: User %s has bot with invalid embedded bot service %s" % (
                    user_profile_id, service.name))
                continue
            try:
                if hasattr(bot_handler, 'initialize'):
                        bot_handler.initialize(self.get_bot_api_client(user_profile))
                if event['trigger'] == 'mention':
                    message['content'] = extract_query_without_mention(
                        message=message,
                        client=self.get_bot_api_client(user_profile),
                    )
                    assert message['content'] is not None
                bot_handler.handle_message(
                    message=message,
                    bot_handler=self.get_bot_api_client(user_profile)
                )
            except EmbeddedBotQuitException as e:
                logging.warning(str(e))

@assign_queue('deferred_work')
class DeferredWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        if event['type'] == 'mark_stream_messages_as_read':
            user_profile = get_user_profile_by_id(event['user_profile_id'])
            client = Client.objects.get(id=event['client_id'])

            for stream_id in event['stream_ids']:
                # Since the user just unsubscribed, we don't require
                # an active Subscription object (otherwise, private
                # streams would never be accessible)
                (stream, recipient, sub) = access_stream_by_id(user_profile, stream_id,
                                                               require_active=False)
                do_mark_stream_messages_as_read(user_profile, client, stream)
