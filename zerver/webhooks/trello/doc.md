Get Zulip notifications from your Trello boards!

!!! tip ""
    Note that [Zapier][1] is usually a simpler way to
    integrate Trello with Zulip.

[1]: ./zapier

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. **Log in to Trello**, and collect the following three items:

    * **Board ID**: Go to your Trello board. The URL should look like
      `https://trello.com/b/<BOARD_ID>/<BOARD_NAME>`. Note down the
      `<BOARD_ID>`.

    * **API Key**: Go to <https://trello.com/1/appkey/generate>. Note down the
      key listed under **Developer API Keys**.

    * **User Token**: Go to <https://trello.com/1/appkey/generate>. Under
      **Developer API Keys**, click on the **Token** link. Click on **Allow**.
      Note down the token generated.

    You're now going to need to run a Trello configuration script from a
    computer (any computer) connected to the internet. It won't make any
    changes to the computer.

1.  Make sure you have a working copy of Python. If you're running
    macOS or Linux, you very likely already do. If you're running
    Windows you may or may not.  If you don't have Python, follow the
    installation instructions
    [here](https://realpython.com/installing-python/). Note that you
    do not need the latest version of Python; anything 2.7 or higher
    will do.

1. Download [zulip-trello.py][2]. `Ctrl+s` or `Cmd+s` on that page should
   work in most browsers.

1. Run the `zulip-trello` script in a terminal, after replacing the
   arguments with the values collected above.

    ```
    python zulip_trello.py --trello-board-name <trello_board_name> \
                           --trello-board-id   <trello_board_id> \
                           --trello-api-key  <trello_api_key> \
                           --trello-token <trello_token> \
                           --zulip-webhook-url <zulip_webhook_url>
    ```

    The `zulip_trello.py` script only needs to be run once, and can be run
    on any computer with python.

1. You can delete `zulip_trello.py` from your computer if you'd like.

[2]: https://raw.githubusercontent.com/zulip/python-zulip-api/master/zulip/integrations/trello/zulip_trello.py

{!congrats.md!}

![](/static/images/integrations/trello/001.png)

**Advanced**

You can learn more about Trello's webhooks via their
[webhook API documentation](https://developers.trello.com/page/webhooks).

Trello does not provide a web interface for their outgoing notifications, so
any webhook configuration must be done through their API.
