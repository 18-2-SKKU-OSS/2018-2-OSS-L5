
import ujson

from django.http import HttpResponse
from django.test import override_settings
from mock import patch
from typing import Any, Dict

from zerver.lib.initial_password import initial_password
from zerver.lib.sessions import get_session_dict_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import MockLDAP
from zerver.lib.users import get_all_api_keys
from zerver.models import get_realm, get_user, UserProfile

class ChangeSettingsTest(ZulipTestCase):

    def check_well_formed_change_settings_response(self, result: Dict[str, Any]) -> None:
        self.assertIn("full_name", result)

    # DEPRECATED, to be deleted after all uses of check_for_toggle_param
    # are converted into check_for_toggle_param_patch.
    def check_for_toggle_param(self, pattern: str, param: str) -> None:
        self.login(self.example_email("hamlet"))
        user_profile = self.example_user('hamlet')
        json_result = self.client_post(pattern,
                                       {param: ujson.dumps(True)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = self.example_user('hamlet')
        self.assertEqual(getattr(user_profile, param), True)

        json_result = self.client_post(pattern,
                                       {param: ujson.dumps(False)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = self.example_user('hamlet')
        self.assertEqual(getattr(user_profile, param), False)

    # TODO: requires method consolidation, right now, there's no alternative
    # for check_for_toggle_param for PATCH.
    def check_for_toggle_param_patch(self, pattern: str, param: str) -> None:
        self.login(self.example_email("hamlet"))
        user_profile = self.example_user('hamlet')
        json_result = self.client_patch(pattern,
                                        {param: ujson.dumps(True)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = self.example_user('hamlet')
        self.assertEqual(getattr(user_profile, param), True)

        json_result = self.client_patch(pattern,
                                        {param: ujson.dumps(False)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = self.example_user('hamlet')
        self.assertEqual(getattr(user_profile, param), False)

    def test_successful_change_settings(self) -> None:
        """
        A call to /json/settings with valid parameters changes the user's
        settings correctly and returns correct values.
        """
        self.login(self.example_email("hamlet"))
        json_result = self.client_patch(
            "/json/settings",
            dict(
                full_name='Foo Bar',
                old_password=initial_password(self.example_email("hamlet")),
                new_password='foobar1',
            ))
        self.assert_json_success(json_result)
        result = ujson.loads(json_result.content)
        self.check_well_formed_change_settings_response(result)
        self.assertEqual(self.example_user('hamlet').
                         full_name, "Foo Bar")
        self.logout()
        self.login(self.example_email("hamlet"), "foobar1")
        user_profile = self.example_user('hamlet')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_illegal_name_changes(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        self.login(email)
        full_name = user.full_name

        with self.settings(NAME_CHANGES_DISABLED=True):
            json_result = self.client_patch("/json/settings",
                                            dict(full_name='Foo Bar'))

        # We actually fail silently here, since this only happens if
        # somebody is trying to game our API, and there's no reason to
        # give them the courtesy of an error reason.
        self.assert_json_success(json_result)

        user = self.example_user('hamlet')
        self.assertEqual(user.full_name, full_name)

        # Now try a too-long name
        json_result = self.client_patch("/json/settings",
                                        dict(full_name='x' * 1000))
        self.assert_json_error(json_result, 'Name too long!')

        # Now try a too-short name
        json_result = self.client_patch("/json/settings",
                                        dict(full_name='x'))
        self.assert_json_error(json_result, 'Name too short!')

    def test_illegal_characters_in_name_changes(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)

        # Now try a name with invalid characters
        json_result = self.client_patch("/json/settings",
                                        dict(full_name='Opheli*'))
        self.assert_json_error(json_result, 'Invalid characters in name!')

    def test_change_email_to_disposable_email(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        realm = get_realm("zulip")
        realm.disallow_disposable_email_addresses = True
        realm.emails_restricted_to_domains = False
        realm.save()

        json_result = self.client_patch("/json/settings",
                                        dict(email='hamlet@mailnator.com'))
        self.assert_json_error(json_result, 'Please use your real email address.')

    # This is basically a don't-explode test.
    def test_notify_settings(self) -> None:
        for notification_setting in UserProfile.notification_setting_types:
            self.check_for_toggle_param_patch("/json/settings/notifications",
                                              notification_setting)

    def test_toggling_boolean_user_display_settings(self) -> None:
        """Test updating each boolean setting in UserProfile property_types"""
        boolean_settings = (s for s in UserProfile.property_types if UserProfile.property_types[s] is bool)
        for display_setting in boolean_settings:
            self.check_for_toggle_param_patch("/json/settings/display", display_setting)

    def test_enter_sends_setting(self) -> None:
        self.check_for_toggle_param('/json/users/me/enter-sends', "enter_sends")

    def test_wrong_old_password(self) -> None:
        self.login(self.example_email("hamlet"))
        result = self.client_patch(
            "/json/settings",
            dict(
                old_password='bad_password',
                new_password="ignored",
            ))
        self.assert_json_error(result, "Wrong password!")

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.EmailAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'),
                       AUTH_LDAP_BIND_PASSWORD='',
                       AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com')
    def test_change_password_ldap_backend(self) -> None:
        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}
        ldap_patcher = patch('django_auth_ldap.config.ldap.initialize')
        mock_initialize = ldap_patcher.start()
        mock_ldap = MockLDAP()
        mock_initialize.return_value = mock_ldap

        mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'ldappassword',
                'fn': ['New LDAP fullname']
            }
        }

        self.login(self.example_email("hamlet"))
        with self.settings(LDAP_APPEND_DOMAIN="zulip.com",
                           AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="ignored",
                ))
            self.assert_json_error(result, "Your Zulip password is managed in LDAP")

            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password='ldappassword',
                    new_password="ignored",
                ))
            self.assert_json_error(result, "Your Zulip password is managed in LDAP")

        with self.settings(LDAP_APPEND_DOMAIN="example.com",
                           AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="ignored",
                ))
            self.assert_json_success(result)

        with self.settings(LDAP_APPEND_DOMAIN=None,
                           AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="ignored",
                ))
            self.assert_json_error(result, "Your Zulip password is managed in LDAP")

    def test_changing_nothing_returns_error(self) -> None:
        """
        We need to supply at least one non-empty parameter
        to this API, or it should fail.  (Eventually, we should
        probably use a patch interface for these changes.)
        """
        self.login(self.example_email("hamlet"))
        result = self.client_patch("/json/settings",
                                   dict(old_password='ignored',))
        self.assert_json_error(result, "Please fill out all fields.")

    def do_test_change_user_display_setting(self, setting_name: str) -> None:

        test_changes = dict(
            default_language = 'de',
            emojiset = 'google',
            timezone = 'US/Mountain',
        )  # type: Dict[str, Any]

        email = self.example_email('hamlet')
        self.login(email)
        test_value = test_changes.get(setting_name)
        # Error if a setting in UserProfile.property_types does not have test values
        if test_value is None:
            raise AssertionError('No test created for %s' % (setting_name))
        invalid_value = 'invalid_' + setting_name

        data = {setting_name: ujson.dumps(test_value)}
        result = self.client_patch("/json/settings/display", data)
        self.assert_json_success(result)
        user_profile = self.example_user('hamlet')
        self.assertEqual(getattr(user_profile, setting_name), test_value)

        # Test to make sure invalid settings are not accepted
        # and saved in the db.
        data = {setting_name: ujson.dumps(invalid_value)}
        result = self.client_patch("/json/settings/display", data)
        # the json error for multiple word setting names (ex: default_language)
        # displays as 'Invalid language'. Using setting_name.split('_') to format.
        self.assert_json_error(result, "Invalid %s '%s'" % (setting_name.split('_')[-1],
                                                            invalid_value))
        user_profile = self.example_user('hamlet')
        self.assertNotEqual(getattr(user_profile, setting_name), invalid_value)

    def test_change_user_display_setting(self) -> None:
        """Test updating each non-boolean setting in UserProfile property_types"""
        user_settings = (s for s in UserProfile.property_types if UserProfile.property_types[s] is not bool)
        for setting in user_settings:
            self.do_test_change_user_display_setting(setting)

    def do_change_emojiset(self, emojiset: str) -> HttpResponse:
        email = self.example_email('hamlet')
        self.login(email)
        data = {'emojiset': ujson.dumps(emojiset)}
        result = self.client_patch("/json/settings/display", data)
        return result

    def test_emojiset(self) -> None:
        """Test banned emojisets are not accepted."""
        banned_emojisets = ['apple', 'emojione']
        valid_emojisets = ['google', 'google-blob', 'text', 'twitter']

        for emojiset in banned_emojisets:
            result = self.do_change_emojiset(emojiset)
            self.assert_json_error(result, "Invalid emojiset '%s'" % (emojiset))

        for emojiset in valid_emojisets:
            result = self.do_change_emojiset(emojiset)
            self.assert_json_success(result)


class UserChangesTest(ZulipTestCase):
    def test_update_api_key(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        self.login(email)
        old_api_keys = get_all_api_keys(user)
        result = self.client_post('/json/users/me/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = result.json()['api_key']
        self.assertNotIn(new_api_key, old_api_keys)
        user = self.example_user('hamlet')
        current_api_keys = get_all_api_keys(user)
        self.assertIn(new_api_key, current_api_keys)
