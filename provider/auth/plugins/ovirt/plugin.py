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
#
from __future__ import absolute_import

import ovirt_provider_config

from auth.plugin import Plugin

from . import sso

DEFAULT_HOST = 'https://localhost'
KEY_HOST = 'host'

DEFAULT_BASE = '/ovirt-engine'
KEY_BASE = 'base'

DEFAULT_CA_FILE = '/etc/pki/ovirt-engine/ca.pem'
KEY_CA_FILE = 'ca-file'

DEFAULT_SSO_CLIENT_ID = 'ovirt-engine-core'
KEY_SSO_CLIENT_ID = 'sso-client-id'

DEFAULT_SSO_CLIENT_SECRET = 'secret'
KEY_SSO_CLIENT_SECRET = 'sso-client-secret'

OVIRT_CONFIG_SECTION = 'OVIRT'


class OVirtPlugin(Plugin):

    def create_token(self, user_at_domain, user_password):
        return sso.create_token(username=user_at_domain,
                                password=user_password,
                                engine_url=self._engine_url(),
                                ca_file=self._engine_ca_file())

    @staticmethod
    def _engine_url():
        return OVirtPlugin._engine_host() + OVirtPlugin._engine_base()

    @staticmethod
    def _engine_host():
        return ovirt_provider_config.get(OVIRT_CONFIG_SECTION, KEY_HOST,
                                         DEFAULT_HOST)

    @staticmethod
    def _engine_base():
        return ovirt_provider_config.get(OVIRT_CONFIG_SECTION, KEY_BASE,
                                         DEFAULT_BASE)

    @staticmethod
    def _engine_ca_file():
        return ovirt_provider_config.get(OVIRT_CONFIG_SECTION, KEY_CA_FILE,
                                         DEFAULT_CA_FILE)

    @staticmethod
    def _sso_client_id():
        return ovirt_provider_config.get(OVIRT_CONFIG_SECTION,
                                         KEY_SSO_CLIENT_ID,
                                         DEFAULT_SSO_CLIENT_ID)

    @staticmethod
    def _sso_client_secret():
        return ovirt_provider_config.get(OVIRT_CONFIG_SECTION,
                                         KEY_SSO_CLIENT_SECRET,
                                         DEFAULT_SSO_CLIENT_SECRET)
