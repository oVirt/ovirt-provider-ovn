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
ENGINE_BASE = '/ovirt-engine'
ENGINE_CA_FILE = '/etc/pki/ovirt-engine/ca.pem'

OVIRT_CONFIG_SECTION = 'OVIRT'


class OVirtPlugin(Plugin):

    def create_token(self, user_at_domain, user_password):
        return sso.create_token(username=user_at_domain,
                                password=user_password,
                                engine_url=_engine_url(),
                                ca_file=_engine_ca_file())


def _engine_url():
    return _engine_host() + _engine_base()


def _engine_host():
    return ovirt_provider_config.get(OVIRT_CONFIG_SECTION, 'host',
                                     DEFAULT_HOST)


def _engine_base():
    return ovirt_provider_config.get(OVIRT_CONFIG_SECTION, 'base', ENGINE_BASE)


def _engine_ca_file():
    return ovirt_provider_config.get(OVIRT_CONFIG_SECTION, 'ca-file',
                                     ENGINE_CA_FILE)
