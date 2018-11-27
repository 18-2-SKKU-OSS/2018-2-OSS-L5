zrequire('Handlebars', 'handlebars');
zrequire('templates');
zrequire('i18n', 'i18next');

i18n.init({
    nsSeparator: false,
    keySeparator: false,
    interpolation: {
        prefix: "__",
        suffix: "__",
    },
    lng: 'fr',
    resources: {
        fr: {
            translation: {
                "Quote and reply": "French translation",
                "Notifications are triggered when a message arrives and Zulip isn't in focus or the message is offscreen.": "Some French text with Zulip",
            },
        },
    },
});

run_test('t_tag', () => {
    var args = {
        message: {
            is_stream: true,
            id: "99",
            stream: "devel",
            subject: "testing",
            sender_full_name: "King Lear",
        },
        should_display_quote_and_reply: true,
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    var html = global.render_template('actions_popover_content', args);
    assert(html.indexOf("French translation") > 0);
});

run_test('tr_tag', () => {
    var args = {
        page_params: {
            full_name: "John Doe",
            password_auth_enabled: false,
            avatar_url: "http://example.com",
            left_side_userlist: false,
            twenty_four_hour_time: false,
            enable_stream_desktop_notifications: false,
            enable_stream_push_notifications: false,
            enable_stream_sounds: false,
            enable_desktop_notifications: false,
            enable_sounds: false,
            enable_offline_email_notifications: false,
            enable_offline_push_notifications: false,
            enable_online_push_notifications: false,
            enable_digest_emails: false,
        },
    };

    var html = global.render_template('settings_tab', args);
    assert(html.indexOf('Some French text with Zulip') > 0);
});
