var info_overlay = (function () {

var exports = {};

function adjust_mac_shortcuts() {
    var keys_map = [
        ['Backspace', 'Delete'],
        ['Enter', 'Return'],
        ['Home', 'Fn + Left'],
        ['End', 'Fn + Right'],
        ['PgUp', 'Fn + Up'],
        ['PgDn', 'Fn + Down'],
    ];

    $(".hotkeys_table").each(function () {
        var html = $(this).html();
        keys_map.forEach(function (pair) {
            html = html.replace(new RegExp(pair[0]), pair[1]);
        });
        $(this).html(html);
    });
}

// Make it explicit that our toggler is undefined until
// set_up_toggler is called.
exports.toggler = undefined;

exports.set_up_toggler = function () {
    var opts = {
        selected: 0,
        child_wants_focus: true,
        values: [
            { label: i18n.t("Keyboard shortcuts"), key: "keyboard-shortcuts" },
            { label: i18n.t("Message formatting"), key: "message-formatting" },
            { label: i18n.t("Search operators"), key: "search-operators" },
        ],
        callback: function (name, key) {
            $(".overlay-modal").hide();
            $("#" + key).show();
            $("#" + key).find(".modal-body").focus();
        },
    };

    var toggler = components.toggle(opts);
    var elem = toggler.get();
    elem.addClass('large');

    var modals = _.map(opts.values, function (item) {
        var key = item.key; // e.g. message-formatting
        var modal = $('#' + key).find('.modal-body');
        return modal;
    });

    _.each(modals, function (modal) {
        keydown_util.handle({
            elem: modal,
            handlers: {
                left_arrow: toggler.maybe_go_left,
                right_arrow: toggler.maybe_go_right,
            },
        });
    });

    $(".informational-overlays .overlay-tabs").append(elem);

    if (/Mac/i.test(navigator.userAgent)) {
        adjust_mac_shortcuts();
    }

    exports.toggler = toggler;
};

exports.show = function (target) {
    if (!exports.toggler) {
        exports.set_up_toggler();
    }

    var overlay = $(".informational-overlays");

    if (!overlay.hasClass("show")) {
        overlays.open_overlay({
            name:  'informationalOverlays',
            overlay: overlay,
            on_close: function () {
                hashchange.changehash("");
            },
        });
    }

    if (target) {
        exports.toggler.goto(target);
    }
};

exports.maybe_show_keyboard_shortcuts = function () {
    if (overlays.is_active()) {
        return;
    }
    if (popovers.any_active()) {
        return;
    }
    exports.show("keyboard-shortcuts");
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = info_overlay;
}
window.info_overlay = info_overlay;
