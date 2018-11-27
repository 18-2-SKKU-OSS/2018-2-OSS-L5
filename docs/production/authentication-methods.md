# Authentication methods

Zulip supports a wide variety of authentication methods.  Some of them
require configuration to set up.

To configure or disable authentication methods on your Zulip server,
edit the `AUTHENTICATION_BACKENDS` setting in
`/etc/zulip/settings.py`, as well as any additional configuration your
chosen authentication methods require; then restart the Zulip server.

Details on each method below.

## Email and password

The `EmailAuthBackend` method is the one method enabled by default,
and it requires no additional configuration.

Users set a password with the Zulip server, and log in with their
email and password.

When first setting up your Zulip server, this method must be used for
creating the initial realm and user.  You can disable it after that.

## Plug-and-play SSO (Google, GitHub)

With just a few lines of configuration, your Zulip server can
authenticate users with any of several single-sign-on (SSO)
authentication providers:
* Google accounts, with `GoogleMobileOauth2Backend`
* GitHub accounts, with `GitHubAuthBackend`

Each of these requires one to a handful of lines of configuration in
`settings.py`, as well as a secret in `zulip-secrets.conf`.  Details
are documented in your `settings.py`.

```eval_rst
.. _ldap:
```
## LDAP (including Active Directory)

Zulip supports retrieving information about users via LDAP, and
optionally using LDAP as an authentication mechanism.

In either configuration, you will need to do the following:

1. Create your organization and first administrator account using
   another authentication backend (usually `EmailAuthBackend`).  LDAP
   authentication does not support organization creation at this time;
   but you can disable `EmailAuthBackend` once you have created the
   organization.

2. Tell Zulip how to connect to your LDAP server:
   * Fill out the section of your `/etc/zulip/settings.py` headed "LDAP
     integration, part 1: Connecting to the LDAP server".
   * If a password is required, put it in
     `/etc/zulip/zulip-secrets.conf` by setting
     `auth_ldap_bind_password`.  For example: `auth_ldap_bind_password
     = abcd1234`.

3. Decide how you want to map the information in your LDAP database to
   users' account data in Zulip.  For each Zulip user, two closely
   related concepts are:
   * their **email address**.  Zulip needs this in order to send, for
     example, a notification when they're offline and another user
     sends a PM.
   * their **Zulip username**.  This means the name the user types into the
     Zulip login form.  You might choose for this to be the user's
     email address (`sam@example.com`), or look like a traditional
     "username" (`sam`), or be something else entirely, depending on
     your environment.

   Either or both of these might be an attribute of the user records
   in your LDAP database.

4. Tell Zulip how to map the user information in your LDAP database to
   the form it needs.  There are three supported ways to set up the
   username and/or email mapping:

   (A) Using email addresses as usernames, if LDAP has each user's
      email address.  To do this, just set `AUTH_LDAP_USER_SEARCH` to
      query by email address.

   (B) Using LDAP usernames as Zulip usernames, with email addresses
      formed consistently like `sam` -> `sam@example.com`.  To do
      this, set `AUTH_LDAP_USER_SEARCH` to query by LDAP username, and
      `LDAP_APPEND_DOMAIN = "example.com"`.

   (C) Using LDAP usernames as Zulip usernames, with email addresses
      taken from some other attribute in LDAP (for example, `email`).
      To do this, set `AUTH_LDAP_USER_SEARCH` to query by LDAP
      username, and `LDAP_EMAIL_ATTR = "email"`.

You can quickly test whether your configuration works by running:

```
  ./manage.py query_ldap username
```

from the root of your Zulip installation.  If your configuration is
working, that will output the full name for your user (and that user's
email address, if it isn't the same as the "Zulip username").

**If you are using LDAP for authentication**: you will need to enable
the `zproject.backends.ZulipLDAPAuthBackend` auth backend, in
`AUTHENTICATION_BACKENDS` in `/etc/zulip/settings.py`.  After doing
so (and as always [restarting the Zulip server](settings.html) to ensure
your settings changes take effect), you should be able to log into
Zulip by entering your email address and LDAP password on the Zulip
login form.

**If you are using LDAP to populate names in Zulip**: once you finish
configuring this integration, you will need to run:
```
  ./manage.py sync_ldap_user_data
```
to sync names for existing users.  You may want to run this in a cron
job to pick up name changes made on your LDAP server.

### Multiple LDAP searches

To do the union of multiple LDAP searches, use `LDAPSearchUnion`.  For example:
```
AUTH_LDAP_USER_SEARCH = LDAPSearchUnion(
    LDAPSearch("ou=users,dc=example,dc=com", ldap.SCOPE_SUBTREE, "(uid=%(user)s)"),
    LDAPSearch("ou=otherusers,dc=example,dc=com", ldap.SCOPE_SUBTREE, "(uid=%(user)s)"),
)
```

## Apache-based SSO with `REMOTE_USER`

If you have any existing SSO solution where a preferred way to deploy
it (a) runs inside Apache, and (b) sets the `REMOTE_USER` environment
variable, then the `ZulipRemoteUserBackend` method provides you with a
straightforward way to deploy that SSO solution with Zulip.

### Setup instructions for Apache-based SSO

1. In `/etc/zulip/settings.py`, configure two settings:

   * `AUTHENTICATION_BACKENDS`: `'zproject.backends.ZulipRemoteUserBackend'`,
     and no other entries.

   * `SSO_APPEND_DOMAIN`: see documentation in `settings.py`.

   Make sure that you've restarted the Zulip server since making this
   configuration change.

2. Edit `/etc/zulip/zulip.conf` and change the `puppet_classes` line to read:

   ```
   puppet_classes = zulip::voyager, zulip::apache_sso
   ```

3. As root, run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`
   to install our SSO integration.

4. To configure our SSO integration, edit a copy of
   `/etc/apache2/sites-available/zulip-sso.example`, saving the result
   as `/etc/apache2/sites-available/zulip-sso.conf`.  The example sets
   up HTTP basic auth, with an `htpasswd` file; you'll want to replace
   that with configuration for your SSO solution to authenticate the
   user and set `REMOTE_USER`.

   For testing, you may want to move ahead with the rest of the setup
   using the `htpasswd` example configuration and demonstrate that
   working end-to-end, before returning later to configure your SSO
   solution.  You can do that with the following steps:
   ```
   /home/zulip/deployments/current/scripts/restart-server
   cd /etc/apache2/sites-available/
   cp zulip-sso.example zulip-sso.conf
   htpasswd -c /home/zulip/zpasswd username@example.com # prompts for a password
   ```

5. Run `a2ensite zulip-sso` to enable the SSO integration within Apache.

6. Run `service apache2 reload` to use your new configuration.  If
   Apache isn't already running, you may need to run `service apache2
   start` instead.

Now you should be able to visit your Zulip server in a browser (e.g.,
at `https://zulip.example.com/`) and log in via the SSO solution.

### Troubleshooting Apache-based SSO

Most issues with this setup tend to be subtle issues with the
hostname/DNS side of the configuration.  Suggestions for how to
improve this SSO setup documentation are very welcome!

* For example, common issues have to do with `/etc/hosts` not mapping
  `settings.EXTERNAL_HOST` to the Apache listening on
  `127.0.0.1`/`localhost`.

* While debugging, it can often help to temporarily change the Apache
  config in `/etc/apache2/sites-available/zulip-sso` to listen on all
  interfaces rather than just `127.0.0.1`.

* While debugging, it can also be helpful to change `proxy_pass` in
  `/etc/nginx/zulip-include/app.d/external-sso.conf` to point to a
  more explicit URL, possibly not over HTTPS.

* The following log files can be helpful when debugging this setup:

   * `/var/log/zulip/{errors.log,server.log}` (the usual places)
   * `/var/log/nginx/access.log` (nginx access logs)
   * `/var/log/apache2/zulip_auth_access.log` (from the
     `zulip-sso.conf` Apache config file; you may want to change
     `LogLevel` in that file to "debug" to make this more verbose)

### Life of an Apache-based SSO login attempt

Here's a summary of how the Apache `REMOTE_USER` SSO system works,
assuming you're using the example configuration with HTTP basic auth.
This summary should help with understanding what's going on as you try
to debug.

* Since you've configured `/etc/zulip/settings.py` to only define the
  `zproject.backends.ZulipRemoteUserBackend`, `zproject/settings.py`
  configures `/accounts/login/sso` as `HOME_NOT_LOGGED_IN`.  This
  makes `https://zulip.example.com/` (a.k.a. the homepage for the main
  Zulip Django app running behind nginx) redirect to
  `/accounts/login/sso` for a user that isn't logged in.

* nginx proxies requests to `/accounts/login/sso/` to an Apache
  instance listening on `localhost:8888`, via the config in
  `/etc/nginx/zulip-include/app.d/external-sso.conf` (using the
  upstream `localhost_sso`, defined in `/etc/nginx/zulip-include/upstreams`).

* The Apache `zulip-sso` site which you've enabled listens on
  `localhost:8888` and (in the example config) presents the `htpasswd`
  dialogue.  (In a real configuration, it takes the user through
  whatever more complex interaction your SSO solution performs.)  The
  user provides correct login information, and the request reaches a
  second Zulip Django app instance, running behind Apache, with
  `REMOTE_USER` set.  That request is served by
  `zerver.views.remote_user_sso`, which just checks the `REMOTE_USER`
  variable and either logs the user in or, if they don't have an
  account already, registers them.  The login sets a cookie.

* After succeeding, that redirects the user back to `/` on port 443.
  This request is sent by nginx to the main Zulip Django app, which
  sees the cookie, treats them as logged in, and proceeds to serve
  them the main app page normally.

## Adding more authentication backends

Adding an integration with another authentication provider (e.g.,
Facebook, Twitter, etc.) is easy to do if you're willing to write a
bit of code, and pull requests to add new backends are welcome.

To write such an integration, look in `zproject/backends.py` at the
implementation of `GitHubAuthBackend`, which is a small wrapper around
the popular [python-social-auth] library.  You can write a similar
class, and add a few settings to control it.  To test your backend
(which we'd require for a pull request to the main Zulip codebase,)
see the framework in `test_auth_backends.py`.

[python-social-auth]: https://python-social-auth.readthedocs.io/en/latest/

## Development only

The `DevAuthBackend` method is used only in development, to allow
passwordless login as any user in a development environment.  It's
mentioned on this page only for completeness.
