Front lets you manage all of your communication channels in one place,
and helps your team collaborate around every message. Follow these steps
to recieve Front notifications without leaving Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Go to the **Settings** page of your Front organization. Click on the
**Integrations** tab, and enable the **Webhooks** integration. Click on
the **Rules** tab, and add a new rule. Select the events you would like to
be notified about. Set the URL of the target webhook to the URL
constructed above.

1. Go to the **Settings** page of your Zulip organization. Click on the
**Linkifiers** tab, and add a new linkifier. Set the pattern to
`cnv_(?P<id>[0-9a-z]+)`. Set the URL format string to
`https://app.frontapp.com/open/cnv_%(id)s`. This step is necessary to map
Front conversations to topics in Zulip.

{!congrats.md!}

![](/static/images/integrations/front/001.png)
