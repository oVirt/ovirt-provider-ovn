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
#
from __future__ import absolute_import

import binascii

import ovirt_provider_config

from auth import Unauthorized

from .plugin import OVirtPlugin
from .sso import get_profiles
from .sso import get_token_info
from .sso import is_active
from .sso import get_user_id
from .sso import extract_authz_name
from .sso import get_principal_id
from .api import search_request
from .api import follow_link

from ovirt_provider_config import CONFIG_SECTION_OVIRT
from ovirt_provider_config import KEY_OVIRT_ADMIN_ROLE_ID
from ovirt_provider_config import DEFAULT_ENGINE_NETWORK_ADMIN_ROLE_ID


STRING_ENCODING = 'ascii'


class AuthorizationByRole(OVirtPlugin):
    def validate_token(self, token):
        return self._has_role(token, _admin_role_id())

    @staticmethod
    def _has_role(token, role_id):
        profiles = get_profiles(
            token=token,
            engine_url=AuthorizationByRole._engine_url(),
            ca_file=AuthorizationByRole._engine_ca_file(),
            timeout=AuthorizationByRole._timeout(),
            client_id=AuthorizationByRole._sso_client_id(),
            client_secret=AuthorizationByRole._sso_client_secret(),
        )

        token_info = get_token_info(
            token=token,
            engine_url=AuthorizationByRole._engine_url(),
            ca_file=AuthorizationByRole._engine_ca_file(),
            timeout=AuthorizationByRole._timeout(),
            client_id=AuthorizationByRole._sso_client_id(),
            client_secret=AuthorizationByRole._sso_client_secret(),
        )

        if not is_active(token_info):
            raise Unauthorized('Token is not active.')

        user_name, authn_name = get_user_id(token_info)

        authz_name = extract_authz_name(profiles, authn_name)

        principal_id = _encode(get_principal_id(token_info))
        users = search_request(
            rel_path='users',
            query='usrname={}@{}'.format(user_name, authz_name),
            engine_url=AuthorizationByRole._engine_url(),
            ca_file=AuthorizationByRole._engine_ca_file(),
            timeout=AuthorizationByRole._timeout(),
            token=token,
        )

        for user in users:
            if user['domain_entry_id'] == principal_id:
                roles = follow_link(
                    obj=user,
                    rel='roles',
                    engine_host=AuthorizationByRole._engine_host(),
                    ca_file=AuthorizationByRole._engine_ca_file(),
                    timeout=AuthorizationByRole._timeout(),
                    token=token,
                )
                for role in roles:
                    if role['id'] == role_id:
                        return True
        return False


def _encode(string):
    return (
        binascii.b2a_hex(string.encode(STRING_ENCODING))
        .decode(STRING_ENCODING)
        .upper()
    )


def _admin_role_id():
    return ovirt_provider_config.get(
        CONFIG_SECTION_OVIRT,
        KEY_OVIRT_ADMIN_ROLE_ID,
        DEFAULT_ENGINE_NETWORK_ADMIN_ROLE_ID,
    )
