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

from ovsdbapp.backend.ovs_idl import connection
from ovsdbapp.schema.ovn_northbound.impl_idl import OvnNbApiIdlImpl

import ovirt_provider_config
from ovirt_provider_config import CONFIG_SECTION_OVN_REMOTE
from ovirt_provider_config import DEFAULT_OVN_REMOTE_AT_LOCALHOST
from ovirt_provider_config import KEY_OVN_REMOTE


class OvnNorth(object):

    def __init__(self):
        ovsdb_connection = connection.Connection(
            idl=connection.OvsdbIdl.from_server(
                self._ovn_remote(),
                'OVN_Northbound'
            ),
            timeout=100)
        self.idl = OvnNbApiIdlImpl(ovsdb_connection)

    def list_networks(self):
        return []

    def get_network(self, network_id):
        return None

    def add_network(self, name):
        return None

    def update_network(self, network_id, name):
        return None

    def delete_network(self, network_id):
        pass

    def list_ports(self):
        return []

    def get_port(self, port_id):
        return None

    def add_port(
        self,
        network_id,
        name,
        mac=None,
        is_enabled=None,
        is_up=None,
        external_device_id=None,
        external_owner=None,
    ):
        return None

    def update_port(
        self,
        port_id,
        network_id=None,
        name=None,
        mac=None,
        is_enabled=None,
        is_up=None,
        external_device_id=None,
        external_owner=None,
    ):
        return None

    def update_port_mac(self, port_id, macaddress):
        pass

    def delete_port(self, port_id):
        pass

    def list_subnets(self):
        return []

    def get_subnet(self, subnet_id):
        return None

    def add_subnet(
        self,
        name,
        cidr,
        network_id,
        dns=None,
        gateway=None
    ):
        return None

    def update_subnet(
        self,
        subnet_id,
        name=None,
        cidr=None,
        dns=None,
        gateway=None
    ):
        return None

    def delete_subnet(self, subnet_id):
        pass

    @staticmethod
    def _ovn_remote():
        return ovirt_provider_config.get(
            CONFIG_SECTION_OVN_REMOTE,
            KEY_OVN_REMOTE,
            DEFAULT_OVN_REMOTE_AT_LOCALHOST
        )
