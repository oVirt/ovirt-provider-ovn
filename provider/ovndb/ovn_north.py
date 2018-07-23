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

import uuid

import ovs.stream
import ovsdbapp.backend.ovs_idl.connection
from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound
from ovsdbapp.schema.ovn_northbound.impl_idl import OvnNbApiIdlImpl

import ovndb.constants as ovnconst
import ovndb.ip as ip_utils
import ovndb.validation as validate

from handlers.base_handler import BadRequestError
from handlers.base_handler import ElementNotFoundError

from ovirt_provider_config_common import ovn_remote
from ovirt_provider_config_common import dhcp_lease_time
from ovirt_provider_config_common import dhcp_server_mac
from ovirt_provider_config_common import dhcp_enable_mtu
from ovirt_provider_config_common import dhcp_mtu
from ovirt_provider_config_common import is_ovn_remote_ssl
from ovirt_provider_config_common import ovs_version_29
from ovirt_provider_config_common import ssl_key_file
from ovirt_provider_config_common import ssl_cacert_file
from ovirt_provider_config_common import ssl_cert_file

from ovndb.db_set_command import DbSetCommand
from ovndb.ovn_north_atomics import OvnNorthAtomics
from ovndb.ovn_north_mappers import AddRouterInterfaceMapper
from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import Network
from ovndb.ovn_north_mappers import NetworkPort
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import RemoveRouterInterfaceMapper
from ovndb.ovn_north_mappers import RestDataError
from ovndb.ovn_north_mappers import Router
from ovndb.ovn_north_mappers import RouterInterface
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
        self.atomics = OvnNorthAtomics(self.idl)

    def _configure_ssl_connection(self):
        if is_ovn_remote_ssl():
            ovs.stream.Stream.ssl_set_private_key_file(ssl_key_file())
            ovs.stream.Stream.ssl_set_certificate_file(ssl_cert_file())
            ovs.stream.Stream.ssl_set_ca_cert_file(ssl_cacert_file())

    def _execute(self, command):
        try:
            return command.execute(check_error=True)
        except (ValueError, TypeError) as e:
            raise BadRequestError(e)
        except RowNotFound as e:
            raise ElementNotFoundError(e)

    def close(self):
        self.ovsidl.close()

    # TODO: could this be moved to ovsdbapp?
    def _get_port_network(self, port):
        networks = self.atomics.list_ls()
        return next(network for network in networks if port in network.ports)

    def _is_port_ovirt_controlled(self, port_row):
        return PortMapper.OVN_NIC_NAME in port_row.external_ids

    @NetworkMapper.map_to_rest
    def list_networks(self):
        ls_rows = self.atomics.list_ls()
        return [self._get_network(ls) for ls in ls_rows]

    def _get_network(self, ls):
        return Network(
            ls=ls,
            localnet_lsp=self._get_localnet_lsp(ls)
        )

    @NetworkMapper.map_to_rest
    def get_network(self, network_id):
        return self._get_network(
            self.atomics.get_ls(ls_id=network_id)
        )

    @NetworkMapper.validate_add
    @NetworkMapper.map_from_rest
    @NetworkMapper.map_to_rest
    def add_network(self, name, localnet=None, vlan=None, mtu=None):
        # TODO: ovirt allows multiple networks with the same name
        # in oVirt, but OVS does not (may_exist=False will cause early fail)
        if localnet:
            return self._add_localnet_network(name, localnet, vlan, mtu)
        else:
            return self._get_network(self._create_network(name, mtu))

    def _create_network(self, name, mtu=None):
        external_ids_dict = {NetworkMapper.OVN_NETWORK_NAME: name}
        if mtu is not None:
            external_ids_dict[NetworkMapper.OVN_MTU] = str(mtu)
        return self._execute(
            self.idl.ls_add(
                switch='ovirt-{name}-{gen_id}'.format(
                    name=name, gen_id=uuid.uuid4()
                ),
                may_exist=False,
                external_ids=self._generate_external_ids(
                    {},
                    **external_ids_dict
                )
            )
        )

    @staticmethod
    def _generate_external_ids(current_external_ids, **kwargs):
        return dict(current_external_ids, **kwargs)

    def _add_localnet_network(self, name, localnet, vlan, mtu):
        network = self._create_network(name, mtu)
        localnet_port = self._create_port(
            ovnconst.LOCALNET_SWITCH_PORT_NAME, str(network.uuid)
        )
        self._set_port_localnet_values(localnet_port, localnet, vlan)
        updated_network = self.atomics.get_ls(ls_id=str(network.uuid))
        return self._get_network(updated_network)

    @NetworkMapper.validate_update
    @NetworkMapper.map_from_rest
    def update_network(
            self,
            network_id,
            name,
            localnet=None,
            vlan=None,
            mtu=None
    ):
        self._update_network_data(network_id, name, mtu)
        self._update_localnet_on_network(network_id, localnet, vlan)
        return self.get_network(network_id)

    def _update_network_data(self, network_id, name, mtu):
        current_external_ids = self.atomics.get_ls(
            ls_id=network_id
        ).external_ids

        relevant_external_ids = {NetworkMapper.OVN_NETWORK_NAME: name}
        if mtu is not None:
            relevant_external_ids[NetworkMapper.OVN_MTU] = str(mtu)
        new_external_ids = self._generate_external_ids(
            current_external_ids,
            **relevant_external_ids
        )
        DbSetCommand(
            self.idl, ovnconst.TABLE_LS, network_id
        ).add(
            ovnconst.ROW_LS_EXTERNAL_IDS,
            new_external_ids
        ).execute()
        if mtu:
            self._update_networks_mtu(network_id, mtu)

    def _update_localnet_on_network(self, network_id, localnet, vlan):
        network = self.atomics.get_ls(ls_id=network_id)
        localnet_port = self._get_localnet_lsp(network)
        if localnet:
            if not localnet_port:
                localnet_port = self._create_port(
                    ovnconst.LOCALNET_SWITCH_PORT_NAME, str(network.uuid))
            self._set_port_localnet_values(localnet_port, localnet, vlan)
        elif localnet_port:
            self._delete_port(str(localnet_port.uuid))

    def _set_port_localnet_values(self, port, localnet, vlan):
        DbSetCommand(
            self.idl, ovnconst.TABLE_LSP, port.uuid
        ).add(
            ovnconst.ROW_LSP_ADDRESSES,
            [ovnconst.LSP_ADDRESS_TYPE_UNKNOWN]
        ).add(
            ovnconst.ROW_LSP_OPTIONS,
            {ovnconst.LSP_OPTION_NETWORK_NAME: localnet}
        ).add(
            ovnconst.ROW_LSP_TYPE, ovnconst.LSP_TYPE_LOCALNET
        ).add(ovnconst.ROW_LSP_TAG_REQUEST, vlan).execute()

    def _update_networks_mtu(self, network_id, mtu):
        subnet = self.atomics.get_dhcp(ls_id=network_id)
        if subnet and subnet.options.get(NetworkMapper.REST_MTU) != mtu:
            DbSetCommand(
                self.idl, ovnconst.TABLE_DHCP_Options, subnet.uuid
            ).add(
                ovnconst.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_MTU: str(mtu)}
            ).execute()

    def delete_network(self, network_id):
        network = self.atomics.get_ls(ls_id=network_id)
        if not network:
            raise RestDataError('Network %s does not exist' % network_id)
        validate.network_has_no_ports(
            network_id, network.ports,
            self._get_localnet_lsp(network)
        )

        subnets = self.atomics.list_dhcp()
        for subnet in subnets:
            subnet_network_id = subnet.external_ids.get('ovirt_network_id')
            if subnet_network_id:
                if network_id == subnet_network_id:
                    self._execute(self.idl.dhcp_options_del(subnet.uuid))

        self._execute(self.idl.ls_del(network_id))

    def _get_localnet_lsp(self, ls):
        for lsp in ls.ports:
            if lsp.type == ovnconst.LSP_TYPE_LOCALNET:
                return lsp
        return None

    @PortMapper.map_to_rest
    def list_ports(self):
        ports_rows = self.atomics.list_lsp()
        return [self._get_network_port(port_row)
                for port_row in ports_rows
                if self._is_port_ovirt_controlled(port_row)]

    @PortMapper.map_to_rest
    def get_port(self, port_id):
        return self._get_network_port(
            self.atomics.get_lsp(ovirt_lsp_id=port_id)
        )

    def _get_network_port(self, lsp):
        ls = self._get_port_network(lsp)
        dhcp_options = self.atomics.get_dhcp(lsp_id=str(lsp.uuid))
        lrp_name = lsp.options.get(ovnconst.LSP_OPTION_ROUTER_PORT)
        lrp = self.atomics.get_lrp(lrp_name=lrp_name) if lrp_name else None
        return NetworkPort(lsp=lsp, ls=ls, dhcp_options=dhcp_options, lrp=lrp)

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
        binding_host=None,
    ):
        port = self._create_port(name, network_id)
        self._update_port_values(
            port, name, is_enabled, device_id, device_owner, binding_host
        )
        mac = mac or ip_utils.random_unique_mac(
            self.atomics.list_lsp(),
            self.atomics.list_lrp()
        )
        self._update_port_address(
            port, network_id=network_id, mac=mac, fixed_ips=fixed_ips)
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
        binding_host=None,
    ):
        port = self.atomics.get_lsp(ovirt_lsp_id=port_id)
        network_id = self._get_validated_port_network_id(port, network_id)
        self._update_port_values(
            port, name, is_enabled, device_id, device_owner, binding_host
        )
        self._update_port_address(
            port, network_id=network_id, mac=mac, fixed_ips=fixed_ips)
        return self.get_port(port_id)

    def _update_lsp_bound_lrp(self, port_id, fixed_ips):
        if not fixed_ips:
            return
        lrp = self.atomics.get_lrp(lsp_id=port_id)
        subnet = self.atomics.get_dhcp(lsp_id=port_id)
        validate.fixed_ip_matches_port_subnet(fixed_ips, subnet)

        new_lrp_ip = '{ip}/{netmask}'.format(
            ip=fixed_ips[0].get(PortMapper.REST_PORT_IP_ADDRESS),
            netmask=ip_utils.get_mask_from_subnet(subnet)
        )

        self._execute(self.idl.db_set(
            ovnconst.TABLE_LRP,
            str(lrp.uuid),
            (ovnconst.ROW_LRP_NETWORKS, new_lrp_ip)
        ))

    def _update_port_values(
        self, port, name=None, is_enabled=None, device_id=None,
        device_owner=None, binding_host=None,
    ):
        # TODO(add transaction): setting of the individual values should
        # one day be done in a transaction:
        #   txn = Transaction(self.idl, self.ovsdb_connection)
        #   txn.add(<command>)
        #   ...
        #   txn.commit()
        # The ovsdbapp transactions seem to have synchronization issues at the
        # moment, hence we'll be using individual transactions for now.
        DbSetCommand(
            self.idl, ovnconst.TABLE_LSP, port.uuid
        ).add(
            ovnconst.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_DEVICE_ID: device_id},
            device_id
        ).add(
            ovnconst.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_NIC_NAME: name},
            name
        ).add(
            ovnconst.ROW_LSP_EXTERNAL_IDS,
            {PortMapper.OVN_DEVICE_OWNER: device_owner},
            device_owner
        ).add(
            ovnconst.ROW_LSP_ENABLED,
            is_enabled,
            is_enabled
        ).add(
            ovnconst.ROW_LSP_OPTIONS,
            {PortMapper.OVN_REQUESTED_CHASSIS: binding_host},
            ovs_version_29() and binding_host
        ).execute()

    def _update_port_address(self, port, network_id, mac=None, fixed_ips=None):
        if port.type == ovnconst.LSP_TYPE_ROUTER:
            self._update_lsp_bound_lrp(str(port.uuid), fixed_ips)
            return
        mac = mac or ip_utils.get_port_mac(port)
        subnet = self.atomics.get_dhcp(ls_id=network_id)
        validate.fixed_ip_matches_port_subnet(fixed_ips, subnet)
        if mac:
            db_set_command = DbSetCommand(
                self.idl, ovnconst.TABLE_LSP, port.uuid
            )
            if subnet:
                db_set_command.add(
                    ovnconst.ROW_LSP_DHCPV4_OPTIONS, subnet.uuid
                )
                mac += ' ' + self._get_port_addesses_suffix(
                    network_id, fixed_ips)
            else:
                self._execute(self.idl.db_clear(
                    ovnconst.TABLE_LSP, port.uuid,
                    ovnconst.ROW_LSP_DHCPV4_OPTIONS
                ))

            db_set_command.add(ovnconst.ROW_LSP_ADDRESSES, [mac]).execute()

    def _get_port_addesses_suffix(self, network_id, fixed_ips):
        if not fixed_ips:
            return ovnconst.LSP_ADDRESS_TYPE_DYNAMIC

        # Only one fixed ip is supported for now
        # OVN does allow multiple IP's, so support for multiple fixed ips
        # can be added
        # TODO: handle multiple fixed_ips
        fixed_ip = fixed_ips[0]
        ip = fixed_ip.get(PortMapper.REST_PORT_IP_ADDRESS)
        if not ip:
            return ovnconst.LSP_ADDRESS_TYPE_DYNAMIC
        validate.ip_available_in_network(
            self.atomics.get_ls(ls_id=network_id), ip
        )
        return ip

    def _connect_port_to_router(
        self, port, router_port_name,
        router_id,
        name=None,
        is_enabled=True,
        is_external_gateway=False,
     ):
        self._update_port_values(
            port=port,
            name=name,
            is_enabled=is_enabled,
            device_id=router_id,
            device_owner=(
                PortMapper.DEVICE_OWNER_ROUTER_GATEWAY
                if is_external_gateway else
                PortMapper.DEVICE_OWNER_ROUTER
            )
        )

        DbSetCommand(
            self.idl, ovnconst.TABLE_LSP, port.uuid
        ).add(
            ovnconst.ROW_LSP_TYPE,
            ovnconst.LSP_TYPE_ROUTER,
        ).add(
            ovnconst.ROW_LSP_OPTIONS,
            {ovnconst.LSP_OPTION_ROUTER_PORT: router_port_name},
        ).add(
            ovnconst.ROW_LSP_ADDRESSES,
            [ovnconst.LSP_ADDRESS_TYPE_ROUTER]
        ).execute()

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

    def update_port_mac(self, port_id, macaddress):
        pass

    def delete_port(self, port_id):
        lsp = self.atomics.get_lsp(lsp_id=port_id)
        validate.port_is_not_connected_to_router(lsp)
        self._delete_port(port_id)

    def _delete_port(self, port_id):
        self._execute(self.idl.lsp_del(port_id))

    @SubnetMapper.map_to_rest
    def list_subnets(self):
        return self.atomics.list_dhcp()

    @SubnetMapper.map_to_rest
    def get_subnet(self, subnet_id):
        return self.atomics.get_dhcp(dhcp_id=subnet_id)

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
            network = self.atomics.get_ls(ls_id=network_id)
        except ElementNotFoundError:
            raise SubnetConfigError('Subnet can not be created, network {}'
                                    ' does not exist'.format(network_id))

        if self.atomics.get_dhcp(ls_id=network_id):
            raise SubnetConfigError('Unable to create more than one subnet'
                                    ' for network {}'.format(network_id))

        external_ids = {
            SubnetMapper.OVN_NETWORK_ID: network_id
        }
        if name:
            external_ids[SubnetMapper.OVN_NAME] = name

        dhcp_server_ip = cidr.split('/', 1)[0]

        options = {
            SubnetMapper.OVN_DHCP_SERVER_ID: dhcp_server_ip,
            SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac(),
            SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time(),
        }
        if gateway:
            options[SubnetMapper.OVN_GATEWAY] = gateway
        network_mtu = network.external_ids.get(SubnetMapper.OVN_DHCP_MTU)
        if network_mtu:
            options[SubnetMapper.OVN_DHCP_MTU] = network_mtu
        elif dhcp_enable_mtu():
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
            if self._is_port_address_value_static(port.type):
                continue
            self._update_port_address(port, network_id=network_id)

        return self.get_subnet(subnet.uuid)

    @SubnetMapper.validate_update
    @SubnetMapper.map_from_rest
    def update_subnet(
        self,
        subnet_id,
        name=None,
        gateway=None,
        dns=None,
    ):
        DbSetCommand(
            self.idl, ovnconst.TABLE_DHCP_Options, subnet_id
        ).add(
            ovnconst.ROW_DHCP_EXTERNAL_IDS,
            {SubnetMapper.OVN_NAME: name},
            name
        ).add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_GATEWAY: gateway},
            gateway
        ).add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DNS_SERVER: dns},
            dns
        ).add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time()}
        ).add(
            ovnconst.ROW_DHCP_OPTIONS,
            {SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac()}
        ).execute()

        return self.get_subnet(subnet_id)

    def delete_subnet(self, subnet_id):
        subnet = self.atomics.get_dhcp(dhcp_id=subnet_id)
        validate.subnet_not_connected_to_router(
            self._get_subnet_gateway_router_id(subnet),
            subnet_id
        )
        network_id = subnet.external_ids.get(
            SubnetMapper.OVN_NETWORK_ID
        )
        network = self.atomics.get_ls(ls_id=network_id)
        self._execute(self.idl.dhcp_options_del(subnet_id))
        for port in network.ports:
            if self._is_port_address_value_static(port.type):
                continue
            self._update_port_address(port, network_id=network_id)

    @RouterMapper.map_to_rest
    def get_router(self, router_id):
        return self._get_router_from_lr(self.atomics.get_lr(lr_id=router_id))

    def _get_router_from_lr(self, lr):
        gw_port_id = lr.external_ids.get(RouterMapper.OVN_ROUTER_GATEWAY_PORT)
        if not gw_port_id:
            return Router(
                lr=lr, ext_gw_ls_id=None, ext_gw_dhcp_options_id=None,
                gw_ip=None
            )
        gw_port = self._execute(self.idl.lsp_get(gw_port_id))
        ls = self._get_port_network(gw_port)
        ls_id = str(ls.uuid)

        dhcp_options = self.atomics.get_dhcp(ls_id=ls_id)
        lrp = self.atomics.get_lrp(lsp_id=gw_port_id)
        gw_ip = ip_utils.get_ip_from_cidr(lrp.networks[0])

        return Router(
            lr=lr, ext_gw_ls_id=ls_id,
            ext_gw_dhcp_options_id=str(dhcp_options.uuid), gw_ip=gw_ip
        )

    @RouterMapper.map_to_rest
    def list_routers(self):
        return [
            self._get_router_from_lr(lr)
            for lr in self._execute(self.idl.lr_list())
        ]

    def _add_router(
        self, name, enabled, network_id=None, gateway_subnet_id=None,
        gateway_ip=None, routes=None
    ):
        self._validate_external_gateway(
            gateway_ip, gateway_subnet_id, network_id
        )
        validate.no_default_gateway_in_routes(network_id is not None, routes)
        self._reserve_network_ip(network_id, gateway_ip)

        router = self._execute(self.idl.lr_add(
            router=name, may_exist=False, enabled=enabled
        ))
        router_id = str(router.uuid)

        self._add_external_gateway_to_router(
            gateway_ip, gateway_subnet_id, network_id, router_id
        )
        self._add_routes_to_router(router_id, routes)
        router = self.atomics.get_lr(lr_id=router_id)
        return Router(
            lr=router, ext_gw_ls_id=network_id,
            ext_gw_dhcp_options_id=gateway_subnet_id, gw_ip=gateway_ip
        )

    def _add_routes_to_router(self, router_id, routes):
        if not routes:
            return
        for route in routes:
            self.atomics.add_route(
                lrp_id=router_id,
                prefix=route[RouterMapper.REST_ROUTER_DESTINATION],
                nexthop=route[RouterMapper.REST_ROUTER_NEXTHOP]
            )

    def _add_external_gateway_to_router(
        self, gateway_ip, gateway_subnet_id, network_id, router_id
    ):
        if network_id:
            self._add_external_gateway_interface(
                router_id, network_id, gateway_subnet_id, gateway_ip
            )
            subnet = self.atomics.get_dhcp(dhcp_id=gateway_subnet_id)
            self.atomics.add_route(
                lrp_id=router_id,
                prefix=ovnconst.DEFAULT_ROUTE,
                nexthop=subnet.options.get('router')
            )

    def _validate_external_gateway(
        self, gateway_ip, gateway_subnet_id, network_id
    ):
        if network_id:
            self._validate_create_routing_lsp_by_subnet(
                network_id, gateway_subnet_id, is_external_gateway=True
            )
            validate.ip_available_in_network(
                self.atomics.get_ls(ls_id=network_id), gateway_ip
            )

    @RouterMapper.validate_add
    @RouterMapper.map_from_rest
    @RouterMapper.map_to_rest
    def add_router(
        self, name, enabled, network_id=None, gateway_subnet=None,
        gateway_ip=None, routes=None
    ):
        return self._add_router(
            name, enabled, network_id, gateway_subnet, gateway_ip, routes
        )

    @RouterMapper.validate_update
    @RouterMapper.map_from_rest
    def update_router(
        self, router_id, name, enabled, network_id=None,
        gateway_subnet=None, gateway_ip=None, routes=None
    ):
        self._validate_external_gateway(
            gateway_ip, gateway_subnet, network_id
        )
        lr = self.atomics.get_lr(lr_id=router_id)

        if routes is not None:
            # NOTE: we only validate default route and external gateway being
            # both present for the rest difinition. We overwrite existing
            # external gateway if a new default route is specified in rest
            # request
            validate.no_default_gateway_in_routes(network_id, routes)

            added_routes, removed_routes = ip_utils.diff_routes(
                routes, lr.static_routes
            )

            for destination in removed_routes:
                self.atomics.remove_static_route(lr, destination)
            for destination in added_routes:
                self.atomics.add_route(
                    router_id, destination, added_routes[destination]
                )

        existing_gw_lsp_id = lr.external_ids.get(
            RouterMapper.OVN_ROUTER_GATEWAY_PORT
        )
        is_updated_gw_different_than_existing = \
            self._is_updated_gw_different_than_existing(
                lr, gateway_subnet, gateway_ip, existing_gw_lsp_id
            )
        if is_updated_gw_different_than_existing:
            self._delete_router_interface_by_port(
                router_id, existing_gw_lsp_id
            )
        self._reserve_network_ip(network_id, gateway_ip)

        DbSetCommand(self.idl, ovnconst.TABLE_LR, router_id).add(
            ovnconst.ROW_LR_NAME, name, name
        ).add(ovnconst.ROW_LR_ENABLED, enabled, enabled).execute()

        should_external_gw_be_added = (
            is_updated_gw_different_than_existing or
            (gateway_subnet and not existing_gw_lsp_id)
        )

        if should_external_gw_be_added:
            self._add_external_gateway_to_router(
                gateway_ip, gateway_subnet, network_id, router_id
            )
        return self.get_router(router_id)

    def _is_updated_gw_different_than_existing(
        self, lr, new_gateway_subnet, new_gateway_ip, existing_lr_gw_lsp_id
    ):
        if not new_gateway_subnet:
            return False
        if not existing_lr_gw_lsp_id:
            return False

        existing_subnet = self.atomics.get_dhcp(lsp_id=existing_lr_gw_lsp_id)
        existing_ip = ip_utils.get_port_ip(
            self.atomics.get_lsp(lsp_id=existing_lr_gw_lsp_id),
            self.atomics.get_lrp(lsp_id=existing_lr_gw_lsp_id)
        )

        return (
            new_gateway_subnet != str(existing_subnet.uuid) or
            new_gateway_ip != existing_ip
        )

    def delete_router(self, router_id):
        existing_gw_lsp_id = self.atomics.get_lr(
            lr_id=router_id).external_ids.get(
                RouterMapper.OVN_ROUTER_GATEWAY_PORT
            )
        if existing_gw_lsp_id:
            self._delete_router_interface_by_port(
                router_id, existing_gw_lsp_id
            )

        validate.router_has_no_ports(self.atomics.get_lr(lr_id=router_id))
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

    def _get_subnet_gateway_router_id(self, subnet):
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
        self, network_id, subnet_id, router_id=None, is_external_gateway=False
    ):
        existing_subnet_for_network = self.atomics.get_dhcp(ls_id=network_id)
        existing_router_for_subnet = self._get_subnet_gateway_router_id(
            existing_subnet_for_network
        )
        validate.create_routing_lsp_by_subnet(
            network_id, subnet_id, existing_subnet_for_network,
            existing_router_for_subnet, router_id,
            is_external_gateway=is_external_gateway
        )
        if router_id:
            self._validate_subnet_is_not_on_router(subnet_id, router_id)

    def _create_routing_lsp_by_subnet(self, subnet_id, router_id):
        subnet = self.atomics.get_dhcp(dhcp_id=subnet_id)
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
            ip_utils.random_unique_mac(
                self.atomics.list_lsp(),
                self.atomics.list_lrp()
            )
        )

    def _validate_subnet_is_not_on_router(self, subnet_id, router_id):
        if self._is_subnet_on_router(router_id, subnet_id):
            raise BadRequestError(
                'Bad router request: Router already has a port on subnet'
                ' {subnet}'.format(subnet=subnet_id)
            )

    def _update_routing_lsp_by_port(self, port_id, router_id):
        port = self.atomics.get_lsp(lsp_id=port_id)
        if port.type == ovnconst.LSP_TYPE_ROUTER:
            raise BadRequestError(
                'Can not add {port} to router. Port is already connected to a'
                ' router'.format(port=port_id)
            )
        subnet = self.atomics.get_dhcp(lsp_id=port_id)
        if subnet:
            self._validate_subnet_is_not_on_router(subnet.uuid, router_id)

        lrp_ipmask = self._get_ip_netmask_for_lrp(port, router_id)
        lrp_name = self._create_router_port_name(port.uuid)
        mac = ip_utils.get_port_mac(port)
        self._connect_port_to_router(
            port,
            lrp_name,
            router_id,
            is_enabled=True
        )
        return (
            port_id, lrp_name, lrp_ipmask,
            str(self._get_port_network(port).uuid), mac
        )

    def _get_ip_netmask_for_lrp(self, lsp, lr_id):
        lsp_ip = ip_utils.get_port_ip(lsp)
        validate.port_ip_for_router(lsp_ip, lsp, lr_id)

        ls_cidr = self._get_port_network(lsp).other_config.get(
            NetworkMapper.OVN_SUBNET
        )
        validate.port_added_to_lr_must_have_subnet(
            ls_cidr, str(lsp.uuid), lr_id
        )
        return ip_utils.get_ip_with_mask(ip=lsp_ip, cidr=ls_cidr)

    def _reserve_network_ip(self, network_id, gateway_ip):
        if not network_id:
            return
        exclude_values = self.atomics.get_ls(
            ls_id=network_id
        ).other_config.get(
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

    def _release_network_ip(self, network_id, ip):
        exclude_values = self.atomics.get_ls(
            ls_id=network_id
        ).other_config.get(
            ovnconst.LS_OPTION_EXCLUDE_IPS, ''
        )
        values = exclude_values.split()
        values.remove(ip)

        if values:
            self._execute(self.idl.db_set(
                ovnconst.TABLE_LS,
                network_id,
                (
                    ovnconst.ROW_LS_OTHER_CONFIG,
                    {ovnconst.LS_OPTION_EXCLUDE_IPS: ' '.join(values)}
                )
            ))
        else:
            self._execute(self.idl.db_remove(
                ovnconst.TABLE_LS,
                network_id,
                ovnconst.ROW_LS_OTHER_CONFIG,
                ovnconst.LS_OPTION_EXCLUDE_IPS
            ))

    def _add_external_gateway_interface(
        self, router_id, network_id, gateway_subnet_id, gateway_ip
    ):
        port_ip = '{ip}/{netmask}'.format(
            ip=gateway_ip,
            netmask=ip_utils.get_mask_from_subnet(
                self.atomics.get_dhcp(dhcp_id=gateway_subnet_id)
            )
        )

        port = self._create_port(ovnconst.ROUTER_SWITCH_PORT_NAME, network_id)
        lrp_name = self._create_router_port_name(port.uuid)
        mac = ip_utils.random_unique_mac(
            self.atomics.list_lsp(),
            self.atomics.list_lrp()
        )
        self.atomics.add_lrp(router_id, lrp_name, mac=mac, lrp_ip=port_ip)
        self._connect_port_to_router(
            port,
            lrp_name,
            router_id,
            name=ovnconst.ROUTER_SWITCH_PORT_NAME,
            is_enabled=True,
            is_external_gateway=True,
        )

        DbSetCommand(self.idl, ovnconst.TABLE_LR, router_id).add(
            ovnconst.ROW_LR_EXTERNAL_IDS,
            {
                RouterMapper.OVN_ROUTER_GATEWAY_PORT: str(port.uuid),
            }
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
            subnet_id = str(self.atomics.get_dhcp(ls_id=network_id).uuid)
        self.atomics.add_lrp(router_id, lrp_name, mac=mac, lrp_ip=lrp_ip)
        return RouterInterface(
            id=router_id,
            ls_id=network_id,
            lsp_id=port_id,
            dhcp_options_id=subnet_id,
        )

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

    @RemoveRouterInterfaceMapper.validate_update
    @RemoveRouterInterfaceMapper.map_from_rest
    @RemoveRouterInterfaceMapper.map_to_rest
    def delete_router_interface(self, router_id, subnet_id=None, port_id=None):
        if subnet_id and port_id:
            return self._delete_router_interface_by_subnet_and_port(
                router_id, subnet_id, port_id
            )
        elif subnet_id:
            return self._delete_router_interface_by_subnet(
                router_id, subnet_id
            )
        else:
            return self._delete_router_interface_by_port(router_id, port_id)

    def _delete_router_interface_by_port(self, router_id, port_id):
        lsp = self.atomics.get_lsp(lsp_id=port_id)
        validate.port_is_connected_to_router(lsp)

        subnet = self.atomics.get_dhcp(lsp_id=port_id)
        subnet_id = str(subnet.uuid)
        lrp = self.atomics.get_lrp(lsp_id=port_id)
        lrp_ip = ip_utils.get_ip_from_cidr(lrp.networks[0])
        lr = self.atomics.get_lr(lr_id=router_id)
        ls_id = str(self.atomics.get_ls(dhcp=subnet).uuid)

        is_subnet_gateway = (
            subnet and
            self._is_subnet_on_router(router_id, subnet_id) and
            lrp_ip == subnet.options.get(SubnetMapper.OVN_GATEWAY, None)
        )
        self._delete_router_interface(router_id, port_id, lrp, lr)
        if is_subnet_gateway:
            self._clear_subnet_gateway_router(str(subnet.uuid))

        lr_gw_port = lr.external_ids.get(RouterMapper.OVN_ROUTER_GATEWAY_PORT)
        if port_id == lr_gw_port:
            self._remove_lr_gw_port(
                lr, ls_id, lrp_ip
            )
        return RouterInterface(
            id=router_id,
            ls_id=ls_id,
            lsp_id=port_id,
            dhcp_options_id=subnet_id,
        )

    def _remove_lr_gw_port(self, lr, ls_id, lrp_ip):
        self._execute(self.idl.db_remove(
            ovnconst.TABLE_LR,
            str(lr.uuid),
            ovnconst.ROW_LR_EXTERNAL_IDS,
            RouterMapper.OVN_ROUTER_GATEWAY_PORT
        ))
        self.atomics.remove_static_route(lr, ovnconst.DEFAULT_ROUTE)
        self._release_network_ip(ls_id, lrp_ip)

    def _is_subnet_on_router(self, router_id, subnet_id):
        lr = self.atomics.get_lr(lr_id=router_id)
        for lrp in lr.ports:
            lsp_id = self.atomics.get_lsp(lrp=lrp)
            lrp_subnet = self.atomics.get_dhcp(lsp_id=lsp_id)
            if str(lrp_subnet.uuid) == subnet_id:
                return True
        return False

    def _delete_router_interface(self, router_id, port_id, lrp, lr):
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
        subnet = self.atomics.get_dhcp(dhcp_id=subnet_id)
        network_id = subnet.external_ids[SubnetMapper.OVN_NETWORK_ID]
        network = self.atomics.get_ls(ls_id=network_id)
        lsp = self.atomics.get_lsp(lsp_id=port_id)
        validate.port_does_not_belong_to_subnet(lsp, network, subnet_id)
        return self._delete_router_interface_by_port(router_id, port_id)

    def _delete_router_interface_by_subnet(self, router_id, subnet_id):
        lr = self.atomics.get_lr(lr_id=router_id)
        subnet = self.atomics.get_dhcp(dhcp_id=subnet_id)
        network_id = subnet.external_ids[SubnetMapper.OVN_NETWORK_ID]
        network = self.atomics.get_ls(ls_id=network_id)
        lr_gw_port = lr.external_ids.get(RouterMapper.OVN_ROUTER_GATEWAY_PORT)
        deleted_lsp_id = None
        for lrp in lr.ports:
            lsp_id = self.atomics.get_lsp(lrp=lrp)
            lsp = self.atomics.get_lsp(lsp_id=lsp_id)
            if lsp in network.ports:
                deleted_lsp_id = lsp_id
                self._delete_router_interface(
                    router_id, lsp_id, lrp=lrp, lr=lr
                )
                if lsp_id == lr_gw_port:
                    self._remove_lr_gw_port(
                        lr, network_id,
                        ip_utils.get_ip_from_cidr(lrp.networks[0])
                    )
        subnet_gw_router_id = self._get_subnet_gateway_router_id(subnet)
        if subnet_gw_router_id == router_id:
            self._clear_subnet_gateway_router(str(subnet.uuid))

        if not deleted_lsp_id:
            raise BadRequestError(
                'Subnet {subnet_id} is not connected to router {router_id}'
                .format(subnet_id=subnet_id, router_id=router_id)
            )
        return RouterInterface(
            id=router_id,
            ls_id=network_id,
            lsp_id=deleted_lsp_id,
            dhcp_options_id=subnet_id,
        )

    def _is_port_address_value_static(self, type):
        return (
            type == ovnconst.LSP_TYPE_ROUTER or
            type == ovnconst.LSP_TYPE_LOCALNET
        )

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()
