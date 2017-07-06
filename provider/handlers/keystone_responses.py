# Copyright 2017 Red Hat, Inc.
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

from handlers.base_handler import BadRequestError
from handlers.base_handler import POST
from handlers.selecting_handler import rest

from ovirt_provider_config import CONFIG_SECTION_PROVIDER
from ovirt_provider_config import KEY_KEYSTONE_PORT
from ovirt_provider_config import KEY_NEUTRON_PORT
from ovirt_provider_config import KEY_PROVIDER_HOST
from ovirt_provider_config import KEY_OPENSTACK_REGION
from ovirt_provider_config import KEY_OPENSTACK_NEUTRON_ID
from ovirt_provider_config import KEY_OPENSTACK_KEYSTONE_ID

from ovirt_provider_config import DEFAULT_NEUTRON_PORT
from ovirt_provider_config import DEFAULT_KEYSTONE_PORT
from ovirt_provider_config import DEFAULT_PROVIDER_HOST
from ovirt_provider_config import DEFAULT_OPENSTACK_REGION
from ovirt_provider_config import DEFAULT_OPENSTACK_NEUTRON_ID
from ovirt_provider_config import DEFAULT_OPENSTACK_KEYSTONE_ID

import auth
# import ovirt_provider_config

SSL_CONFIG_SECTION = 'SSL'

NEUTRON_URL = 'http://{host}:{neutron_port}/v2.0/networks'
KEYSTONE_URL = 'http://{host}:{keystone_port}/v2.0/tokens'

TOKENS = 'tokens'
_responses = {}


def _neturon_port():
    return ovirt_provider_config.getint(
        CONFIG_SECTION_PROVIDER,
        KEY_NEUTRON_PORT,
        DEFAULT_NEUTRON_PORT
    )


def _keystone_port():
    return ovirt_provider_config.getint(
        CONFIG_SECTION_PROVIDER,
        KEY_KEYSTONE_PORT,
        DEFAULT_KEYSTONE_PORT
    )


def _provider_host():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_PROVIDER_HOST,
        DEFAULT_PROVIDER_HOST
    )


def _openstack_region():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_REGION,
        DEFAULT_OPENSTACK_REGION
    )


def _openstack_neutron_id():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_NEUTRON_ID,
        DEFAULT_OPENSTACK_NEUTRON_ID
    )


def _openstack_keystone_id():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_KEYSTONE_ID,
        DEFAULT_OPENSTACK_KEYSTONE_ID
    )


@rest(POST, TOKENS, _responses)
def post_tokens(content, id):
    try:
        password_credentials = content['auth']['passwordCredentials']
        user_at_domain = password_credentials['username']
        user_password = password_credentials['password']
    except KeyError as e:
        raise BadRequestError(e)
    token = auth.create_token(
        user_at_domain=user_at_domain,
        user_password=user_password)

    host = _provider_host()
    neutron_port = _neturon_port()
    keystone_port = _keystone_port()

    neutron_url = NEUTRON_URL.format(host=host, neutron_port=neutron_port)
    keystone_url = KEYSTONE_URL.format(host=host, keystone_port=keystone_port)
    openstack_region = _openstack_region()
    openstack_neutron_id = _openstack_neutron_id()
    openstack_keystone_id = _openstack_keystone_id()

    return {
        'access': {
            'token': {
                'id': token
            },
            'serviceCatalog': [
                {
                    'endpoints': [
                        {
                            'adminURL': neutron_url,
                            'internalURL': neutron_url,
                            'publicURL': neutron_url,
                            'region': openstack_region,
                            'id': openstack_neutron_id,
                        }
                    ],
                    'endpoints_links': [],
                    'type': 'network',
                    'name': 'neutron',
                },
                {
                    'endpoints': [
                        {
                            'adminURL': keystone_url,
                            'region': openstack_region,
                            'internalURL': keystone_url,
                            'id': openstack_keystone_id,
                            'publicURL': keystone_url
                        }
                    ],
                    'endpoints_links': [],
                    'type': 'identity',
                    'name': 'keystone'
                }
            ]
        },
    }


def responses():
    return _responses
