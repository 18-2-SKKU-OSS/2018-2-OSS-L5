# -*- coding: utf-8 -*-

import subprocess

from django.http import HttpResponse

from zerver.lib.test_helpers import (
    most_recent_message,
    most_recent_usermessage,
    POSTRequestMock)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    get_display_recipient,
    get_realm,
    get_stream,
    Recipient,
)

from zerver.lib.actions import (
    encode_email_address,
    ensure_stream,
    decode_email_address,
)
from zerver.lib.email_mirror import (
    process_message, process_stream_message, ZulipEmailForwardError,
    create_missed_message_address,
    get_missed_message_token_from_address,
)

from zerver.lib.send_email import FromAddress
from zerver.lib.notifications import (
    handle_missedmessage_emails,
)
from zerver.management.commands import email_mirror

from email.mime.text import MIMEText

import re
import ujson
import mock
import os
import sys
from io import StringIO
from django.conf import settings

from typing import Any, Callable, Dict, Mapping, Union, Optional

class TestEncodeDecode(ZulipTestCase):
    def test_encode_decode(self) -> None:
        realm = get_realm('zulip')
        stream_name = 'dev. help'
        stream = ensure_stream(realm, stream_name)
        email_address = encode_email_address(stream)
        self.assertTrue(email_address.startswith('dev%0046%0032help'))
        self.assertTrue(email_address.endswith('@testserver'))
        tup = decode_email_address(email_address)
        assert tup is not None
        (decoded_stream_name, token) = tup
        self.assertEqual(decoded_stream_name, stream_name)
        self.assertEqual(token, stream.email_token)

        email_address = email_address.replace('+', '.')
        tup = decode_email_address(email_address)
        assert tup is not None
        (decoded_stream_name, token) = tup
        self.assertEqual(decoded_stream_name, stream_name)
        self.assertEqual(token, stream.email_token)

        email_address = email_address.replace('@testserver', '@zulip.org')
        self.assertEqual(decode_email_address(email_address), None)

        with self.settings(EMAIL_GATEWAY_EXTRA_PATTERN_HACK='@zulip.org'):
            tup = decode_email_address(email_address)
            assert tup is not None
            (decoded_stream_name, token) = tup
            self.assertEqual(decoded_stream_name, stream_name)
            self.assertEqual(token, stream.email_token)

        self.assertEqual(decode_email_address('bogus'), None)

class TestEmailMirrorLibrary(ZulipTestCase):
    def test_get_missed_message_token(self) -> None:

        def get_token(address: str) -> str:
            with self.settings(EMAIL_GATEWAY_PATTERN="%s@example.com"):
                return get_missed_message_token_from_address(address)

        address = 'mm' + ('x' * 32) + '@example.com'
        token = get_token(address)
        self.assertEqual(token, 'x' * 32)

        # This next section was a bug at one point--we'd treat ordinary
        # user addresses that happened to begin with "mm" as being
        # the special mm+32chars tokens.
        address = 'mmathers@example.com'
        with self.assertRaises(ZulipEmailForwardError):
            get_token(address)

        # Now test the case where we our address does not match the
        # EMAIL_GATEWAY_PATTERN.
        # This used to crash in an ugly way; we want to throw a proper
        # exception.
        address = 'alice@not-the-domain-we-were-expecting.com'
        with self.assertRaises(ZulipEmailForwardError):
            get_token(address)

class TestStreamEmailMessagesSuccess(ZulipTestCase):
    def test_receive_stream_email_messages_success(self) -> None:

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

    def test_receive_stream_email_messages_blank_subject_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = ''
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), "(no topic)")

    def test_receive_private_stream_email_messages_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.make_stream("private_stream", invite_only=True)
        self.subscribe(user_profile, "private_stream")
        stream = get_stream("private_stream", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

class TestStreamEmailMessagesEmptyBody(ZulipTestCase):
    def test_receive_stream_email_messages_empty_body(self) -> None:

        # build dummy messages for stream
        # test message with empty body is not sent
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        headers = {}
        headers['Reply-To'] = self.example_email('othello')

        # empty body
        incoming_valid_message = MIMEText('')  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        exception_message = ""
        debug_info = {}  # type: Dict[str, Any]

        # process_message eats the exception & logs an error which can't be parsed here
        # so calling process_stream_message directly
        try:
            process_stream_message(incoming_valid_message['To'],
                                   incoming_valid_message['Subject'],
                                   incoming_valid_message,
                                   debug_info)
        except ZulipEmailForwardError as e:
            # empty body throws exception
            exception_message = str(e)
        self.assertEqual(exception_message, "Unable to find plaintext or HTML message body")

class TestMissedPersonalMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_personal_message_email_messages(self) -> None:

        # build dummy messages for missed messages email reply
        # have Hamlet send Othello a PM. Othello will reply via email
        # Hamlet will receive the message.
        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": self.example_email('othello')})
        self.assert_json_success(result)

        user_profile = self.example_user('othello')
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedMessageEmailMessages Body')  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestMissedMessageEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('othello')
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # self.login(self.example_email("hamlet"))
        # confirm that Hamlet got the message
        user_profile = self.example_user('hamlet')
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedMessageEmailMessages Body")
        self.assertEqual(message.sender, self.example_user('othello'))
        self.assertEqual(message.recipient.id, user_profile.id)
        self.assertEqual(message.recipient.type, Recipient.PERSONAL)

class TestMissedHuddleMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_huddle_message_email_messages(self) -> None:

        # build dummy messages for missed messages email reply
        # have Othello send Iago and Cordelia a PM. Cordelia will reply via email
        # Iago and Othello will receive the message.
        email = self.example_email('othello')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": ujson.dumps([self.example_email('cordelia'),
                                                                        self.example_email('iago')])})
        self.assert_json_success(result)

        user_profile = self.example_user('cordelia')
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedHuddleMessageEmailMessages Body')  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestMissedHuddleMessageEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('cordelia')
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = self.example_email('cordelia')

        process_message(incoming_valid_message)

        # Confirm Iago received the message.
        user_profile = self.example_user('iago')
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages Body")
        self.assertEqual(message.sender, self.example_user('cordelia'))
        self.assertEqual(message.recipient.type, Recipient.HUDDLE)

        # Confirm Othello received the message.
        user_profile = self.example_user('othello')
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages Body")
        self.assertEqual(message.sender, self.example_user('cordelia'))
        self.assertEqual(message.recipient.type, Recipient.HUDDLE)

class TestEmptyGatewaySetting(ZulipTestCase):
    def test_missed_message(self) -> None:
        email = self.example_email('othello')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": ujson.dumps([self.example_email('cordelia'),
                                                                        self.example_email('iago')])})
        self.assert_json_success(result)

        user_profile = self.example_user('cordelia')
        usermessage = most_recent_usermessage(user_profile)
        with self.settings(EMAIL_GATEWAY_PATTERN=''):
            mm_address = create_missed_message_address(user_profile, usermessage.message)
            self.assertEqual(mm_address, FromAddress.NOREPLY)

    def test_encode_email_addr(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))

        with self.settings(EMAIL_GATEWAY_PATTERN=''):
            test_address = encode_email_address(stream)
            self.assertEqual(test_address, '')

class TestReplyExtraction(ZulipTestCase):
    def test_reply_is_extracted_from_plain(self) -> None:

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        email = self.example_email('hamlet')
        self.login(email)
        user_profile = self.example_user('hamlet')
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        text = """Reply

        -----Original Message-----

        Quote"""

        incoming_valid_message = MIMEText(text)  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Reply")

    def test_reply_is_extracted_from_html(self) -> None:

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        email = self.example_email('hamlet')
        self.login(email)
        user_profile = self.example_user('hamlet')
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        html = """
        <html>
            <body>
                <p>Reply</p>
                <blockquote>

                    <div>
                        On 11-Apr-2011, at 6:54 PM, Bob &lt;bob@example.com&gt; wrote:
                    </div>

                    <div>
                        Quote
                    </div>

                </blockquote>
            </body>
        </html>
        """

        incoming_valid_message = MIMEText(html, 'html')  # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, 'Reply')


class TestScriptMTA(ZulipTestCase):

    def test_success(self) -> None:
        script = os.path.join(os.path.dirname(__file__),
                              '../../scripts/lib/email-mirror-postfix')

        sender = self.example_email('hamlet')
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)

        mail_template = self.fixture_data('simple.txt', type='email')
        mail = mail_template.format(stream_to_address=stream_to_address, sender=sender)
        read_pipe, write_pipe = os.pipe()
        os.write(write_pipe, mail.encode())
        os.close(write_pipe)
        subprocess.check_call(
            [script, '-r', stream_to_address, '-s', settings.SHARED_SECRET, '-t'],
            stdin=read_pipe)

    def test_error_no_recipient(self) -> None:
        script = os.path.join(os.path.dirname(__file__),
                              '../../scripts/lib/email-mirror-postfix')

        sender = self.example_email('hamlet')
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        mail_template = self.fixture_data('simple.txt', type='email')
        mail = mail_template.format(stream_to_address=stream_to_address, sender=sender)
        read_pipe, write_pipe = os.pipe()
        os.write(write_pipe, mail.encode())
        os.close(write_pipe)
        success_call = True
        try:
            subprocess.check_output([script, '-s', settings.SHARED_SECRET, '-t'],
                                    stdin=read_pipe)
        except subprocess.CalledProcessError as e:
            self.assertEqual(
                e.output,
                b'5.1.1 Bad destination mailbox address: No missed message email address.\n'
            )
            self.assertEqual(e.returncode, 67)
            success_call = False
        self.assertFalse(success_call)


class TestEmailMirrorTornadoView(ZulipTestCase):

    def send_private_message(self) -> str:
        email = self.example_email('othello')
        self.login(email)
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "test_receive_missed_message_email_messages",
                "client": "test suite",
                "to": ujson.dumps([self.example_email('cordelia'), self.example_email('iago')])
            })
        self.assert_json_success(result)

        user_profile = self.example_user('cordelia')
        user_message = most_recent_usermessage(user_profile)
        return create_missed_message_address(user_profile, user_message.message)

    @mock.patch('zerver.lib.email_mirror.queue_json_publish')
    def send_offline_message(self, to_address: str, sender: str,
                             mock_queue_json_publish: mock.Mock) -> HttpResponse:
        mail_template = self.fixture_data('simple.txt', type='email')
        mail = mail_template.format(stream_to_address=to_address, sender=sender)

        def check_queue_json_publish(queue_name: str,
                                     event: Union[Mapping[str, Any], str],
                                     processor: Optional[Callable[[Any], None]]=None) -> None:
            self.assertEqual(queue_name, "email_mirror")
            self.assertEqual(event, {"rcpt_to": to_address, "message": mail})

        mock_queue_json_publish.side_effect = check_queue_json_publish
        request_data = {
            "recipient": to_address,
            "msg_text": mail
        }
        post_data = dict(
            data=ujson.dumps(request_data),
            secret=settings.SHARED_SECRET
        )
        return self.client_post('/email_mirror_message', post_data)

    def test_success_stream(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        result = self.send_offline_message(stream_to_address, self.example_email('hamlet'))
        self.assert_json_success(result)

    def test_error_to_stream_with_wrong_address(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        stream_to_address = stream_to_address.replace("Denmark", "Wrong_stream")

        result = self.send_offline_message(stream_to_address, self.example_email('hamlet'))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: "
            "Please use the address specified in your Streams page.")

    def test_success_to_private(self) -> None:
        mm_address = self.send_private_message()
        result = self.send_offline_message(mm_address, self.example_email('cordelia'))
        self.assert_json_success(result)

    def test_using_mm_address_twice(self) -> None:
        mm_address = self.send_private_message()
        self.send_offline_message(mm_address, self.example_email('cordelia'))
        result = self.send_offline_message(mm_address, self.example_email('cordelia'))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: Bad or expired missed message address.")

    def test_wrong_missed_email_private_message(self) -> None:
        self.send_private_message()
        mm_address = 'mm' + ('x' * 32) + '@testserver'
        result = self.send_offline_message(mm_address, self.example_email('cordelia'))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: Bad or expired missed message address.")
