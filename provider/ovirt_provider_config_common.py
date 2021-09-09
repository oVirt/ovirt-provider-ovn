# Copyright 2017-2021 Red Hat, Inc.
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

import ovirt_provider_config
from ovirt_provider_config import CONFIG_SECTION_AUTH
from ovirt_provider_config import CONFIG_SECTION_DHCP
from ovirt_provider_config import CONFIG_SECTION_NETWORK
from ovirt_provider_config import CONFIG_SECTION_OVN_REMOTE
from ovirt_provider_config import CONFIG_SECTION_PROVIDER
from ovirt_provider_config import CONFIG_SECTION_SSL
from ovirt_provider_config import CONFIG_SECTION_VALIDATION
from ovirt_provider_config import DEFAULT_AUTH_PLUGIN
from ovirt_provider_config import DEFAULT_AUTH_TOKEN_TIMEOUT
from ovirt_provider_config import DEFAULT_DHCP_ENABLE_MTU
from ovirt_provider_config import DEFAULT_DHCP_LEASE_TIME
from ovirt_provider_config import DEFAULT_DHCP_MTU
from ovirt_provider_config import DEFAULT_DHCP_DEFAULT_IPV6_ADDRESS_MODE
from ovirt_provider_config import DEFAULT_DHCP_SERVER_MAC
from ovirt_provider_config import DEFAULT_KEYSTONE_PORT
from ovirt_provider_config import DEFAULT_NETWORK_PORT_SECURITY_ENABLED
from ovirt_provider_config import DEFAULT_NEUTRON_PORT
from ovirt_provider_config import DEFAULT_NOVA_PORT
from ovirt_provider_config import DEFAULT_OPENSTACK_KEYSTONE_ID
from ovirt_provider_config import DEFAULT_OPENSTACK_NEUTRON_ID
from ovirt_provider_config import DEFAULT_OPENSTACK_REGION
from ovirt_provider_config import DEFAULT_OPENSTACK_TENANT_DESCRIPTION
from ovirt_provider_config import DEFAULT_OPENSTACK_TENANT_ID
from ovirt_provider_config import DEFAULT_OPENSTACK_TENANT_NAME
from ovirt_provider_config import DEFAULT_OVN_REMOTE_AT_LOCALHOST
from ovirt_provider_config import DEFAULT_OVS_VERSION_29
from ovirt_provider_config import DEFAULT_PROVIDER_HOST
from ovirt_provider_config import DEFAULT_SSL_CERT_FILE
from ovirt_provider_config import DEFAULT_SSL_CIPHERS_STRING
from ovirt_provider_config import DEFAULT_SSL_ENABLED
from ovirt_provider_config import DEFAULT_SSL_KEY_FILE
from ovirt_provider_config import DEFAULT_URL_FILTER_EXCEPTION
from ovirt_provider_config import DEFAULT_VALIDATION_MAX_ALLOWED_MTU
from ovirt_provider_config import KEY_AUTH_PLUGIN
from ovirt_provider_config import KEY_AUTH_TOKEN_TIMEOUT
from ovirt_provider_config import KEY_DHCP_DEFAULT_IPV6_ADDRESS_MODE
from ovirt_provider_config import KEY_DHCP_ENABLE_MTU
from ovirt_provider_config import KEY_DHCP_LEASE_TIME
from ovirt_provider_config import KEY_DHCP_MTU
from ovirt_provider_config import KEY_DHCP_SERVER_MAC
from ovirt_provider_config import KEY_HTTPS_ENABLED
from ovirt_provider_config import KEY_KEYSTONE_PORT
from ovirt_provider_config import KEY_NETWORK_PORT_SECURITY_ENABLED
from ovirt_provider_config import KEY_NEUTRON_PORT
from ovirt_provider_config import KEY_NOVA_PORT
from ovirt_provider_config import KEY_OPENSTACK_KEYSTONE_ID
from ovirt_provider_config import KEY_OPENSTACK_NEUTRON_ID
from ovirt_provider_config import KEY_OPENSTACK_REGION
from ovirt_provider_config import KEY_OPENSTACK_TENANT_DESCRIPTION
from ovirt_provider_config import KEY_OPENSTACK_TENANT_ID
from ovirt_provider_config import KEY_OPENSTACK_TENANT_NAME
from ovirt_provider_config import KEY_OVN_REMOTE
from ovirt_provider_config import KEY_OVS_VERSION_29
from ovirt_provider_config import KEY_PROVIDER_HOST
from ovirt_provider_config import KEY_SSL_CACERT_FILE
from ovirt_provider_config import KEY_SSL_CERT_FILE
from ovirt_provider_config import KEY_SSL_CIPHERS_STRING
from ovirt_provider_config import KEY_SSL_KEY_FILE
from ovirt_provider_config import KEY_URL_FILTER_EXCEPTION
from ovirt_provider_config import KEY_VALIDATION_MAX_ALLOWED_MTU


PROTOCOL_HTTP = 'http'
PROTOCOL_HTTPS = 'https'
PROTOCOL_SSL = 'ssl'

SERVICE_URL = '{protocol}://{host}:{port}/'

KEYSTONE_VERSION = 'v2.0/'
NEUTRON_VERSION = 'v2.0/'
NOVA_VERSION = 'v2.1/'


def neturon_port():
    return ovirt_provider_config.getint(
        CONFIG_SECTION_PROVIDER, KEY_NEUTRON_PORT, DEFAULT_NEUTRON_PORT
    )


def keystone_port():
    return ovirt_provider_config.getint(
        CONFIG_SECTION_PROVIDER, KEY_KEYSTONE_PORT, DEFAULT_KEYSTONE_PORT
    )


def nova_port():
    return ovirt_provider_config.getint(
        CONFIG_SECTION_PROVIDER, KEY_NOVA_PORT, DEFAULT_NOVA_PORT
    )


def provider_host():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER, KEY_PROVIDER_HOST, DEFAULT_PROVIDER_HOST
    )


def openstack_region():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER, KEY_OPENSTACK_REGION, DEFAULT_OPENSTACK_REGION
    )


def openstack_neutron_id():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_NEUTRON_ID,
        DEFAULT_OPENSTACK_NEUTRON_ID,
    )


def openstack_keystone_id():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_KEYSTONE_ID,
        DEFAULT_OPENSTACK_KEYSTONE_ID,
    )


def tenant_name():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_TENANT_NAME,
        DEFAULT_OPENSTACK_TENANT_NAME,
    )


def tenant_description():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_TENANT_DESCRIPTION,
        DEFAULT_OPENSTACK_TENANT_DESCRIPTION,
    )


def keystone_url():
    return SERVICE_URL.format(
        protocol=PROTOCOL_HTTPS if ssl_enabled() else PROTOCOL_HTTP,
        host=provider_host(),
        port=keystone_port(),
    )


def neutron_url():
    return SERVICE_URL.format(
        protocol=PROTOCOL_HTTPS if ssl_enabled() else PROTOCOL_HTTP,
        host=provider_host(),
        port=neturon_port(),
    )


def nova_url():
    return SERVICE_URL.format(
        protocol=PROTOCOL_HTTPS if ssl_enabled() else PROTOCOL_HTTP,
        host=provider_host(),
        port=nova_port(),
    )


def neutron_url_with_version():
    return neutron_url() + NEUTRON_VERSION


def nova_url_with_version():
    return nova_url() + NOVA_VERSION


def keystone_url_with_version():
    return keystone_url() + KEYSTONE_VERSION


def tenant_id():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_TENANT_ID,
        DEFAULT_OPENSTACK_TENANT_ID,
    )


def ssl_enabled():
    return ovirt_provider_config.getboolean(
        CONFIG_SECTION_SSL, KEY_HTTPS_ENABLED, DEFAULT_SSL_ENABLED
    )


def ssl_key_file():
    return ovirt_provider_config.get(
        CONFIG_SECTION_SSL, KEY_SSL_KEY_FILE, DEFAULT_SSL_KEY_FILE
    )


def ssl_cert_file():
    return ovirt_provider_config.get(
        CONFIG_SECTION_SSL, KEY_SSL_CERT_FILE, DEFAULT_SSL_CERT_FILE
    )


def ssl_cacert_file():
    return ovirt_provider_config.get(
        CONFIG_SECTION_SSL, KEY_SSL_CACERT_FILE, DEFAULT_SSL_CERT_FILE
    )


def ssl_ciphers_string():
    return ovirt_provider_config.get(
        CONFIG_SECTION_SSL, KEY_SSL_CIPHERS_STRING, DEFAULT_SSL_CIPHERS_STRING
    )


def ovn_remote():
    return ovirt_provider_config.get(
        CONFIG_SECTION_OVN_REMOTE,
        KEY_OVN_REMOTE,
        DEFAULT_OVN_REMOTE_AT_LOCALHOST,
    )


def dhcp_lease_time():
    return ovirt_provider_config.get(
        CONFIG_SECTION_DHCP, KEY_DHCP_LEASE_TIME, DEFAULT_DHCP_LEASE_TIME
    )


def dhcp_server_mac():
    return ovirt_provider_config.get(
        CONFIG_SECTION_DHCP, KEY_DHCP_SERVER_MAC, DEFAULT_DHCP_SERVER_MAC
    )


def dhcp_enable_mtu():
    return ovirt_provider_config.getboolean(
        CONFIG_SECTION_DHCP, KEY_DHCP_ENABLE_MTU, DEFAULT_DHCP_ENABLE_MTU
    )


def dhcp_mtu():
    return ovirt_provider_config.get(
        CONFIG_SECTION_DHCP, KEY_DHCP_MTU, DEFAULT_DHCP_MTU
    )


def dhcp_ipv6_address_mode():
    return ovirt_provider_config.get(
        CONFIG_SECTION_DHCP,
        KEY_DHCP_DEFAULT_IPV6_ADDRESS_MODE,
        DEFAULT_DHCP_DEFAULT_IPV6_ADDRESS_MODE,
    )


def auth_plugin():
    return ovirt_provider_config.get(
        CONFIG_SECTION_AUTH, KEY_AUTH_PLUGIN, DEFAULT_AUTH_PLUGIN
    )


def auth_token_timeout():
    return ovirt_provider_config.getint(
        CONFIG_SECTION_AUTH, KEY_AUTH_TOKEN_TIMEOUT, DEFAULT_AUTH_TOKEN_TIMEOUT
    )


def is_ovn_remote_ssl():
    protocol = ovn_remote().split(':')[0]
    return protocol == PROTOCOL_SSL


def ovs_version_29():
    return ovirt_provider_config.getboolean(
        CONFIG_SECTION_PROVIDER, KEY_OVS_VERSION_29, DEFAULT_OVS_VERSION_29
    )


def max_allowed_mtu():
    return ovirt_provider_config.getint(
        CONFIG_SECTION_VALIDATION,
        KEY_VALIDATION_MAX_ALLOWED_MTU,
        DEFAULT_VALIDATION_MAX_ALLOWED_MTU,
    )


def default_port_security_enabled():
    return ovirt_provider_config.getboolean(
        CONFIG_SECTION_NETWORK,
        KEY_NETWORK_PORT_SECURITY_ENABLED,
        DEFAULT_NETWORK_PORT_SECURITY_ENABLED,
    )


def url_filter_exception():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_URL_FILTER_EXCEPTION,
        DEFAULT_URL_FILTER_EXCEPTION,
    )
