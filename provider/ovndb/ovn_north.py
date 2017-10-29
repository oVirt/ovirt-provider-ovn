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

import ovs.stream
import ovsdbapp.backend.ovs_idl.connection
from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound
from ovsdbapp.schema.ovn_northbound.impl_idl import OvnNbApiIdlImpl
import random

from handlers.base_handler import BadRequestError
from handlers.base_handler import ConflictError
from handlers.base_handler import ElementNotFoundError

from ovirt_provider_config_common import ovn_remote
from ovirt_provider_config_common import dhcp_lease_time
from ovirt_provider_config_common import dhcp_server_mac
from ovirt_provider_config_common import dhcp_enable_mtu
from ovirt_provider_config_common import dhcp_mtu
from ovirt_provider_config_common import is_ovn_remote_ssl
from ovirt_provider_config_common import ssl_key_file
from ovirt_provider_config_common import ssl_cacert_file
from ovirt_provider_config_common import ssl_cert_file

from ovndb.ovn_north_mappers import AddRouterInterfaceMapper
from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import NetworkPort
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import RemoveRouterInterfaceMapper
from ovndb.ovn_north_mappers import RestDataError
from ovndb.ovn_north_mappers import RouterMapper
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
    ROW_LS_EXTERNAL_IDS = 'external_ids'

    TABLE_LSP = 'Logical_Switch_Port'
    ROW_LSP_NAME = 'name'
    ROW_LSP_ADDRESSES = 'addresses'
    ROW_LSP_EXTERNAL_IDS = 'external_ids'
    ROW_LSP_ENABLED = 'enabled'
    ROW_LSP_DHCPV4_OPTIONS = 'dhcpv4_options'
    ROW_LSP_TAG_REQUEST = 'tag_request'
    ROW_LSP_TYPE = 'type'
    ROW_LSP_OPTIONS = 'options'
    LSP_TYPE_ROUTER = 'router'
    LSP_TYPE_LOCALNET = 'localnet'
    LSP_ADDRESS_TYPE_DYNAMIC = 'dynamic'
    LSP_ADDRESS_TYPE_ROUTER = 'router'
    LSP_ADDRESS_TYPE_UNKNOWN = 'unknown'
    LSP_OPTION_ROUTER_PORT = 'router-port'
    LSP_OPTION_NETWORK_NAME = 'network_name'

    TABLE_DHCP_Options = 'DHCP_Options'
    ROW_DHCP_EXTERNAL_IDS = 'external_ids'
    ROW_DHCP_OPTIONS = 'options'
    ROW_DHCP_CIDR = 'cidr'

    TABLE_LR = 'Logical_Router'
    ROW_LR_NAME = 'name'
    ROW_LR_ENABLED = 'enabled'

    TABLE_LRP = 'Logical_Router_Port'

    LOCALNET_SWITCH_PORT_NAME = 'localnet_port'
    ROUTER_SWITCH_PORT_NAME = 'router_port'
    UNASSIGNED_SWTICH_PORT_NAME = 'unassgined_port'

    ROUTER_PORT_NAME_PREFIX = 'lrp'

    def __init__(self):
        self._connect()

    def _connect(self):
        self._configure_ssl_connection()
        self.ovsidl = ovsdbapp.backend.ovs_idl.connection.OvsdbIdl.from_server(
            ovn_remote(),
            OvnNorth.OVN_NORTHBOUND
        )
        ovsdb_connection = ovsdbapp.backend.ovs_idl.connection.Connection(
            idl=self.ovsidl,
            timeout=100)
        self.idl = OvnNbApiIdlImpl(ovsdb_connection)

    def _configure_ssl_connection(self):
        if is_ovn_remote_ssl():
            ovs.stream.Stream.ssl_set_private_key_file(ssl_key_file())
            ovs.stream.Stream.ssl_set_certificate_file(ssl_cert_file())
            ovs.stream.Stream.ssl_set_ca_cert_file(ssl_cacert_file())

    def close(self):
        self.ovsidl.close()

    # TODO: could this be moved to ovsdbapp?
    def _get_port_network(self, port):
        networks = self.idl.ls_list().execute()
        return next(network for network in networks if port in network.ports)

    def _is_port_ovirt_controlled(self, port_row):
        return PortMapper.OVN_NIC_NAME in port_row.external_ids

    @NetworkMapper.map_to_rest
    def list_networks(self):
        return self.idl.ls_list().execute()

    def _get_network(self, network_id):
        network = self.idl.ls_get(network_id).execute()
        if not network:
            raise ElementNotFoundError(
                'Network {network} does not exist'.format(network=network_id)
            )
        return network

    @NetworkMapper.map_to_rest
    def get_network(self, network_id):
        return self._get_network(network_id)

    @NetworkMapper.validate_add
    @NetworkMapper.map_from_rest
    @NetworkMapper.map_to_rest
    def add_network(self, name, localnet=None, vlan=None):
        # TODO: ovirt allows multiple networks with the same name
        # in oVirt, but OVS does not (may_exist=False will cause early fail)
        if localnet:
            return self._add_localnet_network(name, localnet, vlan)
        else:
            return self._add_network(name)

    def _add_network(self, name):
        return self.idl.ls_add(switch=name, may_exist=False).execute()

    def _add_localnet_network(self, name, localnet, vlan):
        network = self.idl.ls_add(switch=name, may_exist=False).execute()
        localnet_port = self._create_port(
            OvnNorth.LOCALNET_SWITCH_PORT_NAME, str(network.uuid))
        self._set_port_localnet_values(localnet_port, localnet, vlan)
        self._set_network_localnet_values(network, localnet, vlan)
        updated_network = self._get_network(str(network.uuid))
        return updated_network

    @NetworkMapper.validate_update
    @NetworkMapper.map_from_rest
    def update_network(self, network_id, name, localnet=None, vlan=None):
        self.idl.db_set(
            self.TABLE_LS,
            network_id,
            (self.ROW_LS_NAME, name),
        ).execute()
        self._update_localnet_on_network(network_id, localnet, vlan)
        return self.get_network(network_id)

    def _update_localnet_on_network(self, network_id, localnet, vlan):
        network = self._get_network(network_id)
        localnet_port = self._get_localnet_port(network)
        if localnet:
            if not localnet_port:
                localnet_port = self._create_port(
                    OvnNorth.LOCALNET_SWITCH_PORT_NAME, str(network.uuid))
            self._set_port_localnet_values(localnet_port, localnet, vlan)
        elif localnet_port:
            self.delete_port(str(localnet_port.uuid))
        self._set_network_localnet_values(network, localnet, vlan)

    def _set_network_localnet_values(self, network, localnet=None, vlan=None):
        db_set_command = DbSetCommand(self.idl, self.TABLE_LS, network.uuid)
        db_set_command.add(
            self.ROW_LS_EXTERNAL_IDS,
            {NetworkMapper.OVN_LOCALNET: localnet},
            localnet
        )
        db_set_command.add(
            self.ROW_LS_EXTERNAL_IDS,
            {NetworkMapper.OVN_VLAN: vlan},
            vlan
        )
        db_set_command.execute()

    def _set_port_localnet_values(self, port, localnet, vlan):
        db_set_command = DbSetCommand(self.idl, self.TABLE_LSP, port.uuid)
        db_set_command.add(
            self.ROW_LSP_ADDRESSES,
            [self.LSP_ADDRESS_TYPE_UNKNOWN]
        )
        db_set_command.add(
            self.ROW_LSP_OPTIONS,
            {OvnNorth.LSP_OPTION_NETWORK_NAME: localnet}
        )
        db_set_command.add(self.ROW_LSP_TYPE, OvnNorth.LSP_TYPE_LOCALNET)
        db_set_command.add(self.ROW_LSP_TAG_REQUEST, vlan)
        db_set_command.execute()

    def delete_network(self, network_id):
        network = self.idl.ls_get(network_id).execute()
        if not network:
            raise RestDataError('Network %s does not exist' % network_id)
        if network.ports:
            localnet_port = self._get_localnet_port(network)
            only_localnet_port = len(network.ports) == 1 and localnet_port
            if not only_localnet_port:
                raise RestDataError(
                    'Unable to delete network %s. Ports exist for the network'
                    % network_id
                )

        subnets = self.idl.dhcp_options_list().execute()
        for subnet in subnets:
            subnet_network_id = subnet.external_ids.get('ovirt_network_id')
            if subnet_network_id:
                if network_id == subnet_network_id:
                    self.idl.dhcp_options_del(subnet.uuid).execute()

        self.idl.ls_del(network_id).execute()

    def _get_localnet_port(self, network):
        for port in network.ports:
            if port.type == OvnNorth.LSP_TYPE_LOCALNET:
                return port
        return None

    @PortMapper.map_to_rest
    def list_ports(self):
        ports_rows = self.idl.lsp_list().execute()
        return [NetworkPort(port_row, self._get_port_network(port_row))
                for port_row in ports_rows
                if self._is_port_ovirt_controlled(port_row)]

    @PortMapper.map_to_rest
    def get_port(self, port_id):
        return self._get_networkport(port_id)

    def _get_switch_port(self, port_id):
        port = self.idl.lsp_get(port_id).execute()
        if not port:
            raise ElementNotFoundError(
                'Port {port} does not exist'.format(port=port_id)
            )
        return port

    def _get_networkport(self, port_id):
        port = self._get_switch_port(port_id)
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
        self._update_port_values(
            port, name, is_enabled, device_id, device_owner
        )
        self._update_port_address(port, network_id=network_id, mac=mac)
        return self.get_port(port.uuid)

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
        port = self._get_networkport(port_id).port
        network_id = self._get_validated_port_network_id(port, network_id)
        self._update_port_values(
            port, name, is_enabled, device_id, device_owner
        )
        self._update_port_address(port, network_id=network_id, mac=mac)
        return self.get_port(port_id)

    def _update_port_values(
        self, port, name=None, is_enabled=None, device_id=None,
        device_owner=None
    ):
        # TODO(add transaction): setting of the individual values should
        # one day be done in a transaction:
        #   txn = Transaction(self.idl, self.ovsdb_connection)
        #   txn.add(<command>)
        #   ...
        #   txn.commit()
        # The ovsdbapp transactions seem to have synchronization issues at the
        # moment, hence we'll be using individual transactions for now.
        db_set_command = DbSetCommand(self.idl, self.TABLE_LSP, port.uuid)
        db_set_command.add(
            self.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_DEVICE_ID: device_id},
            device_id
        )
        db_set_command.add(
            self.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_NIC_NAME: name},
            name
        )
        db_set_command.add(
            self.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_DEVICE_OWNER: device_owner},
            device_owner
        )
        db_set_command.add(
            self.ROW_LSP_ENABLED,
            is_enabled,
            is_enabled
        )
        db_set_command.execute()

    def _update_port_address(self, port, network_id, mac=None):
        if port.type == OvnNorth.LSP_TYPE_ROUTER:
            return
        mac = mac or self._get_port_mac(port)
        if mac:
            db_set_command = DbSetCommand(self.idl, self.TABLE_LSP, port.uuid)
            subnet_row = self._get_dhcp_by_network_id(network_id)
            if subnet_row:
                db_set_command.add(
                    self.ROW_LSP_DHCPV4_OPTIONS, subnet_row.uuid
                )
                mac += ' ' + OvnNorth.LSP_ADDRESS_TYPE_DYNAMIC
            else:
                self.idl.db_clear(
                    OvnNorth.TABLE_LSP, port.uuid,
                    OvnNorth.ROW_LSP_DHCPV4_OPTIONS
                ).execute()

            db_set_command.add(self.ROW_LSP_ADDRESSES, [mac])
            db_set_command.execute()

    def _connect_port_to_router(
        self, port, router_port_name,
        name=None,
        is_enabled=True,
        device_id=None,
        device_owner=None,

     ):
        self._update_port_values(
            port=port,
            name=name,
            is_enabled=is_enabled,
            device_id=device_id,
            device_owner=device_owner
        )

        db_set_command = DbSetCommand(self.idl, self.TABLE_LSP, port.uuid)
        db_set_command.add(
            self.ROW_LSP_TYPE,
            OvnNorth.LSP_TYPE_ROUTER,
        )
        db_set_command.add(
            self.ROW_LSP_OPTIONS,
            {OvnNorth.LSP_OPTION_ROUTER_PORT: router_port_name},
        )
        db_set_command.add(
            self.ROW_LSP_ADDRESSES,
            [OvnNorth.LSP_ADDRESS_TYPE_ROUTER]
        )
        db_set_command.execute()

        self.idl.db_clear(
            OvnNorth.TABLE_LSP, port.uuid, OvnNorth.ROW_LSP_DHCPV4_OPTIONS
        ).execute()

    def _disconnect_port_from_router(self, port):
        self.idl.db_clear(
            OvnNorth.TABLE_LSP, port.uuid, OvnNorth.ROW_LSP_TYPE
        ).execute()
        self.idl.db_remove(
            OvnNorth.TABLE_LSP, port.uuid, OvnNorth.ROW_LSP_OPTIONS,
            OvnNorth.LSP_OPTION_ROUTER_PORT
        ).execute()
        port_name = port.external_ids.get(PortMapper.OVN_NIC_NAME)
        if port_name == OvnNorth.ROUTER_SWITCH_PORT_NAME:
            self._update_port_values(
                port, name=OvnNorth.UNASSIGNED_SWTICH_PORT_NAME
            )

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
        self.idl.db_set(
            self.TABLE_LSP,
            port_id,
            (self.ROW_LSP_NAME, str(port_id))
        ).execute()
        return port

    def _get_dhcp_by_network_id(self, network_id):
        dhcps = self.idl.dhcp_options_list().execute()
        for row in dhcps:
            if str(row.external_ids.get(
                SubnetMapper.OVN_NETWORK_ID
            )) == str(network_id):
                return row

    def update_port_mac(self, port_id, macaddress):
        pass

    def delete_port(self, port_id):
        self.idl.lsp_del(port_id).execute()

    @SubnetMapper.map_to_rest
    def list_subnets(self):
        subnets = self.idl.dhcp_options_list().execute()
        return [
            subnet for subnet in subnets
            if SubnetMapper.OVN_NETWORK_ID in subnet.external_ids
        ]

    def _get_subnet(self, subnet_id):
        subnet = self.idl.dhcp_options_get(subnet_id).execute()
        # TODO: this: str(subnet.uuid) != str(subnet_id)
        # is a workaround for an ovsdbapp problem returning
        # random value for table with no indexing column specified when
        # no record for the given UUID was found.
        # Remove when issue is resolved.
        if not subnet or str(subnet.uuid) != str(subnet_id):
            raise ElementNotFoundError(
                'Subnet {subnet} does not exist'.format(subnet=subnet_id)
            )
        if SubnetMapper.OVN_NETWORK_ID not in subnet.external_ids:
            raise ElementNotFoundError(
                'Subnet {subnet} is not an ovirt manager subnet'
                .format(subnet=subnet_id)
            )
        return subnet

    @SubnetMapper.map_to_rest
    def get_subnet(self, subnet_id):
        return self._get_subnet(subnet_id)

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
        try:
            network = self._get_network(network_id)
        except ElementNotFoundError:
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
            SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac(),
            SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time(),
        }
        if gateway:
            options[SubnetMapper.OVN_GATEWAY] = gateway
        if dhcp_enable_mtu():
            options[SubnetMapper.OVN_DHCP_MTU] = dhcp_mtu()

        if dns:
            options[SubnetMapper.OVN_DNS_SERVER] = dns

        self.idl.db_set(
            OvnNorth.TABLE_LS,
            network_id,
            (OvnNorth.ROW_LS_OTHER_CONFIG, {NetworkMapper.OVN_SUBNET: cidr}),
        ).execute()

        subnet = self.idl.dhcp_options_add(cidr, **external_ids).execute()
        self.idl.dhcp_options_set_options(subnet.uuid, **options).execute()

        for port in network.ports:
            if port.type == OvnNorth.LSP_TYPE_ROUTER:
                continue
            self._update_port_address(port, network_id=network_id)

        return self.get_subnet(subnet.uuid)

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
        if not self.idl.ls_get(network_id).execute():
            raise SubnetConfigError(
                'Unable to move subnet to network {network_id}. The network'
                ' does not exit.'.format(network_id=network_id)
            )
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
        subnet = self._get_subnet(subnet_id)
        router_id = self._get_subnet_gateway_router_id(subnet)
        if router_id:
            raise BadRequestError(
                'Unable to delete subnet {subnet} because it is connected to '
                'router {router}. Please disconnect the subnet from the router'
                ' first.'
                .format(subnet=subnet_id, router=router_id)

            )
        network_id = subnet.external_ids.get(
            SubnetMapper.OVN_NETWORK_ID
        )
        network = self._get_network(network_id)
        self.idl.dhcp_options_del(subnet_id).execute()
        for port in network.ports:
            if port.type == OvnNorth.LSP_TYPE_ROUTER:
                continue
            self._update_port_address(port, network_id=network_id)

    def _get_router(self, router_id):
        # TODO: LrGet is not yet implemented by ovsdbapp
        # patch pending: https://review.openstack.org/#/c/505517/
        # replace once patch is accepted
        try:
            return self.idl.lookup(OvnNorth.TABLE_LR, router_id)
        except RowNotFound:
            raise ElementNotFoundError(
                'Router {router} does not exist'.format(router=router_id)
            )

    @RouterMapper.map_to_rest
    def get_router(self, router_id):
        return self._get_router(router_id)

    @RouterMapper.map_to_rest
    def list_routers(self):
        return self.idl.lr_list().execute()

    @RouterMapper.validate_add
    @RouterMapper.map_from_rest
    @RouterMapper.map_to_rest
    def add_router(self, name, enabled):
        return self.idl.lr_add(
            router=name, may_exist=False, enabled=enabled
        ).execute()

    @RouterMapper.validate_update
    @RouterMapper.map_from_rest
    def update_router(self, router_id, name, enabled):
        db_set_command = DbSetCommand(self.idl, self.TABLE_LR, router_id)
        db_set_command.add(self.ROW_LR_NAME, name, name)
        db_set_command.add(self.ROW_LR_ENABLED, enabled, enabled)
        db_set_command.execute()
        return self.get_router(router_id)

    def delete_router(self, router_id):
        self.idl.lr_del(router_id).execute()

    def _validate_router_exists(self, router_id):
        try:
            self.idl.lookup(OvnNorth.TABLE_LR, router_id)
        except RowNotFound:
            raise ElementNotFoundError(
                'Router {router} does not exist'.format(router=router_id)
            )

    def _create_router_port_name(self, port_id):
        # LSP will reference this LRP by name (port parameter),
        # for convinience we will set the name to the id of the matching LSP
        # with an 'lrp' prefix.
        # We need the prefix due to an ovn issue in OVN lookup (bug pending)
        return OvnNorth.ROUTER_PORT_NAME_PREFIX + str(port_id)

    def _lsp_id_by_lrp(self, lrp):
        return lrp.name[len(OvnNorth.ROUTER_PORT_NAME_PREFIX):]

    def _get_subnet_gateway_router_id(self, subnet):
        return subnet.external_ids.get(SubnetMapper.OVN_GATEWAY_ROUTER_ID)

    def _set_subnet_gateway_router(self, subnet_id, router_id):
        self.idl.db_set(
            OvnNorth.TABLE_DHCP_Options,
            subnet_id,
            (
                OvnNorth.ROW_DHCP_EXTERNAL_IDS,
                {SubnetMapper.OVN_GATEWAY_ROUTER_ID: router_id}
            )
        ).execute()

    def _clear_subnet_gateway_router(self, subnet_id):
        self.idl.db_remove(
            OvnNorth.TABLE_DHCP_Options,
            subnet_id,
            OvnNorth.ROW_DHCP_EXTERNAL_IDS,
            SubnetMapper.OVN_GATEWAY_ROUTER_ID
        ).execute()

    def _validate_create_routing_lsp_by_subnet(
        self, subnet_id, subnet, router_id, network_id
    ):
        if not network_id:
            raise ElementNotFoundError(
                'Unable to add router interface. '
                'Subnet {subnet_id} does not belong to any network'
                .format(subnet_id=subnet_id)
            )

        old_router_id = self._get_subnet_gateway_router_id(subnet)
        if old_router_id:
            if old_router_id == router_id:
                raise BadRequestError(
                    'Can not add subnet {subnet} to router {router}. Subnet is'
                    ' already connected to this router'.format(
                        subnet=subnet_id, router=router_id
                    )
                )
            else:
                raise BadRequestError(
                    'Can not add subnet {subnet} to router {router}. Subnet is'
                    ' already connected to router {old_router}'.format(
                        subnet=subnet_id, router=router_id,
                        old_router=old_router_id
                    )
                )

    def _create_routing_lsp_by_subnet(self, subnet_id, router_id):
        subnet = self._get_subnet(subnet_id)
        network_id = subnet.external_ids.get(SubnetMapper.OVN_NETWORK_ID)
        self._validate_create_routing_lsp_by_subnet(
            subnet_id, subnet, router_id, network_id)
        lrp_ip = self._get_ip_from_subnet(subnet, network_id, router_id)
        port = self._create_port(OvnNorth.ROUTER_SWITCH_PORT_NAME, network_id)
        lrp_name = self._create_router_port_name(port.uuid)
        self._connect_port_to_router(
            port,
            lrp_name,
            name=OvnNorth.ROUTER_SWITCH_PORT_NAME,
            is_enabled=True,
            device_id=port.uuid,
            device_owner=PortMapper.DEVICE_OWNER_OVIRT,
        )
        self._set_subnet_gateway_router(subnet_id, router_id)
        return str(port.uuid), lrp_name, lrp_ip, network_id, self._random_mac()

    def _update_routing_lsp_by_port(self, port_id, router_id):
        port = self._get_switch_port(port_id)
        if port.type == OvnNorth.LSP_TYPE_ROUTER:
            raise BadRequestError(
                'Can not add {port} to router. Port is already connected to a'
                ' router'.format(port=port_id)
            )
        lrp_ip = self._get_ip_from_port(port, router_id)
        lrp_name = self._create_router_port_name(port.uuid)
        mac = self._get_port_mac(port)
        self._connect_port_to_router(port, lrp_name, is_enabled=True)
        return (
            port_id, lrp_name, lrp_ip, str(self._get_port_network(port).uuid),
            mac
        )

    def _create_router_port(self, router_id, lrp_name, lrp_ip, mac):
        self.idl.lrp_add(
            router=router_id, port=lrp_name,
            mac=mac,
            networks=[lrp_ip],
        ).execute()

    @AddRouterInterfaceMapper.validate_update
    @AddRouterInterfaceMapper.map_from_rest
    @AddRouterInterfaceMapper.map_to_rest
    def add_router_interface(self, router_id, subnet_id=None, port_id=None):
        self._validate_router_exists(router_id)
        port_id, lrp_name, lrp_ip, network_id, mac = (
            self._create_routing_lsp_by_subnet(subnet_id, router_id)
            if subnet_id else
            self._update_routing_lsp_by_port(port_id, router_id)
        )
        if not subnet_id:
            subnet_id = str(self._get_dhcp_by_network_id(network_id).uuid)
        self._create_router_port(router_id, lrp_name, lrp_ip, mac)
        return router_id, network_id, port_id, subnet_id

    def _get_ip_from_subnet(self, subnet, network_id, router_id):
        subnet_gateway = subnet.options.get('router')
        if not subnet_gateway:
            raise ElementNotFoundError(
                'Unable to attach network {network_id} to router '
                '{router_id} by subnet {subnet_id}.'
                'Attaching by subnet requires the subnet to have '
                'a default gateway specified.'
                .format(
                    network_id=network_id, subnet_id=subnet.uuid,
                    router_id=router_id
                )
            )
        subnet_netmask = subnet.cidr.split('/')[1]
        return '{ip}/{netmask}'.format(
            ip=subnet_gateway, netmask=subnet_netmask
        )

    def _get_port_ip(self, port, router_id):
        port_addresses = port.dynamic_addresses
        if not port_addresses:
            raise ElementNotFoundError(
                'Unable to attach port {port_id} to router '
                '{router_id}. '
                'Attaching by port requires the port to have '
                'an ip from subnet assigned.'
                .format(port_id=port.uuid, router_id=router_id)
            )
        return port_addresses[0].split(' ')[1]

    def _get_ip_from_port(self, port, router_id):
        port_ip = self._get_port_ip(port, router_id)
        network = self._get_port_network(port)
        network_cidr = network.other_config.get(NetworkMapper.OVN_SUBNET)
        if not network_cidr:
            raise ElementNotFoundError(
                'Unable to attach port {port_id} to router '
                '{router_id}. '
                'Attaching by port requires the port\'s network '
                'to have a subnet attached.'
                .format(port_id=port.uuid, router_id=router_id)
            )
        network_netmask = network_cidr.split('/')[1]
        return '{ip}/{netmask}'.format(
            ip=port_ip, netmask=network_netmask)

    @RemoveRouterInterfaceMapper.validate_update
    @RemoveRouterInterfaceMapper.map_from_rest
    def delete_router_interface(self, router_id, subnet_id=None, port_id=None):
        if subnet_id and port_id:
            self._delete_router_interface_by_subnet_and_port(
                router_id, subnet_id, port_id
            )
        elif subnet_id:
            self._delete_router_interface_by_subnet(router_id, subnet_id)
        else:
            self._delete_router_interface_by_port(router_id, port_id)

    def _delete_router_interface_by_port(self, router_id, port_id):
        lsp = self._get_switch_port(port_id)
        lrp_name = lsp.options.get(OvnNorth.LSP_OPTION_ROUTER_PORT)
        if not lrp_name:
            raise BadRequestError(
                'Port {port} is not connected to a router'
                .format(port=port_id)
            )
        lrp = self._get_lrp(lrp_name)
        network_id = self._get_port_network(lsp)
        lr = self._get_router(router_id)
        self._delete_router_interface(
            router_id, port_id, lrp, network_id, lsp, lr
        )

    def _delete_router_interface(
        self, router_id, port_id, lrp, network_id, lsp, lr
    ):
        if lrp not in lr.ports:
            raise BadRequestError(
                'Port {port} is not connected to router {router}'
                .format(port=port_id, router=router_id)
            )
        self._disconnect_port_from_router(lsp)
        self._update_port_address(lsp, network_id=network_id, mac=lrp.mac)
        self.idl.lrp_del(str(lrp.uuid)).execute()

    def _delete_router_interface_by_subnet_and_port(
        self, router_id, subnet_id, port_id
    ):
        subnet = self._get_subnet(subnet_id)
        network_id = subnet.external_ids[SubnetMapper.OVN_NETWORK_ID]
        network = self._get_network(network_id)
        lsp = self._get_switch_port(port_id)
        if lsp not in network.ports:
            raise ConflictError(
                'Port {port} does not belong to subnet {subnet}.'
                .format(port=port_id, subnet=subnet_id)
            )
        self._delete_router_interface_by_port(router_id, port_id)

    def _delete_router_interface_by_subnet(self, router_id, subnet_id):
        lr = self._get_router(router_id)
        subnet = self._get_subnet(subnet_id)
        network_id = subnet.external_ids[SubnetMapper.OVN_NETWORK_ID]
        network = self._get_network(network_id)
        for lrp in lr.ports:
            lsp_id = self._lsp_id_by_lrp(lrp)
            lsp = self._get_switch_port(lsp_id)
            if lsp in network.ports:
                self._delete_router_interface(
                    router_id, lsp_id, lrp=lrp, network_id=network_id, lsp=lsp,
                    lr=lr
                )
        self._clear_subnet_gateway_router(subnet_id)

    def _get_lrp(self, lrp):
        try:
            return self.idl.lookup(OvnNorth.TABLE_LRP, lrp)
        except RowNotFound:
            raise ElementNotFoundError(
                'Logical router port {port} does not exist'
                .format(port=lrp)
            )

    def _get_port_mac(self, port):
        return port.addresses[0].split()[0] if port.addresses else None

    def _random_mac(self):
        macparts = [0]
        macparts.extend([random.randint(0x00, 0xff) for i in range(5)])
        return ':'.join(map(lambda x: "%02x" % x, macparts))

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()
