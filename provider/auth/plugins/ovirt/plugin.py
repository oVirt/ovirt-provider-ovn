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

from auth.plugin import Plugin
from ovirt_provider_config import CONFIG_SECTION_OVIRT
from ovirt_provider_config import KEY_OVIRT_HOST
from ovirt_provider_config import KEY_OVIRT_BASE
from ovirt_provider_config import KEY_OVIRT_CA_FILE
from ovirt_provider_config import KEY_OVIRT_AUTH_TIMEOUT
from ovirt_provider_config import KEY_OVIRT_SSO_CLIENT_ID
from ovirt_provider_config import KEY_OVIRT_SSO_CLIENT_SECRET
from ovirt_provider_config import DEFAULT_OVIRT_HOST
from ovirt_provider_config import DEFAULT_OVIRT_BASE
from ovirt_provider_config import DEFAULT_OVIRT_CA_FILE
from ovirt_provider_config import DEFAULT_OVIRT_SSO_CLIENT_ID
from ovirt_provider_config import DEFAULT_OVIRT_SSO_CLIENT_SECRET
from ovirt_provider_config import DEFAULT_OVIRT_AUTH_TIMEOUT

from . import sso


class OVirtPlugin(Plugin):
    def create_token(self, user_at_domain, user_password):
        return sso.create_token(
            username=user_at_domain,
            password=user_password,
            engine_url=self._engine_url(),
            ca_file=self._engine_ca_file(),
            timeout=self._timeout(),
        )

    @staticmethod
    def _engine_url():
        return OVirtPlugin._engine_host() + OVirtPlugin._engine_base()

    @staticmethod
    def _engine_host():
        return ovirt_provider_config.get(
            CONFIG_SECTION_OVIRT, KEY_OVIRT_HOST, DEFAULT_OVIRT_HOST
        )

    @staticmethod
    def _engine_base():
        return ovirt_provider_config.get(
            CONFIG_SECTION_OVIRT, KEY_OVIRT_BASE, DEFAULT_OVIRT_BASE
        )

    @staticmethod
    def _engine_ca_file():
        return ovirt_provider_config.get(
            CONFIG_SECTION_OVIRT, KEY_OVIRT_CA_FILE, DEFAULT_OVIRT_CA_FILE
        )

    @staticmethod
    def _timeout():
        return ovirt_provider_config.getfloat(
            CONFIG_SECTION_OVIRT,
            KEY_OVIRT_AUTH_TIMEOUT,
            DEFAULT_OVIRT_AUTH_TIMEOUT,
        )

    @staticmethod
    def _sso_client_id():
        return ovirt_provider_config.get(
            CONFIG_SECTION_OVIRT,
            KEY_OVIRT_SSO_CLIENT_ID,
            DEFAULT_OVIRT_SSO_CLIENT_ID,
        )

    @staticmethod
    def _sso_client_secret():
        return ovirt_provider_config.get(
            CONFIG_SECTION_OVIRT,
            KEY_OVIRT_SSO_CLIENT_SECRET,
            DEFAULT_OVIRT_SSO_CLIENT_SECRET,
        )
