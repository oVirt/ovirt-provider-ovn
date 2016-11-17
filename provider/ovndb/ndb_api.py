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

from collections import namedtuple
import logging

import six

import ovirt_provider_config
from .ovsdb_api import OvsDb
from ovndb.ovn_rest2db_mappers import NetworkMapper, PortMapper, SubnetMapper


# Locally administered mac for use by OVN to assign to dhcp server
DHCP_SERVER_MAC = '02:00:00:00:00:00'
# Make the lease time
DHCP_LEASE_TIME = '86400'


NetworkPort = namedtuple('NetworkPort', ['port', 'network'])


class OvnNbDb(OvsDb):

    NETWORK_TABLE = 'Logical_Switch'
    PORTS_TABLE = 'Logical_Switch_Port'
    DHCP_TABLE = 'DHCP_Options'
    OVN_NB_OVSSCHEMA_FILE = '/usr/share/openvswitch/ovn-nb.ovsschema'
    NETWORK_TABLE_COLUMNS = ['name', 'ports', 'other_config']
    PORTS_TABLE_COLUMNS = ['name', 'type', 'options', 'parent_name', 'tag',
                           'up', 'enabled', 'addresses', 'port_security',
                           'external_ids', 'dhcpv4_options']
    DHCP_TABLE_COLUMNS = ['cidr', 'options', 'external_ids']

    def __init__(self, remote):
        tables = [
            (self.NETWORK_TABLE, self.NETWORK_TABLE_COLUMNS),
            (self.PORTS_TABLE, self.PORTS_TABLE_COLUMNS),
            (self.DHCP_TABLE, self.DHCP_TABLE_COLUMNS)]
        self.connect(tables, remote, self.OVN_NB_OVSSCHEMA_FILE)

    @property
    def networks(self):
        network_rows = self._ovsdb_connection.tables[self.NETWORK_TABLE].rows
        return network_rows.copy().values()

    @property
    def ports(self):
        ports_rows = self._ovsdb_connection.tables[self.PORTS_TABLE].rows
        return [NetworkPort(port_row, self._get_port_network(port_row))
                for port_row in six.itervalues(ports_rows)
                if self._is_port_ovirt_controlled(port_row)]

    def get_network(self, id):
        return self.row_lookup_by_id(self.NETWORK_TABLE, id)

    def get_port(self, port_id):
        port_row = self._get_port_row(port_id)
        if not port_row:
            return None
        network = self._get_port_network(port_row)
        return NetworkPort(port_row, network)

    def update_network(self, network_rest_data):
        transaction = self.create_transaction()
        row = self.set_row(self.NETWORK_TABLE, network_rest_data,
                           NetworkMapper, transaction)
        self.commit(transaction)
        return self.get_real_row_from_inserted(self.NETWORK_TABLE, row,
                                               transaction)

    def update_port(self, port_rest_data):
        assert PortMapper.NETWORK_ID in port_rest_data, ('network_id is a'
                                                         ' required parameter')
        network_id = port_rest_data['network_id']
        transaction = self.create_transaction()
        row = self.set_row(self.PORTS_TABLE, port_rest_data, PortMapper,
                           transaction)
        self._synchronize_network_ports(row, network_id)
        self._set_port_subnet(row, network_id)
        self.commit(transaction)
        row = self.get_real_row_from_inserted(self.PORTS_TABLE, row,
                                              transaction)
        try:
            self._set_port_name_to_uuid(row)
        except Exception:
            logging.exception('Transaction error while adding port.')
            self.delete_port(row.uuid)
            raise
        return NetworkPort(row, self.get_network(network_id))

    def delete_network(self, network_id):
        transaction = self.create_transaction()
        network_row = self.get_network(network_id)
        if network_row is None:
            raise DeletedRowDoesNotExistError('Network {} does not exist.'
                                              .format(network_id))
        network_row.delete()
        self.commit(transaction)

    def delete_port(self, port_id):
        transaction = self.create_transaction()
        port_row = self._get_port_row(port_id)
        if port_row is None:
            raise DeletedRowDoesNotExistError('Port {} does not exist.'
                                              .format(port_id))
        self._synchronize_network_ports(port_row, None)
        port_row.delete()
        self.commit(transaction)

    def update_subnet(self, subnet):
        network_row = self.get_network(subnet['network_id'])
        self._validate_subnet(subnet, network_row)
        transaction = self.create_transaction()
        row = self.set_row(self.DHCP_TABLE, subnet, SubnetMapper, transaction)
        row.setkey('options', 'server_mac', OvnNbDb._dhcp_server_mac)
        row.setkey('options', 'lease_time', OvnNbDb._dhcp_lease_time)
        network_row.setkey('other_config', NetworkMapper.SUBNET,
                           subnet['cidr'])
        self.commit(transaction)
        return self.get_real_row_from_inserted(self.DHCP_TABLE, row,
                                               transaction)

    def get_subnets(self):
        return [row for row in six.itervalues(
                self._ovsdb_connection.tables[self.DHCP_TABLE].rows)
                if 'network_id' in row.external_ids]

    def get_subnet(self, id):
        return self.row_lookup_by_id(self.DHCP_TABLE, id)

    def delete_subnet(self, id):
        row = self.row_lookup_by_id(self.DHCP_TABLE, id)
        if row is None:
            raise DeletedRowDoesNotExistError('Subnet {} does not exist'
                                              .format(id))
        transaction = self.create_transaction()
        if 'network_id' in row.options:
            network_row = self.get_network(row.options['network_id'])
            if network_row:
                port_rows = network_row.ports
                network_row.delvalue('other_config', NetworkMapper.SUBNET)
                for port in port_rows:
                    port.dhcpv4_options = None
        row.delete()
        self.commit(transaction)
        # TODO: should we update macs (delete 'dynamic' everywhere)?
        # This will be known once the OVS IPAM patch is finished.

    def _get_port_row(self, id):
        return self.row_lookup_by_id(self.PORTS_TABLE, id)

    def _synchronize_network_ports(self, port, network_id):
        if network_id:
            network = self.row_lookup_by_id(self.NETWORK_TABLE, network_id)
        else:
            network = None
        self.update_child_parent(self.NETWORK_TABLE, port, network, 'ports')

    def _get_port_network(self, port):
        return next(network for network in self.networks
                    if port in network.ports)

    def _set_port_name_to_uuid(self, row):
        """
        This method updates the name of the row with the row's uuid.
        This is done because:
        - OVN requires the NAME of the port to be present in the VM domxml
        - oVirt external networks framework only passes the id of the port to
          the VIF driver
        To avoid the VIF driver having to query for the Port name, we use
        a workaround in which the uuid and name of an oVirt port row are the
        same.
        The final value of a row uuid is only set after a transaction is
        commited, therefore this operation must be done is a subsequent
        transaction.
        """
        transaction = self.create_transaction()
        self.update_existing_row_value(row, 'name', str(row.uuid), transaction)
        self.commit(transaction)

    def _is_port_ovirt_controlled(self, port_row):
        return PortMapper.NIC_NAME in port_row.options

    def _set_port_subnet(self, port_row, network_id):
        subnet = self.row_lookup(self.DHCP_TABLE, lambda row:
                                 str(row.external_ids.get('network_id')) ==
                                 network_id)
        if subnet:
            port_row.dhcpv4_options = subnet
            port_row.addresses = [port_row.addresses[0] + ' dynamic']

    def _validate_subnet(self, subnet_values, network_row):
        id = subnet_values['network_id']
        if not network_row:
            raise SubnetConfigError('Subnet can not be created, network {}'
                                    ' does not exist'.format(id))

        subnet = self.row_lookup(self.DHCP_TABLE, lambda row: row.external_ids.
                                 get('network_id') == id)
        if subnet is not None:
            raise SubnetConfigError('Unable to create more than one subnet'
                                    ' for network {}'.format(id))

    @staticmethod
    @property
    def _dhcp_lease_time():
        return ovirt_provider_config.get('DHCP', 'dhcp-lease-time',
                                         DHCP_LEASE_TIME)

    @staticmethod
    @property
    def _dhcp_server_mac():
        return ovirt_provider_config.get('DHCP', 'dhcp-server-mac',
                                         DHCP_SERVER_MAC)


class DeletedRowDoesNotExistError(Exception):
    pass


class SubnetConfigError(Exception):
    pass
