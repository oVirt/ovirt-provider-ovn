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

import ovsdbapp.backend.ovs_idl.connection
from ovsdbapp.schema.ovn_northbound.impl_idl import OvnNbApiIdlImpl

from ovirt_provider_config_common import ovn_remote
from ovirt_provider_config_common import dhcp_lease_time
from ovirt_provider_config_common import dhcp_server_mac
from ovirt_provider_config_common import dhcp_enable_mtu
from ovirt_provider_config_common import dhcp_mtu

from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import NetworkPort
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import RestDataError
from ovndb.ovn_north_mappers import SubnetConfigError
from ovndb.ovn_north_mappers import SubnetMapper


class DbSetCommand(object):

    def __init__(self, idl, table, entity_id):
        self.idl = idl
        self.table = table
        self.entity_id = entity_id
        self.values = list()

    def execute(self):
        if not self.values:
            return
        x = self.idl.db_set(
            self.table,
            self.entity_id,
            *self.values
        )
        x.execute()

    def add(self, column, value, add_condition=True):
        if add_condition:
            self.values.append((column, value))


class OvnNorth(object):

    OVN_NORTHBOUND = 'OVN_Northbound'
    TABLE_LS = 'Logical_Switch'
    ROW_LS_NAME = 'name'
    ROW_LS_OTHER_CONFIG = 'other_config'

    TABLE_LSP = 'Logical_Switch_Port'
    ROW_LSP_NAME = 'name'
    ROW_LSP_ADDRESSES = 'addresses'
    ROW_LSP_EXTERNAL_IDS = 'external_ids'
    ROW_LSP_ENABLED = 'enabled'
    ROW_LSP_DHCPV4_OPTIONS = 'dhcpv4_options'

    TABLE_DHCP_Options = 'DHCP_Options'
    ROW_DHCP_EXTERNAL_IDS = 'external_ids'
    ROW_DHCP_OPTIONS = 'options'
    ROW_DHCP_CIDR = 'cidr'

    def __init__(self):
        ovsdb_connection = ovsdbapp.backend.ovs_idl.connection.Connection(
            idl=ovsdbapp.backend.ovs_idl.connection.OvsdbIdl.from_server(
                ovn_remote(),
                OvnNorth.OVN_NORTHBOUND
            ),
            timeout=100)
        self.idl = OvnNbApiIdlImpl(ovsdb_connection)

    # TODO: could this be moved to ovsdbapp?
    def _get_port_network(self, port):
        networks = self.idl.ls_list().execute()
        return next(network for network in networks if port in network.ports)

    def _is_port_ovirt_controlled(self, port_row):
        return PortMapper.OVN_NIC_NAME in port_row.external_ids

    @NetworkMapper.map_to_rest
    def list_networks(self):
        return self.idl.ls_list().execute()

    @NetworkMapper.map_to_rest
    def get_network(self, network_id):
        return self.idl.ls_get(network_id).execute()

    @NetworkMapper.validate_add
    @NetworkMapper.map_from_rest
    @NetworkMapper.map_to_rest
    def add_network(self, name):
        # TODO: ovirt allows multiple networks with the same name
        # in oVirt, but OVS does not (may_exist=False will cause early fail)
        return self.idl.ls_add(switch=name, may_exist=False).execute()

    @NetworkMapper.validate_update
    @NetworkMapper.map_from_rest
    def update_network(self, network_id, name):
        self.idl.db_set(
            self.TABLE_LS,
            network_id,
            (self.ROW_LS_NAME, name),
        ).execute()
        return self.get_network(network_id)

    def delete_network(self, network_id):
        network = self.idl.ls_get(network_id).execute()
        if not network:
            raise RestDataError('Network %s does not exist' % network_id)
        if network.ports:
            raise RestDataError(
                'Unable to delete network %s. Ports exist for the network'
                % network_id
            )

        # TODO: once subnets are added we need to do:
        # subnets = self.idl.dhcp_options_list(ids_only=False).execute()
        # for subnet in subnets:
        #    if subnet.external_ids.get('ovirt_network_id'):
        #        if id == str(subnet.uuid):
        #            self.idl.dhcp_options_del(subnet.uuid).execute()

        self.idl.ls_del(network_id).execute()

    @PortMapper.map_to_rest
    def list_ports(self):
        ports_rows = self.idl.lsp_list().execute()
        return [NetworkPort(port_row, self._get_port_network(port_row))
                for port_row in ports_rows
                if self._is_port_ovirt_controlled(port_row)]

    @PortMapper.map_to_rest
    def get_port(self, port_id):
        return self._get_port(port_id)

    def _get_port(self, port_id):
        port = self.idl.lsp_get(port_id).execute()
        if not self._is_port_ovirt_controlled(port):
            raise ValueError('Not an ovirt controller port')
        return NetworkPort(port, self._get_port_network(port))

    @PortMapper.validate_add
    @PortMapper.map_from_rest
    def add_port(
        self,
        network_id,
        name,
        mac=None,
        is_enabled=None,
        device_id=None,
        device_owner=None,
    ):
        port = self._create_port(name, network_id)
        port_id = port.uuid
        self._update_port_values(port, port_id, network_id, name, mac,
                                 is_enabled, device_id, device_owner)
        return self.get_port(port_id)

    @PortMapper.validate_update
    @PortMapper.map_from_rest
    def update_port(
        self,
        port_id,
        network_id=None,
        name=None,
        mac=None,
        is_enabled=None,
        device_id=None,
        device_owner=None,
    ):
        port = self._get_port(port_id).port
        network_id = self._get_validated_port_network_id(port, network_id)
        self._update_port_values(port, port_id, network_id, name, mac,
                                 is_enabled, device_id, device_owner)
        return self.get_port(port_id)

    def _update_port_values(self, port, port_id, network_id, name, mac,
                            is_enabled, device_id, device_owner):
        # TODO(add transaction): setting of the individual values should
        # one day be done in a transaction:
        #   txn = Transaction(self.idl, self.ovsdb_connection)
        #   txn.add(<command>)
        #   ...
        #   txn.commit()
        # The ovsdbapp transactions seem to have synchronization issues at the
        # moment, hence we'll be using individual transactions for now.
        if not mac and port.addresses:
            mac = port.addresses[0].split()[0]
        subnet_row = self._get_dhcp_by_network_id(network_id)

        if mac:
            if subnet_row:
                mac += ' dynamic'
            self._lsp_set_command(
                port_id, self.ROW_LSP_ADDRESSES, [mac]).execute()
        self._lsp_set(device_id, port_id, self.ROW_LSP_EXTERNAL_IDS,
                      {PortMapper.OVN_DEVICE_ID: device_id})
        self._lsp_set(name, port_id, self.ROW_LSP_EXTERNAL_IDS,
                      {PortMapper.OVN_NIC_NAME: name})
        self._lsp_set(device_owner, port_id, self.ROW_LSP_EXTERNAL_IDS,
                      {PortMapper.OVN_DEVICE_OWNER: device_owner})
        self._lsp_set(is_enabled is not None, port_id,
                      self.ROW_LSP_ENABLED, is_enabled)
        self._lsp_set(subnet_row, port_id, self.ROW_LSP_DHCPV4_OPTIONS,
                      [subnet_row])

    def _get_validated_port_network_id(self, port, network_id):
        """
        Validates that the network_id proposed for the port is valid,
        or if no network_id is given, retrieves the port to which
        the port currently belongs.
        If network_id is not None, it has to match the network to which
        the port already belongs. Moving a port from one network to another
        is not supported
        :param port: the port to be checked
        :param network_id: the network_id received for the port, None if not
        specified
        :return: the port's network_id
        :raises ValueError if new network_id does not match the existing one
        """
        old_network_id = self._get_port_network(port).uuid
        if network_id and not str(old_network_id) == network_id:
            raise ValueError('Unable to change network of existing port')
        return network_id or old_network_id

    def _create_port(self, name, network_id):
        port = self.idl.lsp_add(
            network_id,
            name,
            may_exist=False
        ).execute()
        port_id = str(port.uuid)
        self._lsp_set_command(port_id, self.ROW_LSP_NAME,
                              str(port_id)).execute()
        return port

    def _get_dhcp_by_network_id(self, network_id):
        dhcps = self.idl.dhcp_options_list().execute()
        for row in dhcps:
            if str(row.external_ids.get(
                SubnetMapper.OVN_NETWORK_ID
            )) == network_id:
                return row

    def _lsp_set(self, _lsp_set_if, port_id, column, value):
        if _lsp_set_if:
            self._lsp_set_command(port_id, column, value).execute()

    def _lsp_set_command(self, port_id, column, value):
        return self.idl.db_set(
            self.TABLE_LSP,
            port_id,
            (column, value),
        )

    def update_port_mac(self, port_id, macaddress):
        pass

    def delete_port(self, port_id):
        self.idl.lsp_del(port_id).execute()

    @SubnetMapper.map_to_rest
    def list_subnets(self):
        return self.idl.dhcp_options_list().execute()

    @SubnetMapper.map_to_rest
    def get_subnet(self, subnet_id):
        return self.idl.dhcp_options_get(subnet_id).execute()

    @SubnetMapper.validate_add
    @SubnetMapper.map_from_rest
    def add_subnet(
        self,
        name,
        cidr,
        network_id,
        gateway,
        dns=None,
    ):
        if not self.idl.ls_get(network_id).execute():
            raise SubnetConfigError('Subnet can not be created, network {}'
                                    ' does not exist'.format(network_id))

        if self._get_dhcp_by_network_id(network_id):
            raise SubnetConfigError('Unable to create more than one subnet'
                                    ' for network {}'.format(network_id))

        external_ids = {
            SubnetMapper.OVN_NAME: name,
            SubnetMapper.OVN_NETWORK_ID: network_id
        }
        dhcp_server_ip = cidr.split('/', 1)[0]

        options = {
            SubnetMapper.OVN_DHCP_SERVER_ID: dhcp_server_ip,
            SubnetMapper.OVN_GATEWAY: gateway,
            SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac(),
            SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time(),
        }
        if dhcp_enable_mtu():
            options[SubnetMapper.OVN_DHCP_MTU] = dhcp_mtu()

        if dns:
            options[SubnetMapper.OVN_DNS_SERVER] = dns

        self.idl.db_set(
            OvnNorth.TABLE_LS,
            network_id,
            (OvnNorth.ROW_LS_OTHER_CONFIG, {NetworkMapper.OVN_SUBNET: cidr}),
        ).execute()

        subnet_id = self.idl.dhcp_options_add(cidr, **external_ids).execute()
        self.idl.dhcp_options_set_options(subnet_id, **options).execute()
        return self.get_subnet(subnet_id)

    @SubnetMapper.validate_update
    @SubnetMapper.map_from_rest
    def update_subnet(
        self,
        subnet_id,
        name=None,
        cidr=None,
        network_id=None,
        gateway=None,
        dns=None,
    ):
        subnet_by_network = self._get_dhcp_by_network_id(network_id)
        if subnet_by_network and str(subnet_by_network.uuid) != subnet_id:
            raise SubnetConfigError(
                'Unable to move subnet to network {network_id}. The network'
                ' already has a subnet assigned'.format(network_id=network_id)
            )

        db_set_command = DbSetCommand(
            self.idl, self.TABLE_DHCP_Options, subnet_id)

        if cidr:
            dhcp_server_ip = cidr.split('/', 1)[0]
            db_set_command.add(
                OvnNorth.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_SERVER_ID: dhcp_server_ip}
            )
            db_set_command.add(self.ROW_DHCP_CIDR, cidr)
            self.idl.db_set(
                self.TABLE_LS,
                network_id,
                (self.ROW_LS_OTHER_CONFIG, {NetworkMapper.OVN_SUBNET: cidr}),
            ).execute()

        db_set_command.add(
            self.ROW_DHCP_EXTERNAL_IDS,
            {SubnetMapper.OVN_NAME: name},
            name
        )
        db_set_command.add(
            self.ROW_DHCP_EXTERNAL_IDS,
            {SubnetMapper.OVN_NETWORK_ID: network_id},
            network_id
        )
        db_set_command.add(
            self.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_GATEWAY: gateway},
            gateway
        )
        db_set_command.add(
            self.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DNS_SERVER: dns},
            dns
        )
        db_set_command.add(
            self.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time()}
        )
        db_set_command.add(
            self.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac()}
        )
        db_set_command.execute()

        return self.get_subnet(subnet_id)

    def delete_subnet(self, subnet_id):
        self.idl.dhcp_options_del(subnet_id).execute()
