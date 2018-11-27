{!create-stream.md!}

Next, on your {{ settings_html|safe }}, create a bot.

Construct a webhook URL like the following:

`{{ api_url }}/v1/external/zendesk?ticket_title={% raw %}{{ ticket.title }}&ticket_id={{ ticket.id }}{% endraw %}`

{!append-stream-name.md!}

Next, in Zendesk, open your **Admin** view via gear in the bottom-left
corner. In the **Admin** view, click on **Extensions**, then click
**add target**.

![](/static/images/integrations/zendesk/001.png)
![](/static/images/integrations/zendesk/002.png)

From there, click **URL target**. Fill in the form like this:

* **Title**: Zulip
* **URL**: the URL we created above
* **Method**: POST
* **Attribute Name**: message
* **Username**: *your bot's user name, e.g.* `zendesk-bot@yourdomain.com`
* **Password**: *your bot's API key*

![](/static/images/integrations/zendesk/003.png)

Now, select **Test Target** and click **Submit**. A test message should
appear in the `zendesk` stream. If the message was received, save the
target by selecting **Create target** and clicking **Submit**.

From here, add a new trigger. You'll do this for every action you want
to create a Zulip notification for. Triggers are added by selecting
**Triggers** in the left menu and then clicking **add trigger** in the
top right.

![](/static/images/integrations/zendesk/004.png)
![](/static/images/integrations/zendesk/005.png)

Let's say you want a notification each time a ticket is updated. Put
in a descriptive title like "Announce ticket update". Under **Meet all of
the folllowing conditions** select **Ticket: is...** and then select
**Updated**. In the **Perform these actions** section, select
**Notification: Notify target**, then select **Zulip**.

Next we need need to enter the message body into Message. You can use
Zulip markdown and the Zendesk placeholders when creating your message.

You can copy this example template:

{% raw %}
~~~
Ticket [#{{ ticket.id }}: {{ ticket.title }}]({{ ticket.link }}), was updated by {{ current_user.name }}

* Status: {{ ticket.status }}
* Priority: {{ ticket.priority }}
* Type: {{ ticket.ticket_type }}
* Assignee: {{ ticket.assignee.name }}
* Tags: {{ ticket.tags }}
* Description:
``` quote
{{ ticket.description }}
```
~~~
{% endraw %}

![](/static/images/integrations/zendesk/006.png)

Finally, click **Submit**.

{!congrats.md!}

![](/static/images/integrations/zendesk/007.png)
