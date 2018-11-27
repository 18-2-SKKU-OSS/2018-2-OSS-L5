# Integrations overview

Integrations allow you to send data from other products into or out of
Zulip. Zulip natively integrates with dozens of products, and with hundreds
more through Zapier, IFTTT, and Hubot.

Zulip also makes it very easy to write your own integration, and (if you'd
like) to get it merged into the main Zulip repository.

Integrations are one of the most important parts of a group chat tool like
Zulip, and we are committed to making integrating with Zulip as easy as
possible.

## Set up an existing integration

Most existing integrations send content from a third-party product into
Zulip.

* Search Zulip's [list of native integrations](/integrations) for the
  third-party product. Each integration has a page describing how to set it
  up.

* Check if [Zapier](https://zapier.com/apps) has an integration with the
  product. If it does, follow [these instructions](/integrations/doc/zapier)
  to set it up.

* Check if [IFTTT](https://ifttt.com/search) has an integration with the
  product. If it does, follow [these instructions](/integrations/doc/ifttt)
  to set it up.

* Check if [Hubot](https://github.com/hubot-scripts) has an integration with
  the product. If it does, follow
  [these instructions](/integrations/doc/hubot) to set it up.

* If the product can send email notifications, you can
  [send those emails to a stream](/help/message-a-stream-by-email).

## Write your own integration

We've put a lot of effort into making this as easy as possible, but all of
the options below do require some comfort writing code. If you need an
integration and don't have an engineer on staff, reach out to
`support@zulipchat.com` and we'll see what we can do.

### Sending content into Zulip

* If the third-party service supports outgoing webhooks, you likely want to
  build an [incoming webhook integration](/api/incoming-webhooks-overview).

* If it doesn't, you may want to write a
  [script or plugin integration](/api/non-webhook-integrations).

* Finally, you can
  [send messages using Zulip's API](/api/send-message).

### Sending and receiving content

* To react to activity inside Zulip, look at Zulip's
  [Python framework for interactive bots](/api/running-bots) or
  [Zulip's real-time events API](/api/get-events-from-queue).

* If what you want isn't covered by the above, check out the full
  [REST API](/api/rest). The web, mobile, desktop, and terminal apps are
  built on top of this API, so it can do anything a human user can do. Most
  but not all of the endpoints are documented on this site; if you need
  something that isn't there check out Zulip's
  [REST endpoints](https://github.com/zulip/zulip/tree/master/zproject/urls.py)
  or email `support@zulipchat.com` and we'll help you out.
