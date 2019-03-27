# Copyright 2016 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license

from __future__ import absolute_import

import glob
import os
from six.moves import configparser


CONFIG_FILE = '/etc/ovirt-provider-ovn/ovirt-provider-ovn.conf'
CONFD_DIR = '/etc/ovirt-provider-ovn/conf.d'
CONFD_FILES = '*.conf'

CONFIG_SECTION_OVN_REMOTE = 'OVN REMOTE'
KEY_OVN_REMOTE = 'ovn-remote'
DEFAULT_OVN_REMOTE_AT_LOCALHOST = 'tcp:127.0.0.1:6641'

CONFIG_SECTION_PROVIDER = 'PROVIDER'
KEY_NOVA_PORT = 'nova-port'
KEY_NEUTRON_PORT = 'neutron-port'
KEY_KEYSTONE_PORT = 'keystone-port'
KEY_PROVIDER_HOST = 'provider-host'
KEY_OPENSTACK_REGION = 'openstack-region'
KEY_OPENSTACK_NEUTRON_ID = 'openstack-neutron-id'
KEY_OPENSTACK_KEYSTONE_ID = 'openstack-keystone-id'
KEY_OPENSTACK_TENANT_ID = 'openstack-tenant-id'
KEY_OPENSTACK_TENANT_NAME = 'openstack-tenant-name'
KEY_OPENSTACK_TENANT_DESCRIPTION = 'openstack-tenant-description'
KEY_OVS_VERSION_29 = 'ovs-version-2.9'
KEY_URL_FILTER_EXCEPTION = 'url_filter_exception'

DEFAULT_NOVA_PORT = 9696
DEFAULT_NEUTRON_PORT = 9696
DEFAULT_KEYSTONE_PORT = 35357
DEFAULT_PROVIDER_HOST = 'localhost'
DEFAULT_OPENSTACK_REGION = 'RegionOne'
DEFAULT_OPENSTACK_NEUTRON_ID = '00000000000000000000000000000001'
DEFAULT_OPENSTACK_KEYSTONE_ID = '00000000000000000000000000000002'
DEFAULT_OPENSTACK_TENANT_ID = '00000000000000000000000000000001'
DEFAULT_OPENSTACK_TENANT_NAME = 'tenant'
DEFAULT_OPENSTACK_TENANT_DESCRIPTION = 'tenant'
DEFAULT_OVS_VERSION_29 = False
DEFAULT_URL_FILTER_EXCEPTION = ''


CONFIG_SECTION_SSL = 'SSL'
KEY_HTTPS_ENABLED = 'https-enabled'
KEY_SSL_KEY_FILE = 'ssl-key-file'
KEY_SSL_CERT_FILE = 'ssl-cert-file'
KEY_SSL_CACERT_FILE = 'ssl-cacert-file'
KEY_SSL_CIPHERS_STRING = 'ssl-ciphers-string'

DEFAULT_SSL_KEY_FILE = '/etc/pki/ovirt-engine/keys/ovirt-provider-ovn.pem'
DEFAULT_SSL_CERT_FILE = '/etc/pki/ovirt-engine/certs/ovirt-provider-ovn.cer'
DEFAULT_SSL_CACERT_FILE = '/etc/pki/ovirt-engine/ca.pem'
DEFAULT_SSL_CIPHERS_STRING = 'HIGH'
DEFAULT_SSL_ENABLED = False

CONFIG_SECTION_DHCP = 'DHCP'
KEY_DHCP_SERVER_MAC = 'dhcp-server-mac'
KEY_DHCP_LEASE_TIME = 'dhcp-lease-time'
KEY_DHCP_ENABLE_MTU = 'dhcp-enable-mtu'
KEY_DHCP_MTU = 'dhcp-mtu'
KEY_DHCP_DEFAULT_IPV6_ADDRESS_MODE = 'dhcp-default-ipv6-address-mode'

# Locally administered mac for use by OVN to assign to dhcp server
DEFAULT_DHCP_SERVER_MAC = '02:00:00:00:00:00'
# Make the lease time
DEFAULT_DHCP_LEASE_TIME = '86400'
# MTU of tunneld network should be smaller than the MTU of the tunneling net
DEFAULT_DHCP_MTU = '1442'
# Setting MTU by DHCP is enabled by default, until there is a better way to
# set the MTU
DEFAULT_DHCP_ENABLE_MTU = True
DEFAULT_DHCP_DEFAULT_IPV6_ADDRESS_MODE = 'dhcpv6_stateful'

CONFIG_SECTION_AUTH = 'AUTH'
KEY_AUTH_PLUGIN = 'auth-plugin'
DEFAULT_AUTH_PLUGIN = 'auth.plugins.static_token:MagicTokenPlugin'
KEY_AUTH_TOKEN_TIMEOUT = 'auth-token-timeout'
DEFAULT_AUTH_TOKEN_TIMEOUT = 360000

CONFIG_SECTION_NETWORK = 'NETWORK'
KEY_NETWORK_PORT_SECURITY_ENABLED = 'port-security-enabled-default'
DEFAULT_NETWORK_PORT_SECURITY_ENABLED = False

CONFIG_SECTION_OVIRT = 'OVIRT'
KEY_OVIRT_HOST = 'ovirt-host'
KEY_OVIRT_BASE = 'ovirt-base'
KEY_OVIRT_CA_FILE = 'ovirt-ca-file'
KEY_OVIRT_AUTH_TIMEOUT = 'ovirt-auth-timeout'
KEY_OVIRT_SSO_CLIENT_ID = 'ovirt-sso-client-id'
KEY_OVIRT_SSO_CLIENT_SECRET = 'ovirt-sso-client-secret'
KEY_OVIRT_ADMIN_USER_NAME = 'ovirt-admin-user-name'
KEY_OVIRT_ADMIN_ROLE_ID = 'ovirt-admin-role-id'
KEY_OVIRT_ADMIN_GROUP_ATTRIBUTE_NAME = 'ovirt-admin-group-attribute-name'
KEY_OVIRT_ADMIN_GROUP_ATTRIBUTE_VALUE = 'ovirt-admin-group-attribute-value'

DEFAULT_OVIRT_HOST = 'https://localhost'
DEFAULT_OVIRT_BASE = '/ovirt-engine'
DEFAULT_OVIRT_CA_FILE = '/etc/pki/ovirt-engine/ca.pem'
DEFAULT_OVIRT_SSO_CLIENT_ID = 'ovirt-engine-core'
DEFAULT_OVIRT_SSO_CLIENT_SECRET = 'secret'
DEFAULT_OVIRT_AUTH_TIMEOUT = 110.0
DEFAULT_ENGINE_NETWORK_ADMIN_USER_NAME = 'netadmin@internal'
DEFAULT_ENGINE_NETWORK_ADMIN_ROLE_ID = 'def00005-0000-0000-0000-def000000005'
DEFAULT_ENGINE_ADMIN_GROUP_ATTRIBUTE_NAME = \
  'AAA_AUTHZ_GROUP_NAME;java.lang.String;0eebe54f-b429-44f3-aa80-4704cbb16835'
DEFAULT_ENGINE_ADMIN_GROUP_ATTRIBUTE_VALUE = 'NetAdmin'

CONFIG_SECTION_VALIDATION = 'VALIDATION'
KEY_VALIDATION_MAX_ALLOWED_MTU = 'validation-max-allowed-mtu'

DEFAULT_VALIDATION_MAX_ALLOWED_MTU = 0


DEFAULT_KEY_FILE = '/etc/pki/ovirt-engine/keys/ovirt-provider-ovn.pem'
DEFAULT_CERT_FILE = '/etc/pki/ovirt-engine/certs/ovirt-provider-ovn.cer'
DEFAULT_CACERT_FILE = '/etc/pki/ovirt-engine/ca.pem'
PROTOCOL_SSL = 'ssl'


_config = None


def load():
    global _config
    _config = configparser.ConfigParser()
    _config.read(CONFIG_FILE)
    _config.read(
        sorted(
            glob.glob(
                os.path.join(CONFD_DIR, CONFD_FILES)
            )
        )
    )


def get(section, key, default=None):
    global _config
    try:
        return _config.get(section, key) if _config else default
    except (configparser.NoOptionError, configparser.NoSectionError):
        return default


def getboolean(section, key, default=None):
    global _config
    try:
        return _config.getboolean(section, key) if _config else default
    except (configparser.NoOptionError, configparser.NoSectionError):
        return default


def getfloat(section, key, default=None):
    global _config
    try:
        return _config.getfloat(section, key) if _config else default
    except (configparser.NoOptionError, configparser.NoSectionError):
        return default


def getint(section, key, default=None):
    global _config
    try:
        return _config.getint(section, key) if _config else default
    except (configparser.NoOptionError, configparser.NoSectionError):
        return default
