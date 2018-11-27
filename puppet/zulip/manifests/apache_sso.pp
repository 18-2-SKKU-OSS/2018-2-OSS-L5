class zulip::apache_sso {
  include zulip::localhost_sso

  $apache_packages = [ 'apache2', 'libapache2-mod-wsgi-py3', ]
  package { $apache_packages: ensure => 'installed' }

  $apache_former_packages = [ 'libapache2-mod-wsgi', ]
  package { $apache_former_packages: ensure => 'absent' }

  apache2mod { [ 'headers', 'proxy', 'proxy_http', 'rewrite', 'ssl', 'wsgi', ]:
    ensure  => present,
    require => Package['apache2'],
  }

  file { '/etc/apache2/ports.conf':
    ensure  => file,
    require => Package[apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    source  => 'puppet:///modules/zulip/apache/ports.conf',
  }

  file { '/etc/apache2/sites-available/':
    recurse => true,
    require => Package[apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    source  => 'puppet:///modules/zulip/apache/sites/',
  }

}
