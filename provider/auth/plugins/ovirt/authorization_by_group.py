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

import ovirt_provider_config

from auth import Unauthorized

from .plugin import OVirtPlugin
from .sso import extract_groups
from .sso import get_token_info
from .sso import is_active

from ovirt_provider_config import CONFIG_SECTION_OVIRT
from ovirt_provider_config import KEY_OVIRT_ADMIN_GROUP_ATTRIBUTE_NAME
from ovirt_provider_config import KEY_OVIRT_ADMIN_GROUP_ATTRIBUTE_VALUE
from ovirt_provider_config import DEFAULT_ENGINE_NETWORK_ADMIN_USER_NAME
from ovirt_provider_config import DEFAULT_ENGINE_NETWORK_ADMIN_ROLE_ID


class AuthorizationByGroup(OVirtPlugin):
    def validate_token(self, token):
        return self._has_group(
            token,
            _admin_group_attribute_name(),
            _admin_group_attribute_value(),
        )

    @staticmethod
    def _has_group(token, attribute_name, attribute_value):

        token_info = get_token_info(
            token=token,
            engine_url=AuthorizationByGroup._engine_url(),
            ca_file=AuthorizationByGroup._engine_ca_file(),
            timeout=AuthorizationByGroup._timeout(),
            client_id=AuthorizationByGroup._sso_client_id(),
            client_secret=AuthorizationByGroup._sso_client_secret(),
        )

        if not is_active(token_info):
            raise Unauthorized('Token is not active.')

        return any(
            [
                _contains(group, attribute_name, attribute_value)
                for group in extract_groups(token_info)
            ]
        )


def _contains(d, key, value):
    return key in d and d[key] == value


def _admin_group_attribute_name():
    return ovirt_provider_config.get(
        CONFIG_SECTION_OVIRT,
        KEY_OVIRT_ADMIN_GROUP_ATTRIBUTE_NAME,
        DEFAULT_ENGINE_NETWORK_ADMIN_USER_NAME,
    )


def _admin_group_attribute_value():
    return ovirt_provider_config.get(
        CONFIG_SECTION_OVIRT,
        KEY_OVIRT_ADMIN_GROUP_ATTRIBUTE_VALUE,
        DEFAULT_ENGINE_NETWORK_ADMIN_ROLE_ID,
    )
