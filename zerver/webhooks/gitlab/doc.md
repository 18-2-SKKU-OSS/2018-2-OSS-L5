Receive GitLab notifications in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

   {!git-webhook-url-with-branches-indented.md!}

1. Go to your repository on GitLab and click **Settings** on the left
   sidebar.  Click on **Integrations**.

1. Set **URL** to the URL constructed above. Select the events you
   you would like to receive notifications for, and click
   **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/gitlab/001.png)

!!! tip ""
    If your GitLab server and your Zulip server are on a local network
    together, and you're running GitLab 10.5 or newer, you may need to enable
    GitLab's "Allow requests to the local network from hooks and
    services" setting (by default, recent GitLab versions refuse to post
    webhook events to servers on the local network).  You can find this
    setting near the bottom of the GitLab "Settings" page in the "Admin area".
