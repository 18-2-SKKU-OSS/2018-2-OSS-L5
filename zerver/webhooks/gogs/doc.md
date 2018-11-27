Receive Gogs notifications in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

   {!git-webhook-url-with-branches-indented.md!}

1. Go to your repository on Gogs and click on **Settings**. Select
   **Webhooks** on the left sidebar, and click **Add Webhook**.
   Select **Gogs**.

1. Set **Payload URL** to the URL constructed above. Set **Content type**
   to `application/json`. Select the events you would like to receive
   notifications for, and click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/gogs/001.png)
