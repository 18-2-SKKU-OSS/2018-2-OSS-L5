Zulip’s security strategy covers all aspects of our product and
business. Making sure your information stays protected is our highest
priority.

## Security basics

- All Zulip clients (web, mobile, desktop, terminal, and integrations)
  require TLS encryption and authentication over HTTPS for all data
  transmission between clients and the server, both on LAN and the Internet.
  Encryption-at-rest is available with Zulip on-premise, via hardware and
  software disk encryption of the database and other data storage media.
- Zulip’s on-premise offerings can be hosted entirely behind your firewall,
  or even on an air-gapped network (disconnected from the Internet).
- Every Zulip authenticated API endpoint has built in rate limiting to
  prevent DoS attacks.
- Connections from the Zulip servers to Active Directory/LDAP can be secured
  with TLS.  If Zulip is
  [deployed on multiple servers](https://zulip.readthedocs.io/en/latest/production/deployment.html),
  all connections between parts of the Zulip infrastructure can be secured
  with TLS or SSH.
- Message content can be
  [excluded from mobile push notifications][redact-content],
  to avoid displaying message content on locked mobile screens, and to
  comply with strict compliance policies such as the USA’s HIPAA standards.
- Zulip operates a HackerOne bug bounty program to reward hackers for
  finding and responsibly reporting security vulnerabilities in Zulip.  Our
  [completely open source codebase](https://github.com/zulip/zulip) means
  that HackerOne’s white-hat hackers can audit Zulip for potential security
  issues with full access to the source code.

[redact-content]: https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#security-and-privacy

## Configurable access control policies

- Zulip supports private messages (to one or more individuals), private
  streams with any number of subscribers, as well as public streams
  available to all organization members.  We also support guest accounts,
  which only have access to a fixed set of streams, and announcement
  streams, where only organization administrators can post.
- By default, users can maintain their own names and email addresses, but
  Zulip also supports
  [restricting changes](/help/restrict-name-and-email-changes) and
  synchronizing these data from another database (such as
  [LDAP/Active Directory][ldap-name]).
- Zulip provides many options for
  [managing who can join the organization](/help/manage-who-can-join-and-invite),
  supporting everything from open to the public (e.g. for open source
  projects), to requiring an invitation to join, to having an email from a
  list of domains, to being a member of a specific organization in
  LDAP/Active Directory.
- Zulip also supports customizing whether non-admins can
  [create streams](/help/configure-who-can-create-streams),
  [add custom emoji](/help/only-allow-admins-to-add-emoji),
  [add integrations and bots](/help/restrict-bot-creation),
  [edit or delete messages](/help/configure-message-editing-and-deletion),
  and more.

[ldap-name]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap-including-active-directory

## Authentication

- Zulip supports integrated single sign-on with Google, GitHub, and Active
  Directory/LDAP. SAML and Okta authentication are coming soon. With Zulip
  on-premise, we can support any of the 100+ authentication tools supported
  by
  [python-social-auth](https://python-social-auth-docs.readthedocs.io/en/latest/backends/index.html#social-backends)
  as well as
  [any SSO service that has a plugin for Apache][apache-sso].
- Zulip uses the zxcvbn password strength checker by default, and supports
  customizing users’ password strength requirements. See our documentation
  on
  [password strength](https://zulip.readthedocs.io/en/latest/production/security-model.html#passwords)
  for more detail.
- Users can rotate their accounts’ credentials, blocking further access from
  any compromised Zulip credentials.  With Zulip on-premise, server
  administrators can additionally revoke and reset any user’s credentials.
- Administrators can deactivate any
  [user](/help/deactivate-or-reactivate-a-user),
  [bot, or integration](/help/deactivate-or-reactivate-a-bot).
- With Zulip on-premise,
  [session length](https://github.com/zulip/zulip/blob/master/zproject/prod_settings_template.py#L206)
  and idle timeouts can be configured to match your organization’s security
  policies.

[apache-sso]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#apache-based-sso-with-remote-user

## Integrity and auditing

- Zulip administrators can configure users’
  [ability to edit or delete messages](/help/configure-message-editing-and-deletion),
  and whether deleted messages are retained in the database or deleted
  permanently. Zulip by default stores the complete history of all message
  content on the platform, including edits and deletions, and all uploaded
  files.
- Zulip’s server logging has configurable log rotation policies and can be
  used for an end-to-end history of system usage.
- Zulip stores in its database a permanent long-term audit log containing
  the history of important actions (e.g. changes to passwords, email
  addresses, and stream subscriptions).
- Zulip’s powerful data exports
  ([on-premise](https://zulip.readthedocs.io/en/latest/production/export-and-import.html),
  [cloud](/help/export-your-organization)) can be imported into third-party
  tools for legal discovery and other compliance purposes.  Zulip’s
  enterprise offerings include support for integrating these with your
  compliance tools.
- Zulip supports GDPR and HIPAA compliance.


## The little things

Many products talk about having great security and privacy practices, but
fall short in actually protecting their users due to buggy code or poor
operational practices.

Our focus on security goes beyond a feature checklist: it’s a point of
pride. Zulip founder Tim Abbott was previously the CTO of Ksplice, which
provided rebootless Linux kernel security updates for over 100,000
production servers (now the flagship feature of
[Oracle Linux](https://www.oracle.com/linux/)).

Here are some security practices we’re proud of, all of which are unusual in
the industry:

- The Zulip server’s automated test suite has over 98% test coverage,
  including 100% of Zulip’s API layer (responsible for parsing user input).
  It is difficult to find any full-stack web application with as complete a
  set of automated tests as Zulip.
- Zulip’s python codebase is written entirely in
  [statically typed Python 3](https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/),
  which automatically prevents a wide range of possible bugs.
- All access to user data (messages, streams, uploaded files, etc.) in the
  Zulip backend is through carefully-audited core libraries that validate
  that the user who is making the request has access to that data.
- Only a small handful of people have access to production servers or
  to sensitive customer data.
- Our error handling systems are have been designed from the beginning to
  avoid including user message content in error reports, even in cases where
  this makes debugging quite difficult (e.g. bugs in the message rendering
  codebase).
- Zulip has a carefully designed API surface area of only about 100 API
  endpoints. For comparison, products of similar scope typically have
  hundreds or even thousands of endpoints. Every new API endpoint is
  personally reviewed for security and necessity by the system architect Tim
  Abbott.

These security practices matter!  Slack, the most popular SaaS team chat
provider, has needed to award
[hundreds of bounties](https://hackerone.com/slack) for security bugs found
by security researchers outside the company. This incredible number of
discovered vulnerabilities likely results from Slack not following secure
development practices (e.g. Slack uses a
[famously insecure](https://www.quora.com/Why-is-PHP-hated-by-so-many-developers/answer/Anders-Kaseorg)
programming language as the core language for their product).

## Further reading

- Detailed
  [security model documentation](https://zulip.readthedocs.io/en/latest/production/security-model.html)
