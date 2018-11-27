function MessageListView(list, table_name, collapse_messages) {
    this.list = list;
    this.collapse_messages = collapse_messages;
    this._rows = {};
    this.message_containers = {};
    this.table_name = table_name;
    if (this.table_name) {
        this.clear_table();
    }
    this._message_groups = [];

    // Half-open interval of the indices that define the current render window
    this._render_win_start = 0;
    this._render_win_end = 0;
}

(function () {

function mention_button_refers_to_me(elem) {
    var user_id = $(elem).attr('data-user-id');
    if (user_id === '*' || people.is_my_user_id(user_id)) {
        return true;
    }

    // Handle legacy markdown that was rendered before we cut
    // over to using data-user-id.
    var email = $(elem).attr('data-user-email');
    if (email === '*' || people.is_current_user(email)) {
        return true;
    }

    return false;
}

function same_day(earlier_msg, later_msg) {
    if (earlier_msg === undefined || later_msg === undefined) {
        return false;
    }
    var earlier_time = new XDate(earlier_msg.msg.timestamp * 1000);
    var later_time = new XDate(later_msg.msg.timestamp * 1000);

    return earlier_time.toDateString() === later_time.toDateString();
}

function same_sender(a, b) {
    if (a === undefined || b === undefined) {
        return false;
    }
    return util.same_sender(a.msg, b.msg);
}

function same_recipient(a, b) {
    if (a === undefined || b === undefined) {
        return false;
    }
    return util.same_recipient(a.msg, b.msg);
}

function update_group_time_display(group, message_container, prev) {
    var time = new XDate(message_container.msg.timestamp * 1000);
    var today = new XDate();

    if (prev !== undefined) {
        var prev_time = new XDate(prev.msg.timestamp * 1000);
        if (time.toDateString() !== prev_time.toDateString()) {
            // NB: show_date is HTML, inserted into the document without escaping.
            group.show_date = timerender.render_date(time, prev_time, today)[0].outerHTML;
            group.show_date_separator = true;
        }
    } else {
        // Show the date in the recipient bar, but not a date separator bar.
        group.show_date_separator = false;
        group.show_date = timerender.render_date(time, undefined, today)[0].outerHTML;
    }
}

function update_timestr(message_container) {
    if (message_container.timestr === undefined) {
        var time = new XDate(message_container.msg.timestamp * 1000);
        message_container.timestr = timerender.stringify_time(time);
    }
}

function set_topic_edit_properties(group, message) {
    group.realm_allow_message_editing = page_params.realm_allow_message_editing;
    group.always_visible_topic_edit = false;
    group.on_hover_topic_edit = false;

    // Messages with no topics should always have an edit icon visible
    // to encourage updating them. Admins can also edit any topic.
    if (message.subject === compose.empty_topic_placeholder()) {
        group.always_visible_topic_edit = true;
    } else if (page_params.is_admin || message_edit.is_topic_editable(message)) {
        group.on_hover_topic_edit = true;
    }
}

function populate_group_from_message_container(group, message_container) {
    group.is_stream = message_container.msg.is_stream;
    group.is_private = message_container.msg.is_private;

    if (group.is_stream) {
        group.background_color = stream_data.get_color(message_container.msg.stream);
        group.color_class = stream_color.get_color_class(group.background_color);
        group.invite_only = stream_data.get_invite_only(message_container.msg.stream);
        group.topic = message_container.msg.subject;
        group.match_topic = util.get_match_topic(message_container.msg);
        group.stream_url = message_container.stream_url;
        group.topic_url = message_container.topic_url;
        var sub = stream_data.get_sub(message_container.msg.stream);
        if (sub === undefined) {
            // Hack to handle unusual cases like the tutorial where
            // the streams used don't actually exist in the subs
            // module.  Ideally, we'd clean this up by making the
            // tutorial populate subs.js "properly".
            group.stream_id = -1;
        } else {
            group.stream_id = sub.stream_id;
        }
    } else if (group.is_private) {
        group.pm_with_url = message_container.pm_with_url;
        group.display_reply_to = message_store.get_pm_full_names(message_container.msg);
    }
    group.display_recipient = message_container.msg.display_recipient;
    group.topic_links = util.get_topic_links(message_container.msg);

    set_topic_edit_properties(group, message_container.msg);

    var time = new XDate(message_container.msg.timestamp * 1000);
    var today = new XDate();
    var date_element = timerender.render_date(time, undefined, today)[0];

    group.date = date_element.outerHTML;
}

MessageListView.prototype = {
    // Number of messages to render at a time
    _RENDER_WINDOW_SIZE: 400,
    // Number of messages away from edge of render window at which we
    // trigger a re-render
    _RENDER_THRESHOLD: 50,

    _add_msg_timestring: function (message_container) {
        if (message_container.msg.last_edit_timestamp !== undefined) {
            // Add or update the last_edit_timestr
            var last_edit_time = new XDate(message_container.msg.last_edit_timestamp * 1000);
            var today = new XDate();
            message_container.last_edit_timestr =
                timerender.render_date(last_edit_time, undefined, today)[0].textContent
                + " at " + timerender.stringify_time(last_edit_time);
        }
    },

    add_subscription_marker: function (group, last_msg_container, first_msg_container) {
        if (last_msg_container === undefined) {
            return;
        }

        var last_subscribed = !last_msg_container.msg.historical;
        var first_subscribed = !first_msg_container.msg.historical;
        var stream = first_msg_container.msg.stream;

        if (!last_subscribed && first_subscribed) {
            group.bookend_top = true;
            group.subscribed = stream;
            group.bookend_content = this.list.subscribed_bookend_content(stream);
            return;
        }

        if (last_subscribed && !first_subscribed) {
            group.bookend_top = true;
            group.unsubscribed = stream;
            group.bookend_content = this.list.unsubscribed_bookend_content(stream);
            return;
        }
    },

    build_message_groups: function (message_containers) {
        function start_group() {
            return {
                message_containers: [],
                message_group_id: _.uniqueId('message_group_'),
            };
        }

        var self = this;
        var current_group = start_group();
        var new_message_groups = [];
        var prev;

        function add_message_container_to_group(message_container) {
            if (same_sender(prev, message_container)) {
                prev.next_is_same_sender = true;
            }
            current_group.message_containers.push(message_container);
        }

        function finish_group() {
            if (current_group.message_containers.length > 0) {
                populate_group_from_message_container(current_group,
                                                      current_group.message_containers[0]);
                current_group
                    .message_containers[current_group.message_containers.length - 1]
                    .include_footer = true;
                new_message_groups.push(current_group);
            }
        }

        _.each(message_containers, function (message_container) {
            var message_reactions = reactions.get_message_reactions(message_container.msg);
            message_container.msg.message_reactions = message_reactions;
            message_container.include_recipient = false;
            message_container.include_footer    = false;

            if (same_recipient(prev, message_container) && self.collapse_messages &&
                prev.msg.historical === message_container.msg.historical &&
                same_day(prev, message_container)) {
                add_message_container_to_group(message_container);
            } else {
                finish_group();
                current_group = start_group();
                add_message_container_to_group(message_container);

                message_container.include_recipient = true;
                message_container.subscribed = false;
                message_container.unsubscribed = false;

                // This home_msg_list condition can be removed
                // once we filter historical messages from the
                // home view on the server side (which requires
                // having an index on UserMessage.flags)
                if (self.list !== home_msg_list) {
                    self.add_subscription_marker(current_group, prev, message_container);
                }

                if (message_container.msg.stream) {
                    message_container.stream_url =
                        hash_util.by_stream_uri(message_container.msg.stream);
                    message_container.topic_url =
                        hash_util.by_stream_topic_uri(
                            message_container.msg.stream,
                            message_container.msg.subject);
                } else {
                    message_container.pm_with_url =
                        message_container.msg.pm_with_url;
                }
            }

            update_group_time_display(current_group, message_container, prev);
            update_timestr(message_container);

            message_container.include_sender = true;
            if (!message_container.include_recipient &&
                !prev.status_message &&
                same_sender(prev, message_container)) {
                message_container.include_sender = false;
            }

            message_container.sender_is_bot = people.sender_is_bot(message_container.msg);
            message_container.sender_is_guest = people.sender_is_guest(message_container.msg);

            self._add_msg_timestring(message_container);

            message_container.small_avatar_url = people.small_avatar_url(message_container.msg);
            if (message_container.msg.stream !== undefined) {
                message_container.background_color =
                    stream_data.get_color(message_container.msg.stream);
            }

            message_container.contains_mention = message_container.msg.mentioned;
            self._maybe_format_me_message(message_container);

            prev = message_container;
        });

        finish_group();

        return new_message_groups;
    },

    join_message_groups: function (first_group, second_group) {
        // join_message_groups will combine groups if they have the
        // same_recipient on the same_day and the view supports collapsing
        // otherwise it may add a subscription_marker if required.
        // It returns true if the two groups were joined in to one and
        // the second_group should be ignored.
        if (first_group === undefined || second_group === undefined) {
            return false;
        }
        var last_msg_container = _.last(first_group.message_containers);
        var first_msg_container = _.first(second_group.message_containers);

        // Join two groups into one.
        if (this.collapse_messages && same_recipient(last_msg_container, first_msg_container) &&
            same_day(last_msg_container, first_msg_container) &&
            last_msg_container.msg.historical === first_msg_container.msg.historical) {
            if (!last_msg_container.status_message && !first_msg_container.msg.is_me_message
                && same_sender(last_msg_container, first_msg_container)) {
                first_msg_container.include_sender = false;
            }
            if (same_sender(last_msg_container, first_msg_container)) {
                last_msg_container.next_is_same_sender = true;
            }
            first_group.message_containers =
                first_group.message_containers.concat(second_group.message_containers);
            return true;
        // Add a subscription marker
        } else if (this.list !== home_msg_list &&
                   last_msg_container.msg.historical !== first_msg_container.msg.historical) {
            second_group.bookend_top = true;
            this.add_subscription_marker(second_group, last_msg_container, first_msg_container);
        }
        return false;
    },

    merge_message_groups: function (new_message_groups, where) {
        // merge_message_groups takes a list of new messages groups to add to
        // this._message_groups and a location where to merge them currently
        // top or bottom. It returns an object of changes which needed to be
        // rendered in to the page. The types of actions are append_group,
        // prepend_group, rerender_group, append_message.
        //
        // append_groups are groups to add to the top of the rendered DOM
        // prepend_groups are group to add to the bottom of the rendered DOM
        // rerender_groups are group that should be updated in place in the DOM
        // append_messages are messages which should be added to the last group in the DOM
        // rerender_messages are messages which should be updated in place in the DOM

        var message_actions = {
            append_groups: [],
            prepend_groups: [],
            rerender_groups: [],
            append_messages: [],
            rerender_messages: [],
        };
        var first_group;
        var second_group;
        var curr_msg_container;
        var prev_msg_container;

        if (where === 'top') {
            first_group = _.last(new_message_groups);
            second_group = _.first(this._message_groups);
            if (this.join_message_groups(first_group, second_group)) {
                // join_message_groups moved the old message to the end of the
                // new group. We need to replace the old rendered message
                // group. So we will reuse its ID.

                first_group.message_group_id = second_group.message_group_id;
                message_actions.rerender_groups.push(first_group);

                // Swap the new group in
                this._message_groups.shift();
                this._message_groups.unshift(first_group);

                new_message_groups = _.initial(new_message_groups);
            } else if (!same_day(second_group.message_containers[0],
                                 first_group.message_containers[0])) {
                prev_msg_container = _.last(first_group.message_containers);
                curr_msg_container = _.first(second_group.message_containers);

                // The groups did not merge, so we need up update the date row for the old group
                update_group_time_display(second_group, curr_msg_container, prev_msg_container);
                update_timestr(curr_msg_container);
                // We could add an action to update the date row, but for now rerender the group.
                message_actions.rerender_groups.push(second_group);
            }
            message_actions.prepend_groups = new_message_groups;
            this._message_groups = new_message_groups.concat(this._message_groups);
        } else {
            first_group = _.last(this._message_groups);
            second_group = _.first(new_message_groups);
            if (this.join_message_groups(first_group, second_group)) {
                // rerender the last message
                message_actions.rerender_messages.push(
                    first_group.message_containers[
                        first_group.message_containers.length
                        - second_group.message_containers.length - 1]
                );
                message_actions.append_messages = _.first(new_message_groups).message_containers;
                new_message_groups = _.rest(new_message_groups);
            } else if (first_group !== undefined && second_group !== undefined) {
                prev_msg_container = _.last(first_group.message_containers);
                curr_msg_container = _.first(second_group.message_containers);

                if (same_day(prev_msg_container, curr_msg_container)) {
                    // Clear the date if it is the same as the last group
                    second_group.show_date = false;
                    second_group.show_date_separator = undefined;
                } else {
                    // If we just sent the first message on a new day
                    // in a narrow, make sure we render a date separator.
                    update_group_time_display(second_group, curr_msg_container, prev_msg_container);
                    update_timestr(curr_msg_container);
                }
            }
            message_actions.append_groups = new_message_groups;
            this._message_groups = this._message_groups.concat(new_message_groups);
        }

        return message_actions;
    },

    _put_row: function (row) {
        // row is a jQuery object wrapping one message row
        if (row.hasClass('message_row')) {
            this._rows[row.attr('zid')] = row;
        }
    },

    _post_process: function ($message_rows) {
        // $message_rows wraps one or more message rows

        if ($message_rows.constructor !== jQuery) {
            // An assertion check that we're calling this properly
            blueslip.error('programming error--pass in jQuery objects');
        }

        var self = this;
        _.each($message_rows, function (dom_row) {
            var row = $(dom_row);
            self._put_row(row);
            self._post_process_single_row(row);
        });
    },

    _post_process_single_row: function (row) {
        // For message formatting that requires some post-processing
        // (and is not possible to handle solely via CSS), this is
        // where we modify the content.  It is a goal to minimize how
        // much logic is present in this function; wherever possible,
        // we should implement features with the markdown processor,
        // HTML and CSS.

        if (row.length !== 1) {
            blueslip.error('programming error--expected single element');
        }

        var content = row.find('.message_content');

        // Set the rtl class if the text has an rtl direction
        if (rtl.get_direction(content.text()) === 'rtl') {
            content.addClass('rtl');
        }

        if (row.hasClass('mention')) {
            row.find('.user-mention').each(function () {
                // We give special highlights to the mention buttons
                // that refer to the current user.
                if (mention_button_refers_to_me(this)) {
                    $(this).addClass('user-mention-me');
                }
            });
        }

        // Display emoji (including realm emoji) as text if
        // page_params.emojiset is 'text'.
        if (page_params.emojiset === 'text') {
            row.find(".emoji").replaceWith(function () {
                var text = $(this).attr("title");
                return ":" + text + ":";
            });
        }

        var id = rows.id(row);
        message_edit.maybe_show_edit(row, id);

        submessage.process_submessages({
            row: row,
            message_id: id,
        });
    },

    _get_message_template: function (message_container) {
        var msg_reactions = reactions.get_message_reactions(message_container.msg);
        message_container.msg.message_reactions = msg_reactions;
        var msg_to_render = _.extend(message_container, {
            table_name: this.table_name,
        });
        return templates.render('single_message', msg_to_render);
    },

    render: function (messages, where, messages_are_new) {
        // This function processes messages into chunks with separators between them,
        // and templates them to be inserted as table rows into the DOM.

        if (messages.length === 0 || this.table_name === undefined) {
            return;
        }

        var list = this.list; // for convenience
        var table_name = this.table_name;
        var table = rows.get_table(table_name);
        var orig_scrolltop_offset;
        var message_containers;

        var self = this;

        // The messages we are being asked to render are shared with between
        // all messages lists. To prevent having both list views overwriting
        // each others data we will make a new message object to add data to
        // for rendering.
        message_containers = _.map(messages, function (message) {
            if (message.starred) {
                message.starred_status = i18n.t("Unstar");
            } else {
                message.starred_status = i18n.t("Star");
            }

            return {msg: message};
        });

        function save_scroll_position() {
            if (orig_scrolltop_offset === undefined && self.selected_row().length > 0) {
                orig_scrolltop_offset = self.selected_row().offset().top;
            }
        }

        function restore_scroll_position() {
            if (list === current_msg_list && orig_scrolltop_offset !== undefined) {
                list.view.set_message_offset(orig_scrolltop_offset);
                list.reselect_selected_id();
            }
        }

        // This function processes messages into chunks with separators between them,
        // and templates them to be inserted as table rows into the DOM.

        if (message_containers.length === 0 || this.table_name === undefined) {
            return;
        }

        var new_message_groups = this.build_message_groups(message_containers, this.table_name);
        var message_actions = this.merge_message_groups(new_message_groups, where);
        var new_dom_elements = [];
        var rendered_groups;
        var dom_messages;
        var last_message_row;
        var last_group_row;

        _.each(message_containers, function (message_container) {
            self.message_containers[message_container.msg.id] = message_container;
        });

        // Render new message groups on the top
        if (message_actions.prepend_groups.length > 0) {
            save_scroll_position();

            rendered_groups = $(templates.render('message_group', {
                message_groups: message_actions.prepend_groups,
                use_match_properties: self.list.is_search(),
                table_name: self.table_name,
            }));

            dom_messages = rendered_groups.find('.message_row');
            new_dom_elements = new_dom_elements.concat(rendered_groups);

            self._post_process(dom_messages);

            // The date row will be included in the message groups or will be
            // added in a rerenderd in the group below
            table.find('.recipient_row').first().prev('.date_row').remove();
            table.prepend(rendered_groups);
            condense.condense_and_collapse(dom_messages);
        }

        // Rerender message groups
        if (message_actions.rerender_groups.length > 0) {
            save_scroll_position();

            _.each(message_actions.rerender_groups, function (message_group) {
                var old_message_group = $('#' + message_group.message_group_id);
                // Remove the top date_row, we'll re-add it after rendering
                old_message_group.prev('.date_row').remove();

                rendered_groups = $(templates.render('message_group', {
                    message_groups: [message_group],
                    use_match_properties: self.list.is_search(),
                    table_name: self.table_name,
                }));

                dom_messages = rendered_groups.find('.message_row');
                // Not adding to new_dom_elements it is only used for autoscroll

                self._post_process(dom_messages);
                old_message_group.replaceWith(rendered_groups);
                condense.condense_and_collapse(dom_messages);
            });
        }

        // Rerender message rows
        if (message_actions.rerender_messages.length > 0) {
            _.each(message_actions.rerender_messages, function (message_container) {
                var old_row = self.get_row(message_container.msg.id);
                var row = $(self._get_message_template(message_container));
                self._post_process(row);
                old_row.replaceWith(row);
                condense.condense_and_collapse(row);
                list.reselect_selected_id();
            });
        }

        // Insert new messages in to the last message group
        if (message_actions.append_messages.length > 0) {
            last_message_row = table.find('.message_row:last').expectOne();
            last_group_row = rows.get_message_recipient_row(last_message_row);
            dom_messages = $(_.map(message_actions.append_messages, function (message_container) {
                return self._get_message_template(message_container);
            }).join('')).filter('.message_row');

            self._post_process(dom_messages);
            last_group_row.append(dom_messages);

            condense.condense_and_collapse(dom_messages);
            new_dom_elements = new_dom_elements.concat(dom_messages);
        }

        // Add new message groups to the end
        if (message_actions.append_groups.length > 0) {
            // Remove the trailing bookend; it'll be re-added after we do our rendering
            self.clear_trailing_bookend();

            rendered_groups = $(templates.render('message_group', {
                message_groups: message_actions.append_groups,
                use_match_properties: self.list.is_search(),
                table_name: self.table_name,
            }));

            dom_messages = rendered_groups.find('.message_row');
            new_dom_elements = new_dom_elements.concat(rendered_groups);

            self._post_process(dom_messages);

            // This next line is a workaround for a weird scrolling
            // bug on Chrome.  Basically, in Chrome 64, we had a
            // highly reproducible bug where if you hit the "End" key
            // 5 times in a row in a `near:1` narrow (or any other
            // narrow with enough content below to try this), the 5th
            // time (because RENDER_WINDOW_SIZE / batch_size = 4,
            // i.e. the first time we need to rerender to show the
            // message "End" jumps to) would trigger an unexpected
            // scroll, resulting in some chaotic scrolling and
            // additional fetches (from bottom_whitespace ending up in
            // the view).  During debugging, we found that this adding
            // this next line seems to prevent the Chrome bug from firing.
            message_viewport.scrollTop();

            table.append(rendered_groups);
            condense.condense_and_collapse(dom_messages);
        }

        restore_scroll_position();

        var last_message_group = _.last(self._message_groups);
        if (last_message_group !== undefined) {
            list.last_message_historical =
                _.last(last_message_group.message_containers).msg.historical;
        }

        var stream_name = narrow_state.stream();
        if (stream_name !== undefined) {
            // If user narrows to a stream, doesn't update
            // trailing bookend if user is subscribed.
            var sub = stream_data.get_sub(stream_name);
            if (sub === undefined || !sub.subscribed) {
                list.update_trailing_bookend();
            }
        }

        if (list === current_msg_list) {
            // Update the fade.

            var get_element = function (message_group) {
                // We don't have a MessageGroup class, but we can at least hide the messy details
                // of rows.js from compose_fade.  We provide a callback function to be lazy--
                // compose_fade may not actually need the elements depending on its internal
                // state.
                var message_row = self.get_row(message_group.message_containers[0].msg.id);
                return rows.get_message_recipient_row(message_row);
            };

            compose_fade.update_rendered_message_groups(new_message_groups, get_element);
        }

        if (list === current_msg_list && messages_are_new) {
            self._maybe_autoscroll(new_dom_elements);
        }
    },


    _maybe_autoscroll: function (rendered_elems) {
        // If we are near the bottom of our feed (the bottom is visible) and can
        // scroll up without moving the pointer out of the viewport, do so, by
        // up to the amount taken up by the new message.
        var new_messages_height = 0;
        var id_of_last_message_sent_by_us = -1;

        // C++ iterators would have made this less painful
        _.each(rendered_elems.reverse(), function (elem) {
            // Sometimes there are non-DOM elements in rendered_elems; only
            // try to get the heights of actual trs.
            if (elem.is("div")) {
                new_messages_height += elem.height();
                // starting from the last message, ignore message heights that weren't sent by me.
                if (id_of_last_message_sent_by_us > -1) {
                    return;
                }
                var row_id = rows.id(elem);
                // check for `row_id` NaN in case we're looking at a date row or bookend row
                if (row_id > -1 &&
                    people.is_current_user(this.get_message(row_id).sender_email)) {
                    id_of_last_message_sent_by_us = rows.id(elem);
                }
            }
        }, this);

        var selected_row = this.selected_row();
        var last_visible = rows.last_visible();

        // Make sure we have a selected row and last visible row. (defensive)
        if (!(selected_row && selected_row.length > 0 && last_visible)) {
            return;
        }

        var selected_row_offset = selected_row.offset().top;
        var info = message_viewport.message_viewport_info();
        var available_space_for_scroll = selected_row_offset - info.visible_top;

        // Don't scroll if we can't move the pointer up.
        if (available_space_for_scroll <= 0) {
            return;
        }

        if (new_messages_height <= 0) {
            return;
        }

        if (!activity.has_focus) {
            // Don't autoscroll if the window hasn't had focus
            // recently.  This in intended to help protect us from
            // auto-scrolling downwards when the window is in the
            // background and might be having some functionality
            // throttled by modern Chrome's aggressive power-saving
            // features.
            blueslip.log("Suppressing scrolldown due to inactivity");
            return;
        }

        // do not scroll if there are any active popovers.
        if (popovers.any_active()) {
            return;
        }

        // This next decision is fairly debatable.  For a big message that
        // would push the pointer off the screen, we do a partial autoscroll,
        // which has the following implications:
        //    a) user sees scrolling (good)
        //    b) user's pointer stays on screen (good)
        //    c) scroll amount isn't really tied to size of new messages (bad)
        //    d) all the bad things about scrolling for users who want messages
        //       to stay on the screen
        var scroll_amount = new_messages_height;

        if (scroll_amount > available_space_for_scroll) {
            scroll_amount = available_space_for_scroll;
        }

        // Let's work our way back to whether the user was already dealing
        // with messages off the screen, in which case we shouldn't autoscroll.
        var bottom_last_visible = last_visible.offset().top + last_visible.height();
        var bottom_old_last_visible = bottom_last_visible - new_messages_height;
        var bottom_viewport = info.visible_top + info.visible_height;

        // Exit if the user was already past the bottom.
        if (bottom_old_last_visible > bottom_viewport) {
            return;
        }

        // Ok, we are finally ready to actually scroll.
        message_viewport.system_initiated_animate_scroll(scroll_amount);
    },


    clear_rendering_state: function (clear_table) {
        if (clear_table) {
            this.clear_table();
        }
        this.list.last_message_historical = false;

        this._render_win_start = 0;
        this._render_win_end = 0;
    },

    update_render_window: function (selected_idx, check_for_changed) {
        var new_start = Math.max(selected_idx - this._RENDER_WINDOW_SIZE / 2, 0);
        if (check_for_changed && new_start === this._render_win_start) {
            return false;
        }

        this._render_win_start = new_start;
        this._render_win_end = Math.min(this._render_win_start + this._RENDER_WINDOW_SIZE,
                                        this.list.num_items());
        return true;
    },


    maybe_rerender: function () {
        if (this.table_name === undefined) {
            return false;
        }

        var selected_idx = this.list.selected_idx();

        // We rerender under the following conditions:
        // * The selected message is within this._RENDER_THRESHOLD messages
        //   of the top of the currently rendered window and the top
        //   of the window does not abut the beginning of the message
        //   list
        // * The selected message is within this._RENDER_THRESHOLD messages
        //   of the bottom of the currently rendered window and the
        //   bottom of the window does not abut the end of the
        //   message list
        if (!(selected_idx - this._render_win_start < this._RENDER_THRESHOLD
                && this._render_win_start !== 0 ||
               this._render_win_end - selected_idx <= this._RENDER_THRESHOLD
                && this._render_win_end !== this.list.num_items())) {
            return false;
        }

        if (!this.update_render_window(selected_idx, true)) {
            return false;
        }

        this.rerender_preserving_scrolltop();
        return true;
    },

    rerender_preserving_scrolltop: function () {
        // old_offset is the number of pixels between the top of the
        // viewable window and the selected message
        var old_offset;
        var selected_row = this.selected_row();
        var selected_in_view = selected_row.length > 0;
        if (selected_in_view) {
            old_offset = selected_row.offset().top;
        }
        return this.rerender_with_target_scrolltop(selected_row, old_offset);
    },

    set_message_offset: function (offset) {
        var msg = this.selected_row();
        message_viewport.scrollTop(message_viewport.scrollTop() + msg.offset().top - offset);
    },

    rerender_with_target_scrolltop: function (selected_row, target_offset) {
        // target_offset is the target number of pixels between the top of the
        // viewable window and the selected message
        this.clear_table();
        this.render(this.list.all_messages().slice(this._render_win_start,
                                                   this._render_win_end), 'bottom');

        // If we could see the newly selected message, scroll the
        // window such that the newly selected message is at the
        // same location as it would have been before we
        // re-rendered.
        if (target_offset !== undefined) {
            if (this.selected_row().length === 0 && this.list.selected_id() > -1) {
                this.list.select_id(this.list.selected_id(), {use_closest: true});
            }

            this.set_message_offset(target_offset);
        }
    },

    _rerender_header: function (message_containers) {
        // Given a list of messages that are in the **same** message group,
        // rerender the header / recipient bar of the messages
        if (message_containers.length === 0) {
            return;
        }

        var first_row = this.get_row(message_containers[0].msg.id);

        // We may not have the row if the stream or topic was muted
        if (first_row.length === 0) {
            return;
        }

        var recipient_row = rows.get_message_recipient_row(first_row);
        var header = recipient_row.find('.message_header');

        var group = {message_containers: message_containers};
        populate_group_from_message_container(group, message_containers[0]);

        var rendered_recipient_row = $(templates.render('recipient_row', group));

        header.replaceWith(rendered_recipient_row);
    },

    _rerender_message: function (message_container, message_content_edited) {
        var row = this.get_row(message_container.msg.id);
        var was_selected = this.list.selected_message() === message_container.msg;

        // Re-render just this one message
        this._add_msg_timestring(message_container);
        this._maybe_format_me_message(message_container);

        // Make sure the right thing happens if the message was edited to mention us.
        message_container.contains_mention = message_container.msg.mentioned;

        var rendered_msg = $(this._get_message_template(message_container));
        if (message_content_edited) {
            rendered_msg.addClass("fade-in-message");
        }
        this._post_process(rendered_msg);
        row.replaceWith(rendered_msg);

        if (was_selected) {
            this.list.select_id(message_container.msg.id);
        }
    },

    rerender_messages: function (messages, message_content_edited) {
        var self = this;

        // Convert messages to list messages
        var message_containers = _.map(messages, function (message) {
            return self.message_containers[message.id];
        });
        // We may not have the message_container if the stream or topic was muted
        message_containers = _.reject(message_containers, function (message_container) {
            return message_container === undefined;
        });

        var message_groups = [];
        var current_group = [];
        _.each(message_containers, function (message_container) {
            if (current_group.length === 0 ||
                same_recipient(current_group[current_group.length - 1], message_container)) {
                current_group.push(message_container);
            } else {
                message_groups.push(current_group);
                current_group = [];
            }
            self._rerender_message(message_container, message_content_edited);
        });
        if (current_group.length !== 0) {
            message_groups.push(current_group);
        }
        _.each(message_groups, function (messages_in_group) {
            self._rerender_header(messages_in_group, message_content_edited);
        });
    },

    append: function (messages, messages_are_new) {
        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var slice_to_render = messages.slice(0, this._RENDER_WINDOW_SIZE - cur_window_size);
            this.render(slice_to_render, 'bottom', messages_are_new);
            this._render_win_end += slice_to_render.length;
        }

        // If the pointer is high on the page such that there is a
        // lot of empty space below and the render window is full, a
        // newly received message should trigger a rerender so that
        // the new message, which will appear in the viewable area,
        // is rendered.
        this.maybe_rerender();
    },

    prepend: function (messages) {
        this._render_win_start += messages.length;
        this._render_win_end += messages.length;

        var cur_window_size = this._render_win_end - this._render_win_start;
        if (cur_window_size < this._RENDER_WINDOW_SIZE) {
            var msgs_to_render_count = this._RENDER_WINDOW_SIZE - cur_window_size;
            var slice_to_render = messages.slice(messages.length - msgs_to_render_count);
            this.render(slice_to_render, 'top', false);
            this._render_win_start -= slice_to_render.length;
        }

        // See comment for maybe_rerender call in the append code path
        this.maybe_rerender();
    },

    rerender_the_whole_thing: function () {
        // TODO: Figure out if we can unify this with this.list.rerender().
        this.clear_rendering_state(true);
        this.update_render_window(this.list.selected_idx(), false);
        this.render(this.list.all_messages().slice(this._render_win_start, this._render_win_end), 'bottom');
    },

    clear_table: function () {
        // We do not want to call .empty() because that also clears
        // jQuery data.  This does mean, however, that we need to be
        // mindful of memory leaks.
        rows.get_table(this.table_name).children().detach();
        this._rows = {};
        this._message_groups = [];
        this.message_containers = {};
    },

    get_row: function (id) {
        var row = this._rows[id];

        if (row === undefined) {
            // For legacy reasons we need to return an empty
            // jQuery object here.
            return $(undefined);
        }

        return row;
    },

    clear_trailing_bookend: function () {
        var trailing_bookend = rows.get_table(this.table_name).find('.trailing_bookend');
        trailing_bookend.remove();
    },

    render_trailing_bookend: function (trailing_bookend_content, subscribed, show_button) {
        var rendered_trailing_bookend = $(templates.render('bookend', {
            bookend_content: trailing_bookend_content,
            trailing: show_button,
            subscribed: subscribed,
        }));
        rows.get_table(this.table_name).append(rendered_trailing_bookend);
    },

    selected_row: function () {
        return this.get_row(this.list.selected_id());
    },

    get_message: function (id) {
        return this.list.get(id);
    },

    change_message_id: function (old_id, new_id) {
        if (this._rows[old_id] !== undefined) {
            var row = this._rows[old_id];
            delete this._rows[old_id];

            row.attr('zid', new_id);
            row.attr('id', this.table_name + new_id);
            row.removeClass('local');
            this._rows[new_id] = row;
        }

        if (this.message_containers[old_id] !== undefined) {
            var message_container = this.message_containers[old_id];
            delete this.message_containers[old_id];
            this.message_containers[new_id] = message_container;
        }

    },

    _maybe_format_me_message: function (message_container) {
        if (message_container.msg.is_me_message) {
            // Slice the '<p>/me ' off the front, and '</p>' off the end
            message_container.status_message = message_container.msg.content.slice(4 + 3, -4);
            message_container.include_sender = true;
        } else {
            message_container.status_message = false;
        }
    },
};

}());

if (typeof module !== 'undefined') {
    module.exports = MessageListView;
}
window.MessageListView = MessageListView;
