class zulip::supervisor {
  $supervisor_packages = [# Needed to run supervisor
                          'supervisor',
                          ]
  package { $supervisor_packages: ensure => 'installed' }
  # In the dockervoyager environment, we don't want/need supervisor to be started/stopped
  # /bin/true is used as a decoy command, to maintain compatibility with other
  # code using the supervisor service.
  #
  # This logic is definitely a hack, but it's less bad than the old hack :(
  $puppet_classes = zulipconf('machine', 'puppet_classes', undef)
  if $puppet_classes == 'zulip::dockervoyager' {
    service { 'supervisor':
      ensure     => running,
      require    => [
        File['/var/log/zulip'],
        Package['supervisor'],
      ],
      hasstatus  => true,
      status     => '/bin/true',
      hasrestart => true,
      restart    => '/bin/true'
    }
  } else {
    service { 'supervisor':
      ensure     => running,
      require    => [
        File['/var/log/zulip'],
        Package['supervisor'],
      ],
      hasstatus  => true,
      status     => 'supervisorctl status',
      # The "restart" option in the init script does not work.  We could
      # tell Puppet to fall back to stop/start, which does work, but the
      # better option is to tell supervisord to reread its config via
      # supervisorctl and then to "update".  You need to do both --
      # after a "reread", supervisor won't actually take actual based on
      # the changed configuration until you do an "update" (I assume
      # this is so you can check if your config file parses without
      # doing anything, but it's really confusing)
      #
      # Also, to handle the case that supervisord wasn't running at all,
      # we check if it is not running and if so, start it.
      #
      # We use supervisor[d] as the pattern so the bash/grep commands don't match.
      hasrestart => true,
      # lint:ignore:140chars
      restart    => 'bash -c "if pgrep -f supervisor[d] >/dev/null; then supervisorctl reread && supervisorctl update; else /etc/init.d/supervisor start; fi"'
      # lint:endignore
    }
  }

  file { '/etc/supervisor/supervisord.conf':
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/supervisord.conf',
    notify  => Service['supervisor'],
  }

  if $zulip::base::release_name == 'xenial' {
    exec {'enable supervisor':
      unless  => 'systemctl is-enabled supervisor',
      command => 'systemctl enable supervisor',
      require => Package['supervisor'],
    }
  }
}
