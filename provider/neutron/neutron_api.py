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

from __future__ import absolute_import

import uuid

from functools import wraps
from netaddr import IPNetwork
from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound

import ovn_connection
import constants as ovnconst
import neutron.ip as ip_utils
import neutron.validation as validate

from handlers.base_handler import BadRequestError
from handlers.base_handler import ElementNotFoundError
from handlers.base_handler import MethodNotAllowedError

from neutron.neutron_api_mappers import AddRouterInterfaceMapper
from neutron.neutron_api_mappers import NetworkMapper
from neutron.neutron_api_mappers import Network
from neutron.neutron_api_mappers import NetworkPort
from neutron.neutron_api_mappers import PortMapper
from neutron.neutron_api_mappers import RemoveRouterInterfaceMapper
from neutron.neutron_api_mappers import RestDataError
from neutron.neutron_api_mappers import Router
from neutron.neutron_api_mappers import RouterInterface
from neutron.neutron_api_mappers import RouterMapper
from neutron.neutron_api_mappers import SecurityGroup
from neutron.neutron_api_mappers import SecurityGroupRule
from neutron.neutron_api_mappers import SecurityGroupMapper
from neutron.neutron_api_mappers import SecurityGroupRuleMapper
from neutron.neutron_api_mappers import SubnetConfigError
from neutron.neutron_api_mappers import SubnetMapper

from ovirt_provider_config_common import dhcp_lease_time
from ovirt_provider_config_common import dhcp_server_mac
from ovirt_provider_config_common import dhcp_enable_mtu
from ovirt_provider_config_common import dhcp_mtu
from ovirt_provider_config_common import default_port_security_enabled
from ovirt_provider_config_common import ovs_version_29

from ovndb.ovn_north import OvnNorth
from ovndb.ovn_north import optionally_use_transactions


def assure_security_groups_support(f):
    @wraps(f)
    def inner(wrapped_self, *args, **kwargs):
        if not wrapped_self.security_group_support:
            raise MethodNotAllowedError(
                'Security Groups are only supported on ovirt <= 4.3'
            )
        return f(wrapped_self, *args, **kwargs)
    return inner


def wrap_default_group_id(f):
    @wraps(f)
    def inner(wrapped_self, *args, **kwargs):
        try:
            default_group = wrapped_self.ovn_north.get_security_group(
                SecurityGroupMapper.DEFAULT_PG_NAME
            )
            default_group_id = default_group.uuid
            return f(
                wrapped_self, default_group_id=default_group_id,
                *args, **kwargs
            )
        except ElementNotFoundError:
            return f(wrapped_self, *args, **kwargs)
    return inner


class NeutronApi(object):

    def __init__(self, sec_group_support=None):
        self.ovsidl, self.idl = ovn_connection.connect()
        self.ovn_north = OvnNorth(self.idl)
        self.security_group_support = (
                sec_group_support or self.are_security_groups_supported()
        )
        self.tx_manager = ovn_connection.OvnTransactionManager(
            self.idl.ovsdb_connection
        )

    # TODO: could this be moved to ovsdbapp?
    def _get_port_network(self, port):
        networks = self.ovn_north.list_ls()
        return next(network for network in networks if port in network.ports)

    def _is_port_ovirt_controlled(self, port_row):
        return PortMapper.OVN_NIC_NAME in port_row.external_ids

    @NetworkMapper.map_to_rest
    def list_networks(self):
        ls_rows = self.ovn_north.list_ls()
        return [self._get_network(ls) for ls in ls_rows]

    def _get_network(self, ls):
        return Network(
            ls=ls,
            localnet_lsp=self._get_localnet_lsp(ls)
        )

    @NetworkMapper.map_to_rest
    def get_network(self, network_id):
        return self._get_network(
            self.ovn_north.get_ls(ls_id=network_id)
        )

    @NetworkMapper.validate_add
    @NetworkMapper.map_from_rest
    @NetworkMapper.map_to_rest
    def add_network(
            self, name, localnet=None, vlan=None, mtu=None,
            port_security_enabled=None
    ):
        if localnet:
            return self._add_localnet_network(
                name, localnet, vlan, mtu, port_security_enabled
            )
        else:
            return self._get_network(
                self._create_network(name, mtu, port_security_enabled)
            )

    def _create_network(self, name, mtu=None, port_security=None):
        external_ids_dict = {NetworkMapper.OVN_NETWORK_NAME: name}
        if mtu is not None:
            external_ids_dict[NetworkMapper.OVN_MTU] = str(mtu)
        external_ids_dict[NetworkMapper.OVN_NETWORK_PORT_SECURITY] = str(
            port_security if port_security is not None
            else default_port_security_enabled()
        )
        name = u'ovirt-{name}-{gen_id}'.format(name=name, gen_id=uuid.uuid4())
        return self.ovn_north.add_ls(
            name=name,
            external_ids=self._generate_external_ids({}, **external_ids_dict)
        )

    @staticmethod
    def _generate_external_ids(current_external_ids, **kwargs):
        return dict(current_external_ids, **kwargs)

    def _add_localnet_network(
            self, name, localnet, vlan, mtu, port_security_enabled
    ):
        network = self._create_network(name, mtu, port_security_enabled)
        localnet_port = self._create_port(
            ovnconst.LOCALNET_SWITCH_PORT_NAME, str(network.uuid)
        )
        self._set_port_localnet_values(localnet_port, localnet, vlan)
        updated_network = self.ovn_north.get_ls(ls_id=str(network.uuid))
        return self._get_network(updated_network)

    @NetworkMapper.validate_update
    @NetworkMapper.map_from_rest
    def update_network(
            self,
            network_id,
            name,
            localnet=None,
            vlan=None,
            mtu=None,
            port_security_enabled=None
    ):
        self._update_network_data(network_id, name, mtu, port_security_enabled)
        self._update_localnet_on_network(network_id, localnet, vlan)
        return self.get_network(network_id)

    def _update_network_data(self, network_id, name, mtu, port_security):
        current_external_ids = self.ovn_north.get_ls(
            ls_id=network_id
        ).external_ids

        relevant_external_ids = {
            NetworkMapper.OVN_NETWORK_NAME: name or current_external_ids[
                NetworkMapper.OVN_NETWORK_NAME
            ]
        }
        if mtu is not None:
            relevant_external_ids[NetworkMapper.OVN_MTU] = str(mtu)
        if port_security is not None:
            relevant_external_ids[
                NetworkMapper.OVN_NETWORK_PORT_SECURITY
            ] = str(port_security)
        new_external_ids = self._generate_external_ids(
            current_external_ids,
            **relevant_external_ids
        )
        self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LS, network_id).add(
            ovnconst.ROW_LS_EXTERNAL_IDS,
            new_external_ids
        ).execute()
        if mtu:
            self._update_networks_mtu(network_id, mtu)

    def _update_localnet_on_network(self, network_id, localnet, vlan):
        network = self.ovn_north.get_ls(ls_id=network_id)
        localnet_port = self._get_localnet_lsp(network)
        if localnet:
            if not localnet_port:
                localnet_port = self._create_port(
                    ovnconst.LOCALNET_SWITCH_PORT_NAME, str(network.uuid))
            self._set_port_localnet_values(localnet_port, localnet, vlan)
        elif localnet_port:
            self.ovn_north.remove_lsp(str(localnet_port.uuid))

    def _set_port_localnet_values(self, port_id, localnet, vlan):
        self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LSP, port_id
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
        subnet = self.ovn_north.get_dhcp(ls_id=network_id)
        old_mtu = self._get_subnet_mtu(subnet)
        if subnet and old_mtu != mtu:
            self.ovn_north.create_ovn_update_command(
                ovnconst.TABLE_DHCP_Options, subnet.uuid
            ).add(
                ovnconst.ROW_DHCP_OPTIONS
                if ip_utils.is_subnet_ipv4(subnet)
                else ovnconst.ROW_DHCP_EXTERNAL_IDS,
                {SubnetMapper.OVN_DHCP_MTU: str(mtu)}
            ).execute()
            if ip_utils.is_subnet_ipv6(subnet):
                self._update_ipv6_subnet_lrp_mtu(subnet, str(mtu))

    @staticmethod
    def _get_subnet_mtu(subnet):
        return (
            subnet.options.get(NetworkMapper.REST_MTU)
            if ip_utils.is_subnet_ipv4(subnet)
            else subnet.external_ids.get(SubnetMapper.OVN_DHCP_MTU)
        )

    def _update_ipv6_subnet_lrp_mtu(self, subnet, mtu):
        impacted_lrp = self.ovn_north.get_lrp_by_subnet(subnet)
        if impacted_lrp:
            self._update_ipv6_lrp_mtu(impacted_lrp, subnet, mtu)

    def _update_ipv6_lrp_mtu(self, router_port, subnet, mtu):
        self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LRP, self.ovn_north.get_lrp_id(router_port)
        ).add(
            ovnconst.ROW_LRP_IPV6_RA_CONFIGS,
            self._build_ra_config_dict(subnet, mtu)
        ).execute()

    def delete_network(self, network_id):
        network = self.ovn_north.get_ls(ls_id=network_id)
        if not network:
            raise RestDataError('Network %s does not exist' % network_id)
        validate.network_has_no_ports(
            network_id, network.ports,
            self._get_localnet_lsp(network)
        )

        subnets = self.ovn_north.list_dhcp()
        for subnet in subnets:
            subnet_network_id = subnet.external_ids.get('ovirt_network_id')
            if subnet_network_id:
                if network_id == subnet_network_id:
                    self.ovn_north.remove_dhcp_options(subnet.uuid)
        self.ovn_north.remove_ls(ls_id=network_id)

    def _get_localnet_lsp(self, ls):
        for lsp in ls.ports:
            if lsp.type == ovnconst.LSP_TYPE_LOCALNET:
                return lsp
        return None

    @PortMapper.map_to_rest
    def list_ports(self):
        ports_rows = self.ovn_north.list_lsp()
        return [self._get_network_port(port_row)
                for port_row in ports_rows
                if self._is_port_ovirt_controlled(port_row)]

    @PortMapper.map_to_rest
    def get_port(self, port_id):
        return self._get_network_port(
            self.ovn_north.get_lsp(ovirt_lsp_id=port_id)
        )

    @PortMapper.map_to_rest
    def _serialize_port(self, port):
        return port

    def _get_network_port(self, lsp):
        ls = self._get_port_network(lsp)
        dhcp_options = self.ovn_north.get_dhcp(lsp_id=lsp.uuid)
        lrp_name = lsp.options.get(ovnconst.LSP_OPTION_ROUTER_PORT)
        lrp = self.ovn_north.get_lrp(lrp_name=lrp_name) if lrp_name else None
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
        port_security=None,
        security_groups=None,
    ):
        with self.tx_manager.transaction() as tx:
            port_id = self._create_port(name, network_id, transaction=tx)
            self._update_port_values(
                port_id, name, is_enabled, device_id, device_owner,
                binding_host, transaction=tx
            )
            mac = mac or ip_utils.random_unique_mac(
                self.ovn_north.list_lsp(),
                self.ovn_north.list_lrp()
            )
            tx.add(
                self.get_update_port_addr_command(
                    port_id, network_id=network_id, mac=mac,
                    fixed_ips=fixed_ips
                ).build_command()
            )
            port_security = (
                port_security
                or self._get_port_security_from_network(network_id)
            )

            if security_groups is None and port_security:
                security_groups = [SecurityGroupMapper.DEFAULT_PG_NAME]
            elif security_groups is None:
                security_groups = []

            self.update_port_security(tx, port_id, mac, port_security)
            self.ovn_north.add_security_groups_to_port(
                port_id, security_groups, tx
            )
            self._update_port_security_groups_command(
                port_id, security_groups, tx
            )
        port_data = self._get_network_port(
            self.ovn_north.get_lsp(ovirt_lsp_id=port_id)
        )
        with self.tx_manager.transaction() as tx:
            self.ovn_north.add_addr_set_ip(
                security_groups, ip_utils.get_port_ip(lsp=port_data.lsp),
                transaction=tx
            )
        return self._serialize_port(port_data)

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
        port_security=None,
        security_groups=None,
    ):
        port = self.ovn_north.get_lsp(ovirt_lsp_id=port_id)
        network_id = self._get_validated_port_network_id(port, network_id)
        mac = mac or ip_utils.get_port_mac(port)
        with self.tx_manager.transaction() as tx:
            self._update_port_values(
                port.uuid, name, is_enabled, device_id, device_owner,
                binding_host, transaction=tx
            )
            tx.add(
                self.get_update_port_addr_command(
                    port.name, network_id=network_id, mac=mac,
                    fixed_ips=fixed_ips, port_type=port.type
                ).build_command()
            )
            self.update_port_security(
                tx, port.name, mac, port_security,
                update_port_association=False
            )
            self._update_port_security_groups(
                port, security_groups, tx, port_security=port_security,
                ip=fixed_ips[0].get(
                    PortMapper.REST_PORT_IP_ADDRESS
                ) if fixed_ips else None
            )
        return self.get_port(port_id)

    def _update_lsp_bound_lrp(self, port_id, fixed_ips):
        if not fixed_ips:
            return
        lrp = self.ovn_north.get_lrp(lsp_id=port_id)
        subnet = self.ovn_north.get_dhcp(lsp_id=port_id)
        validate.fixed_ip_matches_port_subnet(fixed_ips, subnet)
        validate.fixed_ips_require_stateful_dhcp(subnet, fixed_ips)

        new_lrp_ip = '{ip}/{netmask}'.format(
            ip=fixed_ips[0].get(PortMapper.REST_PORT_IP_ADDRESS),
            netmask=ip_utils.get_mask_from_subnet(subnet)
        )

        self.ovn_north.db_set(
            ovnconst.TABLE_LRP,
            str(lrp.uuid),
            (ovnconst.ROW_LRP_NETWORKS, new_lrp_ip)
        )

    @optionally_use_transactions
    def _update_port_values(
        self, port, name=None, is_enabled=None, device_id=None,
        device_owner=None, binding_host=None, transaction=None
    ):
        return self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LSP, port
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
        ).build_command()

    def get_update_port_addr_command(
        self, port_id, network_id, mac=None, fixed_ips=None, port_type=None
    ):
        if port_type == ovnconst.LSP_TYPE_ROUTER:
            self._update_lsp_bound_lrp(port_id, fixed_ips)
            return
        subnet = self.ovn_north.get_dhcp(ls_id=network_id)
        validate.fixed_ip_matches_port_subnet(fixed_ips, subnet)
        validate.fixed_ips_require_stateful_dhcp(subnet, fixed_ips)
        db_set_command = self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LSP, port_id
        )
        ip_version = int(
            subnet.external_ids.get(
                SubnetMapper.OVN_IP_VERSION, SubnetMapper.IP_VERSION_4
            ) if subnet else SubnetMapper.IP_VERSION_4
        )
        if mac:
            if subnet:
                self.update_port_subnet(db_set_command, subnet, ip_version)
                mac += ' ' + self._get_port_addesses_suffix(
                    network_id, fixed_ips)
            else:
                self.ovn_north.clear_row_column(
                    ovnconst.TABLE_LSP, port_id,
                    ovnconst.ROW_LSP_DHCPV4_OPTIONS
                )
            db_set_command.add(ovnconst.ROW_LSP_ADDRESSES, [mac])
        return db_set_command

    @staticmethod
    def update_port_subnet(ovsdb_update_command, subnet, ip_version):
        options_type = (
            ovnconst.ROW_LSP_DHCPV4_OPTIONS
            if ip_version == SubnetMapper.IP_VERSION_4
            else ovnconst.ROW_LSP_DHCPV6_OPTIONS
        )
        ovsdb_update_command.add(
            options_type, subnet.uuid
        )

    def update_port_security(
        self, transaction, port_id, mac, port_security,
            update_port_association=True
    ):
        update_db_command = self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LSP, port_id
        )
        if port_security is True:
            self.ovn_north.activate_default_security_group(
                port_id, transaction, update_port_association
            )
            update_db_command.add(
                ovnconst.ROW_LSP_PORT_SECURITY, [mac]
            )
        elif port_security is False:
            update_db_command = self.deactivate_port_security(
                port_id, transaction
            )
        cmd = update_db_command.build_command()
        if cmd:
            transaction.add(cmd)

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
            self.ovn_north.get_ls(ls_id=network_id), ip
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

        self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LSP, port
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

        self.ovn_north.clear_row_column(
            ovnconst.TABLE_LSP, port, ovnconst.ROW_LSP_DHCPV4_OPTIONS
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

    def _create_port(self, name, network_id, transaction=None):
        generated_id = str(uuid.uuid4())
        self.ovn_north.add_lsp(
            generated_id, name, network_id, transaction
        )
        return generated_id

    def _update_port_security_groups(
        self, port, security_groups, transaction, port_security=None, ip=None
    ):
        if security_groups is not None:
            new_groups = set(security_groups)
        elif port_security is True:
            new_groups = {SecurityGroupMapper.DEFAULT_PG_NAME}
        else:
            return
        old_security_groups = port.external_ids.get(
            PortMapper.OVN_SECURITY_GROUPS, ''
        ).split()
        old_groups = set(old_security_groups)
        sec_groups_to_install = new_groups - old_groups
        sec_groups_to_delete = old_groups - new_groups
        sec_groups_to_remain = old_groups.union(new_groups)

        self._process_sec_groups_ip_update(
            old_ip=ip_utils.get_port_ip(port),
            new_ip=ip or ip_utils.get_port_ip(port),
            to_install=sec_groups_to_install, to_remove=sec_groups_to_delete,
            to_remain=sec_groups_to_remain, transaction=transaction
        )

        self.ovn_north.add_security_groups_to_port(
            port.uuid, sec_groups_to_install, transaction
        )
        self.ovn_north.remove_security_groups_from_port(
            port.uuid, sec_groups_to_delete, transaction
        )
        self._update_port_security_groups_command(
            port.uuid, security_groups or sec_groups_to_install, transaction
        )

    def _process_sec_groups_ip_update(
            self, old_ip, new_ip, to_install, to_remove,
            to_remain, transaction
    ):
        self.ovn_north.delete_addr_set_ip(to_remove, old_ip, transaction)
        self.ovn_north.add_addr_set_ip(to_install, new_ip, transaction)
        if to_remain and old_ip != new_ip:
            self.ovn_north.delete_addr_set_ip(to_remain, old_ip, transaction)
            self.ovn_north.add_addr_set_ip(to_remain, new_ip, transaction)

    def _update_port_security_groups_command(
        self, port_id, security_groups, transaction
    ):
        transaction.add(
            self.ovn_north.create_ovn_update_command(
                ovnconst.TABLE_LSP, port_id
            ).add(
                ovnconst.ROW_LSP_EXTERNAL_IDS,
                {
                    PortMapper.OVN_SECURITY_GROUPS: ' '.join(security_groups)
                }
            ).build_command()
        )

    def update_port_mac(self, port_id, macaddress):
        pass

    def delete_port(self, port_id):
        lsp = self.ovn_north.get_lsp(lsp_id=port_id)
        validate.port_is_not_connected_to_router(lsp)
        with self.tx_manager.transaction() as tx:
            self.ovn_north.remove_lsp(port_id, transaction=tx)
            self.ovn_north.delete_addr_set_ip(
                security_groups=lsp.external_ids.get(
                    PortMapper.OVN_SECURITY_GROUPS, ''
                ).split(), ip=ip_utils.get_port_ip(lsp), transaction=tx
            )

    def deactivate_port_security(
        self, port_id, transaction,
    ):
        self.ovn_north.deactivate_dropall_security_group(port_id, transaction)
        return self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LSP, port_id
        ).add(ovnconst.ROW_LSP_PORT_SECURITY, [])

    @SubnetMapper.map_to_rest
    def list_subnets(self):
        return self.ovn_north.list_dhcp()

    @SubnetMapper.map_to_rest
    def get_subnet(self, subnet_id):
        return self.ovn_north.get_dhcp(dhcp_id=subnet_id)

    @SubnetMapper.validate_add
    @SubnetMapper.map_from_rest
    def add_subnet(
        self,
        name,
        cidr,
        network_id,
        gateway,
        ip_version,
        dns=None,
        ipv6_address_mode=None
    ):
        try:
            network = self.ovn_north.get_ls(ls_id=network_id)
        except ElementNotFoundError:
            raise SubnetConfigError('Subnet can not be created, network {}'
                                    ' does not exist'.format(network_id))

        if self.ovn_north.get_dhcp(ls_id=network_id):
            raise SubnetConfigError('Unable to create more than one subnet'
                                    ' for network {}'.format(network_id))

        network_mtu = network.external_ids.get(SubnetMapper.OVN_DHCP_MTU)
        external_ids = self.get_subnet_external_ids(
            network_id,
            ip_version,
            name,
            ipv6_address_mode,
            gateway,
            network_mtu or (dhcp_mtu() if dhcp_enable_mtu() else None)
        )
        options = self.get_subnet_options(
            cidr, gateway, network_mtu, dns, ipv6_address_mode
        )

        self.ovn_north.db_set(
            ovnconst.TABLE_LS,
            network_id,
            (ovnconst.ROW_LS_OTHER_CONFIG, self.get_ls_options(cidr)),
        )

        subnet = self.ovn_north.add_dhcp_options(cidr, external_ids)
        self.ovn_north.set_dhcp_options_options_column(subnet.uuid, options)

        for port in network.ports:
            if self._is_port_address_value_static(port.type):
                continue
            self.get_update_port_addr_command(
                port, network_id=network_id
            ).execute()

        return self.get_subnet(subnet.uuid)

    @staticmethod
    def get_ls_options(cidr):
        network = IPNetwork(cidr)
        if network.version == SubnetMapper.IP_VERSION_4:
            options = {NetworkMapper.OVN_SUBNET: cidr}
        else:
            options = {NetworkMapper.OVN_IPV6_PREFIX: str(network[0])}
        return options

    @staticmethod
    def get_subnet_options(
            cidr, gateway, network_mtu, dns, ipv6_address_mode=None
    ):
        network = IPNetwork(cidr)
        if network.version == SubnetMapper.IP_VERSION_4:
            options = {
                SubnetMapper.OVN_DHCP_SERVER_ID: cidr.split('/', 1)[0],
                SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac(),
                SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time(),
            }
            if gateway:
                options[SubnetMapper.OVN_GATEWAY] = gateway
            if network_mtu:
                options[SubnetMapper.OVN_DHCP_MTU] = network_mtu
            elif dhcp_enable_mtu():
                options[SubnetMapper.OVN_DHCP_MTU] = dhcp_mtu()
        else:
            options = {
                SubnetMapper.OVN_DHCP_SERVER_ID: dhcp_server_mac()
            }
            if ipv6_address_mode == SubnetMapper.IPV6_ADDRESS_MODE_STATELESS:
                options[SubnetMapper.OVN_DHCPV6_STATELESS] = "true"
        if dns:
            options[SubnetMapper.OVN_DNS_SERVER] = dns
        return options

    @staticmethod
    def get_subnet_external_ids(
            network_id,
            ip_version,
            name,
            ipv6_address_mode,
            gateway,
            mtu
    ):
        external_ids = {
            SubnetMapper.OVN_NETWORK_ID: network_id,
            SubnetMapper.OVN_IP_VERSION: str(ip_version)
        }
        if name:
            external_ids[SubnetMapper.OVN_NAME] = name
        if ipv6_address_mode:
            external_ids[
                SubnetMapper.OVN_IPV6_ADDRESS_MODE
            ] = ipv6_address_mode
            external_ids[SubnetMapper.OVN_DHCP_MTU] = mtu
        if ip_version == SubnetMapper.IP_VERSION_6 and gateway:
            external_ids[SubnetMapper.OVN_GATEWAY] = gateway
        return external_ids

    @SubnetMapper.validate_update
    @SubnetMapper.map_from_rest
    def update_subnet(
        self,
        subnet_id,
        name=None,
        gateway=None,
        dns=None,
    ):
        subnet = self.ovn_north.get_dhcp(dhcp_id=subnet_id)
        self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_DHCP_Options, subnet_id
        ).add(
            ovnconst.ROW_DHCP_EXTERNAL_IDS,
            {SubnetMapper.OVN_NAME: name},
            name
        ).add(
            (
                ovnconst.ROW_DHCP_OPTIONS if ip_utils.is_subnet_ipv4(subnet)
                else ovnconst.ROW_DHCP_EXTERNAL_IDS
            ),
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
        subnet = self.ovn_north.get_dhcp(dhcp_id=subnet_id)
        validate.subnet_not_connected_to_router(
            self._get_subnet_gateway_router_id(subnet),
            subnet_id
        )
        network_id = subnet.external_ids.get(
            SubnetMapper.OVN_NETWORK_ID
        )
        network = self.ovn_north.get_ls(ls_id=network_id)
        self.ovn_north.remove_dhcp_options(subnet_id)
        for port in network.ports:
            if self._is_port_address_value_static(port.type):
                continue
            self.get_update_port_addr_command(
                port, network_id=network_id
            ).execute()

    @RouterMapper.map_to_rest
    def get_router(self, router_id):
        return self._get_router_from_lr(self.ovn_north.get_lr(lr_id=router_id))

    def _get_router_from_lr(self, lr):
        gw_port_id = lr.external_ids.get(RouterMapper.OVN_ROUTER_GATEWAY_PORT)
        if not gw_port_id:
            return Router(
                lr=lr, ext_gw_ls_id=None, ext_gw_dhcp_options_id=None,
                gw_ip=None
            )
        gw_port = self.ovn_north.get_lsp(lsp_id=gw_port_id)
        ls = self._get_port_network(gw_port)
        ls_id = str(ls.uuid)

        dhcp_options = self.ovn_north.get_dhcp(ls_id=ls_id)
        lrp = self.ovn_north.get_lrp(lsp_id=gw_port_id)
        gw_ip = ip_utils.get_ip_from_cidr(lrp.networks[0])

        return Router(
            lr=lr, ext_gw_ls_id=ls_id,
            ext_gw_dhcp_options_id=str(dhcp_options.uuid), gw_ip=gw_ip
        )

    @RouterMapper.map_to_rest
    def list_routers(self):
        return [
            self._get_router_from_lr(lr)
            for lr in self.ovn_north.list_lr()
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

        router = self.ovn_north.add_lr(name, enabled)
        router_id = str(router.uuid)

        self._add_external_gateway_to_router(
            gateway_ip, gateway_subnet_id, network_id, router_id
        )
        self._add_routes_to_router(router_id, routes)
        router = self.ovn_north.get_lr(lr_id=router_id)
        return Router(
            lr=router, ext_gw_ls_id=network_id,
            ext_gw_dhcp_options_id=gateway_subnet_id, gw_ip=gateway_ip
        )

    def _add_routes_to_router(self, router_id, routes):
        if not routes:
            return
        for route in routes:
            self.ovn_north.add_route(
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
            subnet = self.ovn_north.get_dhcp(dhcp_id=gateway_subnet_id)
            self.ovn_north.add_route(
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
                self.ovn_north.get_ls(ls_id=network_id), gateway_ip
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
        lr = self.ovn_north.get_lr(lr_id=router_id)

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
                self.ovn_north.remove_static_route(lr, destination)
            for destination in added_routes:
                self.ovn_north.add_route(
                    router_id, destination, added_routes[destination]
                )

        existing_gw_lsp_id = lr.external_ids.get(
            RouterMapper.OVN_ROUTER_GATEWAY_PORT
        )
        is_updated_gw_different_than_existing = \
            self._is_updated_gw_different_than_existing(
                lr, gateway_subnet, gateway_ip, uuid.UUID(existing_gw_lsp_id)
                if existing_gw_lsp_id else None
            )
        if is_updated_gw_different_than_existing:
            self._delete_router_interface_by_port(
                router_id, existing_gw_lsp_id
            )
        self._reserve_network_ip(network_id, gateway_ip)

        self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LR, router_id
        ).add(
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

        existing_subnet = self.ovn_north.get_dhcp(lsp_id=existing_lr_gw_lsp_id)
        existing_ip = ip_utils.get_port_ip(
            self.ovn_north.get_lsp(lsp_id=existing_lr_gw_lsp_id),
            self.ovn_north.get_lrp(lsp_id=existing_lr_gw_lsp_id)
        )

        return (
            new_gateway_subnet != str(existing_subnet.uuid) or
            new_gateway_ip != existing_ip
        )

    def delete_router(self, router_id):
        existing_gw_lsp_id = self.ovn_north.get_lr(
            lr_id=router_id).external_ids.get(
                RouterMapper.OVN_ROUTER_GATEWAY_PORT
            )
        if existing_gw_lsp_id:
            self._delete_router_interface_by_port(
                router_id, existing_gw_lsp_id
            )

        validate.router_has_no_ports(self.ovn_north.get_lr(lr_id=router_id))
        self.ovn_north.remove_router(router_id)

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
        self.ovn_north.db_set(
            ovnconst.TABLE_DHCP_Options,
            subnet_id,
            (
                ovnconst.ROW_DHCP_EXTERNAL_IDS,
                {SubnetMapper.OVN_GATEWAY_ROUTER_ID: router_id}
            )
        )

    def _clear_subnet_gateway_router(self, subnet_id):
        self.ovn_north.remove_key_from_column(
            ovnconst.TABLE_DHCP_Options,
            subnet_id,
            ovnconst.ROW_DHCP_EXTERNAL_IDS,
            SubnetMapper.OVN_GATEWAY_ROUTER_ID
        )

    def _validate_create_routing_lsp_by_subnet(
        self, network_id, subnet_id, router_id=None, is_external_gateway=False
    ):
        existing_subnet_for_network = self.ovn_north.get_dhcp(ls_id=network_id)
        existing_router_for_subnet = self._get_subnet_gateway_router_id(
            existing_subnet_for_network
        )
        validate.create_routing_lsp_by_subnet(
            network_id, subnet_id, existing_subnet_for_network,
            existing_router_for_subnet, router_id,
            is_external_gateway=is_external_gateway
        )
        if router_id:
            router = self.ovn_north.get_lr(lr_id=router_id)
            self._validate_subnet_is_not_on_router(subnet_id, router_id)
            validate.unique_gateway_per_router(
                router, existing_subnet_for_network,
                self._get_router_gateways(router)
            )

    def _get_router_gateways(self, router):
        router_ports = (
            self.ovn_north.list_lrp(router_id=router.uuid) if router else []
        )
        return sum(
            [lrp[ovnconst.ROW_LRP_NETWORKS] for lrp in router_ports], []
        )

    def _create_routing_lsp_by_subnet(self, subnet_id, router_id):
        subnet = self.ovn_north.get_dhcp(dhcp_id=subnet_id)
        network_id = subnet.external_ids.get(SubnetMapper.OVN_NETWORK_ID)
        self._validate_create_routing_lsp_by_subnet(
            network_id, subnet_id, router_id)
        lrp_ip = self._get_ip_from_subnet(subnet, network_id, router_id)
        port = self._create_port(ovnconst.ROUTER_SWITCH_PORT_NAME, network_id)
        lrp_name = self._create_router_port_name(port)
        self._connect_port_to_router(
            port,
            lrp_name,
            router_id,
            name=ovnconst.ROUTER_SWITCH_PORT_NAME,
            is_enabled=True
        )
        self._set_subnet_gateway_router(subnet_id, router_id)
        return (
            str(port),
            lrp_name,
            lrp_ip,
            network_id,
            ip_utils.random_unique_mac(
                self.ovn_north.list_lsp(),
                self.ovn_north.list_lrp()
            )
        )

    def _validate_subnet_is_not_on_router(self, subnet_id, router_id):
        if self._is_subnet_on_router(router_id, subnet_id):
            raise BadRequestError(
                'Bad router request: Router already has a port on subnet'
                ' {subnet}'.format(subnet=subnet_id)
            )

    def _update_routing_lsp_by_port(self, port_id, router_id):
        port = self.ovn_north.get_lsp(lsp_id=port_id)
        if port.type == ovnconst.LSP_TYPE_ROUTER:
            raise BadRequestError(
                'Can not add {port} to router. Port is already connected to a'
                ' router'.format(port=port_id)
            )
        subnet = self.ovn_north.get_dhcp(lsp_id=port_id)
        if subnet:
            self._validate_subnet_is_not_on_router(subnet.uuid, router_id)

        lrp_ipmask = self._get_ip_netmask_for_lrp(port, router_id)
        lrp_name = self._create_router_port_name(port.name)
        mac = ip_utils.get_port_mac(port)
        self._connect_port_to_router(
            port.uuid,
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
        exclude_values = self.ovn_north.get_ls(
            ls_id=network_id
        ).other_config.get(
            ovnconst.LS_OPTION_EXCLUDE_IPS, {}
        )
        new_values = (
            (exclude_values + ' ') if exclude_values else str()
         ) + gateway_ip

        self.ovn_north.db_set(
            ovnconst.TABLE_LS,
            network_id,
            (
                ovnconst.ROW_LS_OTHER_CONFIG,
                {ovnconst.LS_OPTION_EXCLUDE_IPS: new_values}
            )
        )

    def _release_network_ip(self, network_id, ip):
        exclude_values = self.ovn_north.get_ls(
            ls_id=network_id
        ).other_config.get(
            ovnconst.LS_OPTION_EXCLUDE_IPS, ''
        )
        values = exclude_values.split()
        values.remove(ip)

        if values:
            self.ovn_north.db_set(
                ovnconst.TABLE_LS,
                network_id,
                (
                    ovnconst.ROW_LS_OTHER_CONFIG,
                    {ovnconst.LS_OPTION_EXCLUDE_IPS: ' '.join(values)}
                )
            )
        else:
            self.ovn_north.remove_key_from_column(
                ovnconst.TABLE_LS,
                network_id,
                ovnconst.ROW_LS_OTHER_CONFIG,
                ovnconst.LS_OPTION_EXCLUDE_IPS
            )

    def _add_external_gateway_interface(
        self, router_id, network_id, gateway_subnet_id, gateway_ip
    ):
        port_ip = '{ip}/{netmask}'.format(
            ip=gateway_ip,
            netmask=ip_utils.get_mask_from_subnet(
                self.ovn_north.get_dhcp(dhcp_id=gateway_subnet_id)
            )
        )

        port = self._create_port(ovnconst.ROUTER_SWITCH_PORT_NAME, network_id)
        lrp_name = self._create_router_port_name(port)
        mac = ip_utils.random_unique_mac(
            self.ovn_north.list_lsp(),
            self.ovn_north.list_lrp()
        )
        self.ovn_north.add_lrp(router_id, lrp_name, mac=mac, lrp_ip=port_ip)
        self._connect_port_to_router(
            port,
            lrp_name,
            router_id,
            name=ovnconst.ROUTER_SWITCH_PORT_NAME,
            is_enabled=True,
            is_external_gateway=True,
        )

        self.ovn_north.create_ovn_update_command(
            ovnconst.TABLE_LR, router_id
        ).add(
            ovnconst.ROW_LR_EXTERNAL_IDS,
            {
                RouterMapper.OVN_ROUTER_GATEWAY_PORT: str(port),
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
        subnet = (
            self.ovn_north.get_dhcp(dhcp_id=subnet_id) if subnet_id
            else self.ovn_north.get_dhcp(ls_id=network_id)
        )
        self.ovn_north.add_lrp(
            router_id, lrp_name, mac=mac, lrp_ip=lrp_ip,
            ipv6_ra_configs=self._get_ra_configs(subnet)
        )

        return RouterInterface(
            id=router_id,
            ls_id=network_id,
            lsp_id=port_id,
            dhcp_options_id=subnet_id or str(subnet.uuid),
        )

    def _get_ra_configs(self, subnet):
        network = self.ovn_north.get_ls(dhcp=subnet)
        return self._build_ra_config_dict(
            subnet,
            network.external_ids.get(NetworkMapper.OVN_MTU)
        )

    @staticmethod
    def _build_ra_config_dict(subnet, mtu=None):
        if not ip_utils.is_subnet_ipv6(subnet):
            return {}
        ra_options = {
            ovnconst.ROW_LRP_IPV6_ADDRESS_MODE: subnet.external_ids.get(
                SubnetMapper.OVN_IPV6_ADDRESS_MODE
            ),
            ovnconst.ROW_LRP_IPV6_SEND_PERIODIC: "true"
        }
        if mtu:
            ra_options[ovnconst.ROW_LRP_IPV6_MTU] = mtu
        return ra_options

    def _get_ip_from_subnet(self, subnet, network_id, router_id):
        validate.attach_network_to_router_by_subnet(
            subnet, network_id, router_id
        )
        subnet_gateway = (
            subnet.options.get('router') if ip_utils.is_subnet_ipv4(subnet)
            else subnet.external_ids.get(SubnetMapper.OVN_GATEWAY)
        )
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
        lsp = self.ovn_north.get_lsp(lsp_name=port_id)
        validate.port_is_connected_to_router(lsp)

        subnet = self.ovn_north.get_dhcp(lsp_id=lsp.uuid)
        subnet_id = str(subnet.uuid)
        lrp = self.ovn_north.get_lrp(lsp_id=port_id)
        lrp_ip = ip_utils.get_ip_from_cidr(lrp.networks[0])
        lr = self.ovn_north.get_lr(lr_id=router_id)
        ls_id = str(self.ovn_north.get_ls(dhcp=subnet).uuid)

        is_subnet_gateway = (
            subnet and
            self._is_subnet_on_router(router_id, subnet_id) and
            lrp_ip == ip_utils.get_subnet_gateway(subnet)
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
        self.ovn_north.remove_key_from_column(
            ovnconst.TABLE_LR,
            str(lr.uuid),
            ovnconst.ROW_LR_EXTERNAL_IDS,
            RouterMapper.OVN_ROUTER_GATEWAY_PORT
        )
        self.ovn_north.remove_static_route(lr, ovnconst.DEFAULT_ROUTE)
        self._release_network_ip(ls_id, lrp_ip)

    def _is_subnet_on_router(self, router_id, subnet_id):
        lr = self.ovn_north.get_lr(lr_id=router_id)
        for lrp in lr.ports:
            lsp_id = self.ovn_north.get_lsp(lrp=lrp).uuid
            lrp_subnet = self.ovn_north.get_dhcp(lsp_id=lsp_id)
            if str(lrp_subnet.uuid) == subnet_id:
                return True
        return False

    def _delete_router_interface(self, router_id, port_id, lrp, lr):
        if lrp not in lr.ports:
            raise BadRequestError(
                'Port {port} is not connected to router {router}'
                .format(port=port_id, router=router_id)
            )
        self.ovn_north.remove_lrp(lrp.uuid)
        self.ovn_north.remove_lsp(port_id)

    def _delete_router_interface_by_subnet_and_port(
        self, router_id, subnet_id, port_id
    ):
        subnet = self.ovn_north.get_dhcp(dhcp_id=subnet_id)
        network_id = subnet.external_ids[SubnetMapper.OVN_NETWORK_ID]
        network = self.ovn_north.get_ls(ls_id=network_id)
        lsp = self.ovn_north.get_lsp(lsp_id=port_id)
        validate.port_does_not_belong_to_subnet(lsp, network, subnet_id)
        return self._delete_router_interface_by_port(router_id, port_id)

    def _delete_router_interface_by_subnet(self, router_id, subnet_id):
        lr = self.ovn_north.get_lr(lr_id=router_id)
        subnet = self.ovn_north.get_dhcp(dhcp_id=subnet_id)
        network_id = subnet.external_ids[SubnetMapper.OVN_NETWORK_ID]
        network = self.ovn_north.get_ls(ls_id=network_id)
        lr_gw_port = lr.external_ids.get(RouterMapper.OVN_ROUTER_GATEWAY_PORT)
        deleted_lsp_id = None
        for lrp in lr.ports:
            lsp_id = self.ovn_north.get_lsp(lrp=lrp).uuid
            lsp = self.ovn_north.get_lsp(lsp_id=lsp_id)
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

    def _get_port_security_from_network(self, network_id):
        network = self.ovn_north.get_ls(
            ls_id=network_id
        )
        return NetworkMapper._str2bool(
            str(network.external_ids.get(
                NetworkMapper.OVN_NETWORK_PORT_SECURITY,
                default_port_security_enabled()
            ))
        )

    @SecurityGroupMapper.map_to_rest
    @wrap_default_group_id
    def list_security_groups(self, default_group_id=None):
        return [
            SecurityGroup(
                sec_group=group_data,
                sec_group_rules=[
                    SecurityGroupRule(rule, default_group_id)
                    for rule in self.ovn_north.list_security_group_rules(
                        group_data
                    )
                ]
            )
            for group_data in self.ovn_north.list_security_groups()
        ] if self.are_security_groups_supported() else []

    @SecurityGroupMapper.map_to_rest
    @wrap_default_group_id
    @assure_security_groups_support
    def get_security_group(self, sec_group_id, default_group_id=None):
        security_group = self.ovn_north.get_security_group(sec_group_id)
        all_rules = self.ovn_north.list_security_group_rules(
            security_group
        )
        return SecurityGroup(
            sec_group=security_group,
            sec_group_rules=[
                SecurityGroupRule(rule, default_group_id)
                for rule in all_rules
            ]
        )

    @SecurityGroupMapper.validate_add
    @SecurityGroupMapper.map_from_rest
    @assure_security_groups_support
    def add_security_group(
            self, name, project_id=None, tenant_id=None, description=None
    ):
        with self.tx_manager.transaction() as tx:
            group_data, egress_rules = self.ovn_north.add_security_group(
                name, project_id, tenant_id, description, transaction=tx
            )
        return self.get_security_group(group_data.name)

    @assure_security_groups_support
    def delete_security_group(self, security_group_id):
        self.ovn_north.remove_security_group(security_group_id)

    @SecurityGroupMapper.validate_update
    @SecurityGroupMapper.map_from_rest
    @assure_security_groups_support
    def update_security_group(self, sec_group_id, name, description=None):
        with self.tx_manager.transaction() as tx:
            self.ovn_north.update_security_group(
                sec_group_id, name, description, transaction=tx
            )
        return SecurityGroup(
            sec_group=self.get_security_group(sec_group_id),
            sec_group_rules=[]
        )

    @SecurityGroupRuleMapper.map_to_rest
    @wrap_default_group_id
    @assure_security_groups_support
    def list_security_group_rules(self, default_group_id=None):
        rules = self.ovn_north.list_security_group_rules()
        return [
            SecurityGroupRule(rule, default_group_id)
            for rule in rules
        ]

    @SecurityGroupRuleMapper.map_to_rest
    @wrap_default_group_id
    @assure_security_groups_support
    def get_security_group_rule(
            self, security_group_rule_id, default_group_id=None
    ):
        rule = self.ovn_north.get_security_group_rule(security_group_rule_id)
        return SecurityGroupRule(rule, default_group_id)

    @SecurityGroupRuleMapper.validate_add
    @SecurityGroupRuleMapper.map_from_rest
    @SecurityGroupRuleMapper.map_to_rest
    @assure_security_groups_support
    def add_security_group_rule(
            self, security_group_id, direction, description=None,
            ether_type=None, port_min=None, port_max=None,
            remote_ip_prefix=None, protocol=None, remote_group_id=None
    ):
        sec_group = self.ovn_north.get_security_group(security_group_id)
        sec_group_rule = self.ovn_north.create_security_group_rule(
            sec_group, direction, description=description,
            ether_type=ether_type, remote_ip_prefix=remote_ip_prefix,
            port_min=port_min, port_max=port_max, protocol=protocol,
            remote_group_id=remote_group_id
        )
        default_group_id = (
            sec_group.uuid
            if sec_group.name in SecurityGroupMapper.WHITE_LIST_GROUP_NAMES
            else None
        )
        return SecurityGroupRule(sec_group_rule, default_group_id)

    @assure_security_groups_support
    def delete_security_group_rule(self, security_group_rule_id):
        self.ovn_north.remove_security_group_rule(security_group_rule_id)

    def are_security_groups_supported(self):
        return ovnconst.TABLE_PORT_GROUP in self.ovsidl.tables

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.ovsidl.close()
