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

from datetime import datetime, timedelta
from six.moves import http_client

from ovirt_provider_config_common import auth_token_timeout
from ovirt_provider_config_common import openstack_region
from ovirt_provider_config_common import openstack_neutron_id
from ovirt_provider_config_common import openstack_keystone_id
from ovirt_provider_config_common import tenant_description
from ovirt_provider_config_common import tenant_name
from ovirt_provider_config_common import tenant_id
from ovirt_provider_config_common import keystone_url
from ovirt_provider_config_common import neutron_url
from ovirt_provider_config_common import nova_url_with_version


from handlers.base_handler import BadRequestError
from handlers.base_handler import GET
from handlers.base_handler import POST
from handlers.base_handler import Response
from handlers.responses_utils import get_entity
from handlers.selecting_handler import rest

import auth


SSL_CONFIG_SECTION = 'SSL'

TENANTS = 'tenants'
TOKENS = 'tokens'
_responses = {}


@rest(POST, TOKENS, _responses)
def post_tokens(content, parameters):
    received_auth = get_entity(content, 'auth')
    try:
        if 'passwordCredentials' in received_auth:
            password_credentials = received_auth['passwordCredentials']
            user_at_domain = password_credentials['username']
            user_password = password_credentials['password']
            token = auth.create_token(
                user_at_domain=user_at_domain,
                user_password=user_password)
        else:
            token = received_auth['token']['id']
    except KeyError as e:
        raise BadRequestError(e)

    if not auth.validate_token(token):
        raise auth.Forbidden()

    neutronurl = neutron_url()
    keystoneurl = keystone_url()
    novaurl = nova_url_with_version()
    region = openstack_region()
    neutron_id = openstack_neutron_id()
    keystone_id = openstack_keystone_id()

    # OpenStack Identity API v2.0 specifies HTTP 200 as return code for
    # successful token creation
    http_code = http_client.OK

    return Response({
        'access': {
            'token': {
                'id': token,
                'expires': _get_token_expires()
            },
            'user': {
                'username': 'admin',
                'roles_links': [],
                'id': '',
                'roles': [{'name': 'admin'}],
                'name': 'admin'
            },
            'serviceCatalog': [
                {
                    'endpoints': [
                        {
                            'adminURL': neutronurl,
                            'internalURL': neutronurl,
                            'publicURL': neutronurl,
                            'region': region,
                            'id': neutron_id,
                        }
                    ],
                    'endpoints_links': [],
                    'type': 'network',
                    'name': 'neutron',
                },
                {
                    'endpoints': [
                        {
                            'adminURL': keystoneurl,
                            'region': region,
                            'internalURL': keystoneurl,
                            'id': keystone_id,
                            'publicURL': keystoneurl
                        }
                    ],
                    'endpoints_links': [],
                    'type': 'identity',
                    'name': 'keystone'
                },
                {
                    'endpoints': [
                        {
                            'adminURL': novaurl,
                            'region': region,
                            'internalURL': novaurl,
                            'id': keystone_id,
                            'publicURL': novaurl
                        }
                    ],
                    'endpoints_links': [],
                    'type': 'compute',
                    'name': 'nova'
                }
            ]
        },
    }, code=http_code)


def _get_token_expires():
    if auth_token_timeout() == 0:
        return None

    expires = datetime.utcnow() + timedelta(seconds=auth_token_timeout())
    return expires.strftime('%Y-%m-%dT%H:%M:%SZ')


@rest(GET, TENANTS, _responses)
def get_tenants(content, parameters):
    return Response({
        'tenants': [{
            'description': tenant_description(),
            'name': tenant_name(),
            'id': tenant_id(),
            'enabled': True}]
    })


def responses():
    return _responses
