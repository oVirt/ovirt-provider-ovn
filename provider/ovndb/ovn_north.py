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

import ovndb.constants as ovnconst
import ovndb.ip as ip_utils
import ovndb.validation as validate

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

from ovndb.db_set_command import DbSetCommand
from ovndb.ovn_north_mappers import AddRouterInterfaceMapper
from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import NetworkPort
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import RemoveRouterInterfaceMapper
from ovndb.ovn_north_mappers import RestDataError
from ovndb.ovn_north_mappers import RouterMapper
from ovndb.ovn_north_mappers import SubnetConfigError
from ovndb.ovn_north_mappers import SubnetMapper


class OvnNorth(object):

    def __init__(self):
        self._connect()

    def _connect(self):
        self._configure_ssl_connection()
        self.ovsidl = ovsdbapp.backend.ovs_idl.connection.OvsdbIdl.from_server(
            ovn_remote(),
            ovnconst.OVN_NORTHBOUND
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

    def _execute(self, command):
        return command.execute()

    def close(self):
        self.ovsidl.close()

    # TODO: could this be moved to ovsdbapp?
    def _get_port_network(self, port):
        networks = self._execute(self.idl.ls_list())
        return next(network for network in networks if port in network.ports)

    def _is_port_ovirt_controlled(self, port_row):
        return PortMapper.OVN_NIC_NAME in port_row.external_ids

    @NetworkMapper.map_to_rest
    def list_networks(self):
        return self._execute(self.idl.ls_list())

    def _get_network(self, network_id):
        network = self._execute(self.idl.ls_get(network_id))
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
        return self._execute(self.idl.ls_add(switch=name, may_exist=False))

    def _add_localnet_network(self, name, localnet, vlan):
        network = self._execute(self.idl.ls_add(switch=name, may_exist=False))
        localnet_port = self._create_port(
            ovnconst.LOCALNET_SWITCH_PORT_NAME, str(network.uuid))
        self._set_port_localnet_values(localnet_port, localnet, vlan)
        self._set_network_localnet_values(network, localnet, vlan)
        updated_network = self._get_network(str(network.uuid))
        return updated_network

    @NetworkMapper.validate_update
    @NetworkMapper.map_from_rest
    def update_network(self, network_id, name, localnet=None, vlan=None):
        self._execute(self.idl.db_set(
            ovnconst.TABLE_LS,
            network_id,
            (ovnconst.ROW_LS_NAME, name),
        ))
        self._update_localnet_on_network(network_id, localnet, vlan)
        return self.get_network(network_id)

    def _update_localnet_on_network(self, network_id, localnet, vlan):
        network = self._get_network(network_id)
        localnet_port = self._get_localnet_port(network)
        if localnet:
            if not localnet_port:
                localnet_port = self._create_port(
                    ovnconst.LOCALNET_SWITCH_PORT_NAME, str(network.uuid))
            self._set_port_localnet_values(localnet_port, localnet, vlan)
        elif localnet_port:
            self._delete_port(str(localnet_port.uuid))
        self._set_network_localnet_values(network, localnet, vlan)

    def _set_network_localnet_values(self, network, localnet=None, vlan=None):
        db_set_command = DbSetCommand(
            self.idl, ovnconst.TABLE_LS, network.uuid
        )
        db_set_command.add(
            ovnconst.ROW_LS_EXTERNAL_IDS,
            {NetworkMapper.OVN_LOCALNET: localnet},
            localnet
        )
        db_set_command.add(
            ovnconst.ROW_LS_EXTERNAL_IDS,
            {NetworkMapper.OVN_VLAN: str(vlan)},
            vlan
        )
        db_set_command.execute()

    def _set_port_localnet_values(self, port, localnet, vlan):
        db_set_command = DbSetCommand(self.idl, ovnconst.TABLE_LSP, port.uuid)
        db_set_command.add(
            ovnconst.ROW_LSP_ADDRESSES,
            [ovnconst.LSP_ADDRESS_TYPE_UNKNOWN]
        )
        db_set_command.add(
            ovnconst.ROW_LSP_OPTIONS,
            {ovnconst.LSP_OPTION_NETWORK_NAME: localnet}
        )
        db_set_command.add(ovnconst.ROW_LSP_TYPE, ovnconst.LSP_TYPE_LOCALNET)
        db_set_command.add(ovnconst.ROW_LSP_TAG_REQUEST, vlan)
        db_set_command.execute()

    def delete_network(self, network_id):
        network = self._execute(self.idl.ls_get(network_id))
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

        subnets = self._execute(self.idl.dhcp_options_list())
        for subnet in subnets:
            subnet_network_id = subnet.external_ids.get('ovirt_network_id')
            if subnet_network_id:
                if network_id == subnet_network_id:
                    self._execute(self.idl.dhcp_options_del(subnet.uuid))

        self._execute(self.idl.ls_del(network_id))

    def _get_localnet_port(self, network):
        for port in network.ports:
            if port.type == ovnconst.LSP_TYPE_LOCALNET:
                return port
        return None

    @PortMapper.map_to_rest
    def list_ports(self):
        ports_rows = self._execute(self.idl.lsp_list())
        return [self._get_network_port(port_row)
                for port_row in ports_rows
                if self._is_port_ovirt_controlled(port_row)]

    @PortMapper.map_to_rest
    def get_port(self, port_id):
        return self._get_network_port(self._get_port(port_id))

    def _get_network_port(self, lsp):
        ls = self._get_port_network(lsp)
        dhcp_options = self._get_subnet_from_port_id(str(lsp.uuid))
        lrp_name = lsp.options.get(ovnconst.LSP_OPTION_ROUTER_PORT)
        lrp = self._get_lrp(lrp_name) if lrp_name else None
        return NetworkPort(lsp=lsp, ls=ls, dhcp_options=dhcp_options, lrp=lrp)

    def _get_switch_port(self, port_id):
        port = self._execute(self.idl.lsp_get(port_id))
        if not port:
            raise ElementNotFoundError(
                'Port {port} does not exist'.format(port=port_id)
            )
        return port

    def _get_port(self, port_id):
        port = self._get_switch_port(port_id)
        if not self._is_port_ovirt_controlled(port):
            raise ValueError('Not an ovirt controller port')
        return port

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
        fixed_ips=None,
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
        fixed_ips=None,
    ):
        port = self._get_port(port_id)
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
        db_set_command = DbSetCommand(self.idl, ovnconst.TABLE_LSP, port.uuid)
        db_set_command.add(
            ovnconst.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_DEVICE_ID: device_id},
            device_id
        )
        db_set_command.add(
            ovnconst.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_NIC_NAME: name},
            name
        )
        db_set_command.add(
            ovnconst.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_DEVICE_OWNER: device_owner},
            device_owner
        )
        db_set_command.add(
            ovnconst.ROW_LSP_ENABLED,
            is_enabled,
            is_enabled
        )
        db_set_command.execute()

    def _update_port_address(self, port, network_id, mac=None):
        if port.type == ovnconst.LSP_TYPE_ROUTER:
            return
        mac = mac or ip_utils.get_port_mac(port)
        if mac:
            db_set_command = DbSetCommand(
                self.idl, ovnconst.TABLE_LSP, port.uuid
            )
            subnet_row = self._get_dhcp_by_network_id(network_id)
            if subnet_row:
                db_set_command.add(
                    ovnconst.ROW_LSP_DHCPV4_OPTIONS, subnet_row.uuid
                )
                mac += ' ' + ovnconst.LSP_ADDRESS_TYPE_DYNAMIC
            else:
                self._execute(self.idl.db_clear(
                    ovnconst.TABLE_LSP, port.uuid,
                    ovnconst.ROW_LSP_DHCPV4_OPTIONS
                ))

            db_set_command.add(ovnconst.ROW_LSP_ADDRESSES, [mac])
            db_set_command.execute()

    def _connect_port_to_router(
        self, port, router_port_name,
        router_id,
        name=None,
        is_enabled=True
     ):
        self._update_port_values(
            port=port,
            name=name,
            is_enabled=is_enabled,
            device_id=router_id,
            device_owner=PortMapper.DEVICE_OWNER_ROUTER
        )

        db_set_command = DbSetCommand(self.idl, ovnconst.TABLE_LSP, port.uuid)
        db_set_command.add(
            ovnconst.ROW_LSP_TYPE,
            ovnconst.LSP_TYPE_ROUTER,
        )
        db_set_command.add(
            ovnconst.ROW_LSP_OPTIONS,
            {ovnconst.LSP_OPTION_ROUTER_PORT: router_port_name},
        )
        db_set_command.add(
            ovnconst.ROW_LSP_ADDRESSES,
            [ovnconst.LSP_ADDRESS_TYPE_ROUTER]
        )
        db_set_command.execute()

        self._execute(self.idl.db_clear(
            ovnconst.TABLE_LSP, port.uuid, ovnconst.ROW_LSP_DHCPV4_OPTIONS
        ))

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
        port = self._execute(self.idl.lsp_add(
            network_id,
            name,
            may_exist=False
        ))
        port_id = str(port.uuid)
        self._execute(self.idl.db_set(
            ovnconst.TABLE_LSP,
            port_id,
            (ovnconst.ROW_LSP_NAME, str(port_id))
        ))
        return port

    def _get_dhcp_by_network_id(self, network_id):
        dhcps = self._execute(self.idl.dhcp_options_list())
        for row in dhcps:
            if str(row.external_ids.get(
                SubnetMapper.OVN_NETWORK_ID
            )) == str(network_id):
                return row

    def update_port_mac(self, port_id, macaddress):
        pass

    def delete_port(self, port_id):
        lsp = self._get_switch_port(port_id)
        if lsp.external_ids.get(PortMapper.OVN_DEVICE_OWNER) == \
                PortMapper.DEVICE_OWNER_ROUTER:
            raise ConflictError(
                'Port {port} cannot be deleted directly via the port API: '
                'has device owner network:router_interface'.format(
                    port=port_id
                )
            )
        self._delete_port(port_id)

    def _delete_port(self, port_id):
        self._execute(self.idl.lsp_del(port_id))

    @SubnetMapper.map_to_rest
    def list_subnets(self):
        return self._list_subnets()

    def _list_subnets(self):
        subnets = self._execute(self.idl.dhcp_options_list())
        return [
            subnet for subnet in subnets
            if SubnetMapper.OVN_NETWORK_ID in subnet.external_ids
        ]

    def _get_subnet(self, subnet_id):
        subnet = self._execute(self.idl.dhcp_options_get(subnet_id))
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

        self._execute(self.idl.db_set(
            ovnconst.TABLE_LS,
            network_id,
            (ovnconst.ROW_LS_OTHER_CONFIG, {NetworkMapper.OVN_SUBNET: cidr}),
        ))

        subnet = self._execute(self.idl.dhcp_options_add(cidr, **external_ids))
        self._execute(
            self.idl.dhcp_options_set_options(subnet.uuid, **options)
        )

        for port in network.ports:
            if port.type == ovnconst.LSP_TYPE_ROUTER:
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
        if network_id:
            if not self._execute(self.idl.ls_get(network_id)):
                raise SubnetConfigError(
                    'Unable to move subnet to network {network_id}. '
                    'The network does not exit.'
                    .format(network_id=network_id)
                )
            subnet_by_network = self._get_dhcp_by_network_id(network_id)
            if subnet_by_network and str(subnet_by_network.uuid) != subnet_id:
                raise SubnetConfigError(
                    'Unable to move subnet to network {network_id}. The'
                    ' network already has a subnet assigned'
                    .format(network_id=network_id)
                )

        db_set_command = DbSetCommand(
            self.idl, ovnconst.TABLE_DHCP_Options, subnet_id)

        if cidr:
            dhcp_server_ip = cidr.split('/', 1)[0]
            db_set_command.add(
                ovnconst.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_SERVER_ID: dhcp_server_ip}
            )
            db_set_command.add(ovnconst.ROW_DHCP_CIDR, cidr)
            self._execute(self.idl.db_set(
                ovnconst.TABLE_LS,
                network_id,
                (
                    ovnconst.ROW_LS_OTHER_CONFIG,
                    {NetworkMapper.OVN_SUBNET: cidr}
                ),
            ))

        db_set_command.add(
            ovnconst.ROW_DHCP_EXTERNAL_IDS,
            {SubnetMapper.OVN_NAME: name},
            name
        )
        db_set_command.add(
            ovnconst.ROW_DHCP_EXTERNAL_IDS,
            {SubnetMapper.OVN_NETWORK_ID: network_id},
            network_id
        )
        db_set_command.add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_GATEWAY: gateway},
            gateway
        )
        db_set_command.add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DNS_SERVER: dns},
            dns
        )
        db_set_command.add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time()}
        )
        db_set_command.add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac()}
        )
        db_set_command.execute()

        return self.get_subnet(subnet_id)

    def delete_subnet(self, subnet_id):
        subnet = self._get_subnet(subnet_id)
        router_id = self._get_subnet_gateway_router_id(subnet_id)
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
        self._execute(self.idl.dhcp_options_del(subnet_id))
        for port in network.ports:
            if port.type == ovnconst.LSP_TYPE_ROUTER:
                continue
            self._update_port_address(port, network_id=network_id)

    def _get_router(self, router_id):
        # TODO: LrGet is not yet implemented by ovsdbapp
        # patch pending: https://review.openstack.org/#/c/505517/
        # replace once patch is accepted
        try:
            return self.idl.lookup(ovnconst.TABLE_LR, router_id)
        except RowNotFound:
            raise ElementNotFoundError(
                'Router {router} does not exist'.format(router=router_id)
            )

    @RouterMapper.map_to_rest
    def get_router(self, router_id):
        return self._get_router(router_id)

    @RouterMapper.map_to_rest
    def list_routers(self):
        return self._execute(self.idl.lr_list())

    def _add_router(
        self, name, enabled, network_id=None, gateway_subnet_id=None,
        gateway_ip=None
    ):
        if network_id:
            self._validate_create_routing_lsp_by_subnet(
                network_id, gateway_subnet_id
            )
            self._validate_gateway_router_ip(network_id, gateway_ip)
            self._reserve_network_ip(network_id, gateway_ip)

        router = self._execute(self.idl.lr_add(
            router=name, may_exist=False, enabled=enabled
        ))
        router_id = str(router.uuid)

        if network_id:
            self._add_external_gateway_interface(
                router_id, network_id, gateway_subnet_id, gateway_ip
            )
            router = self._get_router(router_id)
        return router

    @RouterMapper.validate_add
    @RouterMapper.map_from_rest
    @RouterMapper.map_to_rest
    def add_router(
        self, name, enabled, network_id=None, gateway_subnet=None,
        gateway_ip=None
    ):
        return self._add_router(
            name, enabled, network_id, gateway_subnet, gateway_ip
        )

    @RouterMapper.validate_update
    @RouterMapper.map_from_rest
    def update_router(
        self, router_id, name, enabled, network_id=None,
        gateway_subnet=None, gateway_ip=None
    ):
        db_set_command = DbSetCommand(self.idl, ovnconst.TABLE_LR, router_id)
        db_set_command.add(ovnconst.ROW_LR_NAME, name, name)
        db_set_command.add(ovnconst.ROW_LR_ENABLED, enabled, enabled)
        db_set_command.execute()
        return self.get_router(router_id)

    def delete_router(self, router_id):
        self._execute(self.idl.lr_del(router_id))

    def _validate_router_exists(self, router_id):
        try:
            self.idl.lookup(ovnconst.TABLE_LR, router_id)
        except RowNotFound:
            raise ElementNotFoundError(
                'Router {router} does not exist'.format(router=router_id)
            )

    def _create_router_port_name(self, port_id):
        # LSP will reference this LRP by name (port parameter),
        # for convinience we will set the name to the id of the matching LSP
        # with an 'lrp' prefix.
        # We need the prefix due to an ovn issue in OVN lookup (bug pending)
        return ovnconst.ROUTER_PORT_NAME_PREFIX + str(port_id)

    def _lsp_id_by_lrp(self, lrp):
        return lrp.name[len(ovnconst.ROUTER_PORT_NAME_PREFIX):]

    def _get_subnet_gateway_router_id(self, subnet_id):
        subnet = self._get_subnet(subnet_id)
        return subnet.external_ids.get(SubnetMapper.OVN_GATEWAY_ROUTER_ID)

    def _set_subnet_gateway_router(self, subnet_id, router_id):
        self._execute(self.idl.db_set(
            ovnconst.TABLE_DHCP_Options,
            subnet_id,
            (
                ovnconst.ROW_DHCP_EXTERNAL_IDS,
                {SubnetMapper.OVN_GATEWAY_ROUTER_ID: router_id}
            )
        ))

    def _clear_subnet_gateway_router(self, subnet_id):
        self._execute(self.idl.db_remove(
            ovnconst.TABLE_DHCP_Options,
            subnet_id,
            ovnconst.ROW_DHCP_EXTERNAL_IDS,
            SubnetMapper.OVN_GATEWAY_ROUTER_ID
        ))

    def _validate_create_routing_lsp_by_subnet(
        self, network_id, subnet_id, router_id=None
    ):
        if not network_id:
            raise ElementNotFoundError(
                'Unable to add router interface. '
                'Subnet {subnet_id} does not belong to any network'
                .format(subnet_id=subnet_id)
            )

        network_subnet = self._get_dhcp_by_network_id(network_id)
        if not network_subnet or str(network_subnet.uuid) != subnet_id:
            raise BadRequestError(
                'Subnet {subnet_id} does not belong to network {network_id}'
                .format(subnet_id=subnet_id, network_id=network_id)
            )

        old_router_id = self._get_subnet_gateway_router_id(subnet_id)
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
                    'Can not add subnet {subnet} to router. Subnet is'
                    ' already connected to router {old_router}'.format(
                        subnet=subnet_id, router=router_id,
                        old_router=old_router_id
                    )
                )
        if router_id:
            self._validate_subnet_is_not_on_router(subnet_id, router_id)

    def _create_routing_lsp_by_subnet(self, subnet_id, router_id):
        subnet = self._get_subnet(subnet_id)
        network_id = subnet.external_ids.get(SubnetMapper.OVN_NETWORK_ID)
        self._validate_create_routing_lsp_by_subnet(
            network_id, subnet_id, router_id)
        lrp_ip = self._get_ip_from_subnet(subnet, network_id, router_id)
        port = self._create_port(ovnconst.ROUTER_SWITCH_PORT_NAME, network_id)
        lrp_name = self._create_router_port_name(port.uuid)
        self._connect_port_to_router(
            port,
            lrp_name,
            router_id,
            name=ovnconst.ROUTER_SWITCH_PORT_NAME,
            is_enabled=True
        )
        self._set_subnet_gateway_router(subnet_id, router_id)
        return (
            str(port.uuid),
            lrp_name,
            lrp_ip,
            network_id,
            ip_utils.random_mac()
        )

    def _validate_subnet_is_not_on_router(self, subnet_id, router_id):
        if self._is_subnet_on_router(router_id, subnet_id):
            raise BadRequestError(
                'Bad router request: Router already has a port on subnet'
                ' {subnet}'.format(subnet=subnet_id)
            )

    def _update_routing_lsp_by_port(self, port_id, router_id):
        port = self._get_switch_port(port_id)
        if port.type == ovnconst.LSP_TYPE_ROUTER:
            raise BadRequestError(
                'Can not add {port} to router. Port is already connected to a'
                ' router'.format(port=port_id)
            )
        subnet = self._get_subnet_from_port_id(port_id)
        if subnet:
            self._validate_subnet_is_not_on_router(subnet.uuid, router_id)
        lrp_ip = self._get_ip_from_port(port, router_id)
        lrp_name = self._create_router_port_name(port.uuid)
        mac = ip_utils.get_port_mac(port)
        self._connect_port_to_router(
            port,
            lrp_name,
            router_id,
            is_enabled=True
        )
        return (
            port_id, lrp_name, lrp_ip, str(self._get_port_network(port).uuid),
            mac
        )

    def _create_router_port(self, router_id, lrp_name, lrp_ip, mac):
        self._execute(self.idl.lrp_add(
            router=router_id, port=lrp_name,
            mac=mac,
            networks=[lrp_ip],
        ))

    def _is_ip_available_in_network(self, network_id, ip):
        network = self._get_network(network_id)
        if any(
            ip == ip_utils.get_port_dynamic_ip(port) or
            ip == ip_utils.get_port_static_ip(port)
            for port in network.ports
        ):
            return False
        exclude_ips = self._get_network_exclude_ips(network)
        return ip not in exclude_ips

    def _validate_gateway_router_ip(self, network_id, gateway_ip):
        if not self._is_ip_available_in_network(network_id, gateway_ip):
            raise RestDataError(
                'ip_address {ip_address} is already used on the external '
                'network {network_id}'.format(
                    ip_address=gateway_ip,
                    network_id=network_id
                )
            )

    def _get_network_exclude_ips(self, network):
        exclude_values = network.other_config.get(
            ovnconst.LS_OPTION_EXCLUDE_IPS
        )
        # TODO: should we care about IP ranges? we do not use them, but
        # what if someone else will?
        # lets raise for now
        result = []
        for exclude_value in exclude_values.split():
            if ovnconst.LS_EXCLUDED_IP_DELIMITER in exclude_value:
                raise NotImplementedError(
                    'Handling of ip ranges not yet implemented'
                )
            result.append(exclude_value)
        return result

    def _reserve_network_ip(self, network_id, gateway_ip):
        exclude_values = self._get_network(network_id).other_config.get(
            ovnconst.LS_OPTION_EXCLUDE_IPS, {}
        )
        new_values = (
            (exclude_values + ' ') if exclude_values else str()
         ) + gateway_ip

        self._execute(self.idl.db_set(
            ovnconst.TABLE_LS,
            network_id,
            (
                ovnconst.ROW_LS_OTHER_CONFIG,
                {ovnconst.LS_OPTION_EXCLUDE_IPS: new_values}
            )
        ))

    def _add_external_gateway_interface(
        self, router_id, network_id, gateway_subnet_id, gateway_ip
    ):
        port_ip = '{ip}/{netmask}'.format(
            ip=gateway_ip,
            netmask=ip_utils.get_mask_from_subnet(
                self._get_subnet(gateway_subnet_id)
            )
        )

        port = self._create_port(ovnconst.ROUTER_SWITCH_PORT_NAME, network_id)
        lrp_name = self._create_router_port_name(port.uuid)
        self._create_router_port(
            router_id, lrp_name, port_ip, ip_utils.random_mac()
        )
        self._connect_port_to_router(
            port,
            lrp_name,
            router_id,
            name=ovnconst.ROUTER_SWITCH_PORT_NAME,
            is_enabled=True
        )

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
        validate.attach_network_to_router_by_subnet(
            subnet, network_id, router_id
        )
        subnet_gateway = subnet.options.get('router')
        subnet_netmask = ip_utils.get_mask_from_subnet(subnet)
        return '{ip}/{netmask}'.format(
            ip=subnet_gateway, netmask=subnet_netmask
        )

    def _get_ip_from_addresses(self, addresses):
        if not addresses:
            return None
        address_parts = addresses[0].split(' ')
        return address_parts[1] if len(address_parts) > 1 else None

    def _validate_port_ip_for_router(self, port_ip, port, router_id):
        if not port_ip:
            raise ElementNotFoundError(
                'Unable to attach port {port_id} to router '
                '{router_id}. '
                'Attaching by port requires the port to have '
                'an ip from subnet assigned.'
                .format(port_id=port.uuid, router_id=router_id)
            )

    def _get_ip_from_port(self, port, router_id):
        port_ip = ip_utils.get_port_dynamic_ip(port)
        self._validate_port_ip_for_router(port_ip, port, router_id)
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
        lrp_name = lsp.options.get(ovnconst.LSP_OPTION_ROUTER_PORT)
        if not lrp_name:
            raise BadRequestError(
                'Port {port} is not connected to a router'
                .format(port=port_id)
            )
        subnet = self._get_subnet_from_port_id(port_id)
        lrp = self._get_lrp(lrp_name)
        network_id = str(self._get_port_network(lsp).uuid)
        lr = self._get_router(router_id)
        self._delete_router_interface(
            router_id, port_id, lrp, network_id, lsp, lr
        )
        if subnet and not self._is_subnet_on_router(router_id, subnet.uuid):
            self._clear_subnet_gateway_router(str(subnet.uuid))

    def _is_subnet_on_router(self, router_id, subnet_id):
        lr = self._get_router(router_id)
        for lrp in lr.ports:
            lsp_id = self._lsp_id_by_lrp(lrp)
            lrp_subnet = self._get_subnet_from_port_id(lsp_id)
            if str(lrp_subnet.uuid) == subnet_id:
                return True
        return False

    def _get_subnet_from_port_id(self, port_id):
        for subnet in self._list_subnets():
            network_id = subnet.external_ids[SubnetMapper.OVN_NETWORK_ID]
            network = self._get_network(network_id)
            if any(port.name == port_id for port in network.ports):
                return subnet

    def _delete_router_interface(
        self, router_id, port_id, lrp, network_id, lsp, lr
    ):
        if lrp not in lr.ports:
            raise BadRequestError(
                'Port {port} is not connected to router {router}'
                .format(port=port_id, router=router_id)
            )
        self._execute(self.idl.lrp_del(str(lrp.uuid)))
        self._delete_port(port_id)

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
            return self.idl.lookup(ovnconst.TABLE_LRP, lrp)
        except RowNotFound:
            raise ElementNotFoundError(
                'Logical router port {port} does not exist'
                .format(port=lrp)
            )

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()
