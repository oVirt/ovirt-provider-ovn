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

import abc
from collections import namedtuple
from functools import wraps

from netaddr import IPNetwork
import six

from ovirt_provider_config_common import tenant_id
import ovndb.constants as ovnconst
import ovndb.ip as ip_utils
from handlers.base_handler import MethodNotAllowedError
from handlers.base_handler import BadRequestError


NetworkPort = namedtuple('NetworkPort', ['lsp', 'ls', 'dhcp_options', 'lrp'])
Network = namedtuple('Network', ['ls', 'localnet_lsp'])


@six.add_metaclass(abc.ABCMeta)
class Mapper(object):

    REST_TENANT_ID = 'tenant_id'

    @classmethod
    def map_from_rest(cls, f):
        @wraps(f)
        def wrapper(wrapped_self, rest_data, entity_id=None):
            return cls.rest2row(wrapped_self, f, rest_data, entity_id)
        return wrapper

    @classmethod
    def validate_add(cls, f):
        return cls._validate(f, cls.validate_add_rest_input)

    @classmethod
    def validate_update(cls, f):
        return cls._validate(f, cls.validate_update_rest_input)

    @classmethod
    def _validate(cls, f, validate_rest_input):
        @wraps(f)
        def wrapper(wrapped_self, rest_data, entity_id=None):
            validate_rest_input(rest_data)
            return (f(wrapped_self, rest_data, entity_id) if entity_id
                    else f(wrapped_self, rest_data))
        return wrapper

    @classmethod
    def map_to_rest(cls, f):
        @wraps(f)
        def wrapper(wrapped_self, *args, **kwargs):
            data = f(wrapped_self, *args, **kwargs)
            if isinstance(data, list):
                return [cls.row2rest(row) for row in data]
            else:
                return cls.row2rest(data)
        return wrapper

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, entity_id):
        raise NotImplementedError()

    @staticmethod
    def row2rest(func, row):
        raise NotImplementedError()

    @staticmethod
    def validate_add_rest_input(rest_data):
        raise NotImplementedError()

    @staticmethod
    def validate_update_rest_input(rest_data):
        raise NotImplementedError()


class NetworkMapper(Mapper):
    # The names of properties received/sent in a REST request
    REST_NETWORK_ID = 'id'
    REST_NETWORK_NAME = 'name'
    REST_STATUS = 'status'
    REST_PROVIDER_NETWORK_TYPE = 'provider:network_type'
    REST_PROVIDER_PHYSICAL_NETWORK = 'provider:physical_network'
    REST_PROVIDER_SEGMENTATION_ID = 'provider:segmentation_id'

    NETWORK_TYPE_FLAT = 'flat'
    NETWORK_TYPE_VLAN = 'vlan'

    OVN_SUBNET = 'subnet'

    NETWORK_STATUS_ACTIVE = 'ACTIVE'

    @staticmethod
    def rest2row(wrapped_self, func, rest_network_data, network_id):
        network_name = rest_network_data.get(NetworkMapper.REST_NETWORK_NAME)
        provider_physical_network = rest_network_data.get(
            NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK)
        provider_segmentation_id = rest_network_data.get(
            NetworkMapper.REST_PROVIDER_SEGMENTATION_ID)
        if network_id:
            return func(
                wrapped_self,
                network_id,
                name=network_name,
                localnet=provider_physical_network,
                vlan=provider_segmentation_id
            )
        return func(
            wrapped_self,
            name=network_name,
            localnet=provider_physical_network,
            vlan=provider_segmentation_id
        )

    @staticmethod
    def row2rest(network):
        if not network:
            return {}
        ls, localnet_lsp = network.ls, network.localnet_lsp
        result = {
            NetworkMapper.REST_NETWORK_ID: str(ls.uuid),
            NetworkMapper.REST_NETWORK_NAME: ls.name,
            NetworkMapper.REST_TENANT_ID: tenant_id(),
            NetworkMapper.REST_STATUS: NetworkMapper.NETWORK_STATUS_ACTIVE
        }
        result.update(NetworkMapper._row2rest_localnet(localnet_lsp))
        return result

    @staticmethod
    def _row2rest_localnet(localnet_lsp):
        if not localnet_lsp:
            return {}
        result = {
            NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK:
                localnet_lsp.options.get(ovnconst.LSP_OPTION_NETWORK_NAME)
        }
        ovn_vlan = localnet_lsp.tag
        if ovn_vlan:
            result[NetworkMapper.REST_PROVIDER_SEGMENTATION_ID] = int(
                ovn_vlan[0]
            )
            result[
                NetworkMapper.REST_PROVIDER_NETWORK_TYPE
            ] = NetworkMapper.NETWORK_TYPE_VLAN
        else:
            result[
                NetworkMapper.REST_PROVIDER_NETWORK_TYPE
            ] = NetworkMapper.NETWORK_TYPE_FLAT
        return result

    @staticmethod
    def validate_add_rest_input(rest_data):
        NetworkMapper._validate_rest_input(rest_data)

    @staticmethod
    def validate_update_rest_input(rest_data):
        NetworkMapper._validate_rest_input(rest_data)

    @staticmethod
    def _validate_rest_input(rest_data):
        if NetworkMapper.REST_NETWORK_NAME not in rest_data:
            raise NetworkNameRequiredDataError()
        NetworkMapper._validate_rest_input_provider_network(rest_data)

    @staticmethod
    def _validate_rest_input_provider_network(rest_data):
        network_type = rest_data.get(NetworkMapper.REST_PROVIDER_NETWORK_TYPE)
        if not network_type:
            if NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK in rest_data:
                raise PhysicalNetworkProviderDataError(
                    'provider:physical_network cannot be used without a '
                    'specified provider:network_type')
            elif NetworkMapper.REST_PROVIDER_SEGMENTATION_ID in rest_data:
                raise PhysicalNetworkProviderDataError(
                    'provider:segmentation_id cannot be used without a '
                    'specified provider:network_type')
        elif network_type == NetworkMapper.NETWORK_TYPE_FLAT:
            if NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK not in rest_data:
                raise PhysicalNetworkProviderDataError(
                    'provider:physical_network is mandatory for network type '
                    'flat')
            elif NetworkMapper.REST_PROVIDER_SEGMENTATION_ID in rest_data:
                raise PhysicalNetworkProviderDataError(
                    'provider:segmentation_id can only be used with network '
                    'type vlan')
        elif network_type == NetworkMapper.NETWORK_TYPE_VLAN:
            if NetworkMapper.REST_PROVIDER_SEGMENTATION_ID not in rest_data:
                raise PhysicalNetworkProviderDataError(
                    'provider:segmentation_id is mandatory for network type '
                    'vlan')
            elif NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK not in rest_data:
                raise PhysicalNetworkProviderDataError(
                    'provider:physical_network is mandatory for network type '
                    'vlan')
        else:
            raise PhysicalNetworkProviderDataError(
                'provider:network_type [{}] is not supported'.format(
                    network_type))


class PortMapper(Mapper):
    # The names of properties received/sent in a REST request
    REST_PORT_ID = 'id'
    REST_PORT_NETWORK_ID = 'network_id'
    REST_PORT_NAME = 'name'
    REST_PORT_MAC_ADDRESS = 'mac_address'
    REST_PORT_ADMIN_STATE_UP = 'admin_state_up'
    REST_PORT_DEVICE_ID = 'device_id'
    REST_PORT_DEVICE_OWNER = 'device_owner'
    REST_PORT_SECURITY_GROUPS = 'security_groups'
    REST_PORT_SECURITY_ENABLED = 'port_security_enabled'
    REST_PORT_FIXED_IPS = 'fixed_ips'
    REST_PORT_SUBNET_ID = 'subnet_id'
    REST_PORT_IP_ADDRESS = 'ip_address'
    REST_PORT_BINDING_HOST = 'binding:host_id'

    OVN_DEVICE_ID = 'ovirt_device_id'
    OVN_NIC_NAME = 'ovirt_nic_name'
    OVN_DEVICE_OWNER = 'ovirt_device_owner'
    OVN_REQUESTED_CHASSIS = 'requested-chassis'
    DEVICE_OWNER_ROUTER = 'network:router_interface'

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, port_id):
        network_id = rest_data.get(PortMapper.REST_PORT_NETWORK_ID)
        name = rest_data.get(PortMapper.REST_PORT_NAME)
        mac = rest_data.get(PortMapper.REST_PORT_MAC_ADDRESS)
        is_enabled = rest_data.get(PortMapper.REST_PORT_ADMIN_STATE_UP)
        device_id = rest_data.get(PortMapper.REST_PORT_DEVICE_ID)
        device_owner = rest_data.get(PortMapper.REST_PORT_DEVICE_OWNER)
        fixed_ips = rest_data.get(PortMapper.REST_PORT_FIXED_IPS)
        binding_host = rest_data.get(PortMapper.REST_PORT_BINDING_HOST)

        if port_id:
            return func(
                wrapped_self,
                port_id=port_id,
                network_id=network_id,
                name=name,
                mac=mac,
                is_enabled=is_enabled,
                device_id=device_id,
                device_owner=device_owner,
                fixed_ips=fixed_ips,
                binding_host=binding_host,
            )
        else:
            return func(
                wrapped_self,
                network_id=network_id,
                name=name,
                mac=mac,
                is_enabled=is_enabled,
                device_id=device_id,
                device_owner=device_owner,
                fixed_ips=fixed_ips,
                binding_host=binding_host,
            )

    @staticmethod
    def row2rest(row):
        """
            Maps the db rows (lsp, ls) to a Json representation of a port.
            The 'admin_state_up' property of the lsp is the product of
            two values:
            - lsp.up - managed internally by OVN, True only if
            set explicitly to [True]
            - lsp.enabled - set by the user, True if empty (None) or
            set to [True]
        """
        if not row:
            return {}
        lsp, ls, dhcp_options, lrp = row
        rest_data = {
            PortMapper.REST_PORT_ID: str(lsp.uuid),
            PortMapper.REST_PORT_NAME:
                lsp.external_ids[PortMapper.OVN_NIC_NAME],
            PortMapper.REST_PORT_NETWORK_ID: str(ls.uuid),
            PortMapper.REST_PORT_SECURITY_GROUPS: [],
            PortMapper.REST_PORT_SECURITY_ENABLED: False,
            PortMapper.REST_TENANT_ID: tenant_id(),
            PortMapper.REST_PORT_FIXED_IPS: PortMapper.get_fixed_ips(
                lsp,
                dhcp_options,
                lrp
            ),
            PortMapper.REST_PORT_ADMIN_STATE_UP: bool(
                (lsp.up and lsp.up[0]) and
                (not lsp.enabled or lsp.enabled[0])
            )
        }
        if PortMapper.OVN_DEVICE_ID in lsp.external_ids:
            rest_data[
                PortMapper.REST_PORT_DEVICE_ID
            ] = str(lsp.external_ids[PortMapper.OVN_DEVICE_ID])
        if PortMapper.OVN_DEVICE_OWNER in lsp.external_ids:
            rest_data[
                PortMapper.REST_PORT_DEVICE_OWNER
            ] = lsp.external_ids[PortMapper.OVN_DEVICE_OWNER]
        if lsp.addresses:
            mac = lsp.addresses[0].split(' ')[0]
            rest_data[PortMapper.REST_PORT_MAC_ADDRESS] = mac
        if lsp.options and PortMapper.OVN_REQUESTED_CHASSIS in lsp.options:
            binding_host = lsp.options[PortMapper.REST_PORT_BINDING_HOST]
            rest_data[PortMapper.REST_PORT_BINDING_HOST] = binding_host
        return rest_data

    @staticmethod
    def get_fixed_ips(lsp, dhcp_options, lrp):
        ip_address = ip_utils.get_port_ip(lsp, lrp)
        if ip_address:
            return [{
                PortMapper.REST_PORT_IP_ADDRESS: ip_address,
                PortMapper.REST_PORT_SUBNET_ID:
                    str(dhcp_options.uuid) if dhcp_options else None,
            }]

        return []

    @staticmethod
    def validate_add_rest_input(rest_data):
        if PortMapper.REST_PORT_NETWORK_ID not in rest_data:
            raise NetworkIdRequiredForPortDataError()
        PortMapper._validate_common(rest_data)

    @staticmethod
    def validate_update_rest_input(rest_data):
        PortMapper._validate_common(rest_data)

    @staticmethod
    def _validate_common(rest_data):

        sec_groups = rest_data.get(PortMapper.REST_PORT_SECURITY_GROUPS)
        if sec_groups and sec_groups != []:
            raise SecurityGroupsNotSupportedDataError()

        sec_enabled = rest_data.get(PortMapper.REST_PORT_SECURITY_ENABLED)
        if sec_enabled:
            raise PortSecurityNotSupportedDataError()
        fixed_ips = rest_data.get(PortMapper.REST_PORT_FIXED_IPS)
        if fixed_ips:
            if type(fixed_ips) is not list:
                raise RestDataError(
                    '{type} must be of type: list'.format(
                        type=PortMapper.REST_PORT_FIXED_IPS
                    )
                )
            if len(fixed_ips) > 1:
                raise RestDataError(
                    'Specifying more then one {type} value is not allowed'
                    .format(type=PortMapper.REST_PORT_FIXED_IPS)
                )
            if (type(fixed_ips[0]) is not dict):
                raise RestDataError(
                    '{type} must be a dictionary containing {ip_addr} and '
                    '{subnet_id}'.format(
                        type=PortMapper.REST_PORT_FIXED_IPS,
                        ip_addr=PortMapper.REST_PORT_IP_ADDRESS,
                        subnet_id=PortMapper.REST_PORT_SUBNET_ID,
                    )
                )
            if (
                PortMapper.REST_PORT_IP_ADDRESS not in fixed_ips[0] and
                PortMapper.REST_PORT_SUBNET_ID not in fixed_ips[0]

            ):
                raise RestDataError(
                    '{type} must contain at least the {ip_addr} or the '
                    '{subnet_id} element'.format(
                        type=PortMapper.REST_PORT_FIXED_IPS,
                        ip_addr=PortMapper.REST_PORT_IP_ADDRESS,
                        subnet_id=PortMapper.REST_PORT_SUBNET_ID
                    )
                )


class SubnetMapper(Mapper):
    REST_SUBNET_ID = 'id'
    REST_SUBNET_NAME = 'name'
    REST_SUBNET_CIDR = 'cidr'
    REST_SUBNET_NETWORK_ID = 'network_id'
    REST_SUBNET_DNS_NAMESERVERS = 'dns_nameservers'
    REST_SUBNET_GATEWAY_IP = 'gateway_ip'
    REST_SUBNET_ENABLE_DHCP = 'enable_dhcp'
    REST_SUBNET_IP_VERSION = 'ip_version'
    REST_SUBNET_ALLOCATION_POOLS = 'allocation_pools'
    REST_SUBNET_ALLOCATION_POOLS_START = 'start'
    REST_SUBNET_ALLOCATION_POOLS_STOP = 'stop'

    OVN_NAME = 'ovirt_name'
    OVN_NETWORK_ID = 'ovirt_network_id'
    OVN_DNS_SERVER = 'dns_server'
    OVN_GATEWAY = 'router'
    OVN_DHCP_SERVER_ID = 'server_id'
    OVN_DHCP_SERVER_MAC = 'server_mac'
    OVN_DHCP_LEASE_TIME = 'lease_time'
    OVN_DHCP_MTU = 'mtu'
    OVN_GATEWAY_ROUTER_ID = 'gateway_router'

    IP_VERSION = 4

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, subnet_id):
        name = rest_data.get(SubnetMapper.REST_SUBNET_NAME)
        cidr = rest_data.get(SubnetMapper.REST_SUBNET_CIDR)
        network_id = rest_data.get(SubnetMapper.REST_SUBNET_NETWORK_ID)
        dnses = rest_data.get(SubnetMapper.REST_SUBNET_DNS_NAMESERVERS)
        dns = dnses[0] if dnses else None
        gateway = rest_data.get(SubnetMapper.REST_SUBNET_GATEWAY_IP)

        if subnet_id:
            return func(
                wrapped_self,
                subnet_id=subnet_id,
                name=name,
                gateway=gateway,
                dns=dns,
            )
        else:
            return func(
                wrapped_self,
                name=name,
                cidr=cidr,
                network_id=network_id,
                gateway=gateway,
                dns=dns,
            )

    @staticmethod
    def row2rest(row):
        if not row:
            return {}
        options = row.options
        external_ids = row.external_ids
        result = {
            SubnetMapper.REST_SUBNET_ID: str(row.uuid),
            SubnetMapper.REST_SUBNET_CIDR: row.cidr,
            SubnetMapper.REST_SUBNET_NETWORK_ID:
                external_ids[SubnetMapper.OVN_NETWORK_ID],
            SubnetMapper.REST_SUBNET_IP_VERSION: SubnetMapper.IP_VERSION,
            SubnetMapper.REST_TENANT_ID: tenant_id(),
            SubnetMapper.REST_SUBNET_ENABLE_DHCP: True,
            SubnetMapper.REST_SUBNET_ALLOCATION_POOLS: [
                SubnetMapper.get_allocation_pool(row.cidr),
            ],
            SubnetMapper.REST_SUBNET_DNS_NAMESERVERS: [
                options[SubnetMapper.OVN_DNS_SERVER]
            ] if SubnetMapper.OVN_DNS_SERVER in options else []
        }
        if SubnetMapper.OVN_NAME in external_ids:
            result[SubnetMapper.REST_SUBNET_NAME] = (
                external_ids[SubnetMapper.OVN_NAME]
            )
        if SubnetMapper.OVN_GATEWAY in options:
            result[SubnetMapper.REST_SUBNET_GATEWAY_IP] = (
                options[SubnetMapper.OVN_GATEWAY]
            )

        return result

    @staticmethod
    def get_allocation_pool(cidr):
        ip_network = IPNetwork(cidr)
        if len(ip_network) > 2:
            return {
                SubnetMapper.REST_SUBNET_ALLOCATION_POOLS_START:
                    str(ip_network[2]),
                SubnetMapper.REST_SUBNET_ALLOCATION_POOLS_STOP:
                    str(ip_network[-1])
            }

    @staticmethod
    def validate_add_rest_input(rest_data):
        SubnetMapper._validate_common(rest_data)

    @staticmethod
    def validate_update_rest_input(rest_data):
        SubnetMapper._validate_common(rest_data)

    @staticmethod
    def _validate_common(rest_data):
        if (SubnetMapper.REST_SUBNET_ENABLE_DHCP in rest_data and
           not rest_data[SubnetMapper.REST_SUBNET_ENABLE_DHCP]):
            raise UnsupportedDataValueError(
                SubnetMapper.REST_SUBNET_ENABLE_DHCP,
                False
            )


class RouterMapper(Mapper):
    REST_ROUTER_ID = 'id'
    REST_ROUTER_NAME = 'name'

    REST_ROUTER_ROUTES = 'routes'
    REST_ROUTER_ADMIN_STATE_UP = 'admin_state_up'
    REST_ROUTER_STATUS = 'status'

    REST_ROUTER_EXTERNAL_GATEWAY_INFO = 'external_gateway_info'
    REST_ROUTER_NETWORK_ID = 'network_id'
    REST_ROUTER_ENABLE_SNAT = 'enable_snat'

    REST_ROUTER_FIXED_IPS = 'external_fixed_ips'
    REST_ROUTER_IP_ADDRESS = 'ip_address'
    REST_ROUTER_SUBNET_ID = 'subnet_id'

    OVN_ROUTER_GATEWAY_NETWORK = 'ovirt_gateway_network'
    OVN_ROUTER_GATEWAY_SUBNET = 'ovirt_gateway_subnet'
    OVN_ROUTER_GATEWAY_IP = 'ovirt_gateway_ip'

    ROUTER_STATUS_ACTIVE = 'ACTIVE'
    ROUTER_STATUS_INACTIVE = 'INACTIVE'

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, router_id):
        name = rest_data.get(RouterMapper.REST_ROUTER_NAME)
        enabled = rest_data.get(RouterMapper.REST_ROUTER_ADMIN_STATE_UP, True)

        network, subnet, ip = RouterMapper._get_external_gateway_from_rest(
            rest_data
        )

        if router_id:
            return func(
                wrapped_self, router_id=router_id, name=name, enabled=enabled,
                network_id=network, gateway_subnet=subnet,
                gateway_ip=ip
            )
        else:
            return func(
                wrapped_self, name=name, enabled=enabled,
                network_id=network, gateway_subnet=subnet,
                gateway_ip=ip
            )

    @staticmethod
    def _get_external_gateway_from_rest(rest_data):
        gateway_info = rest_data.get(
            RouterMapper.REST_ROUTER_EXTERNAL_GATEWAY_INFO, {})
        if not gateway_info:
            return None, None, None
        network_id = gateway_info.get(RouterMapper.REST_ROUTER_NETWORK_ID)
        fixed_ips = gateway_info.get(
            RouterMapper.REST_ROUTER_FIXED_IPS
        )
        fixed_ip = fixed_ips[0]
        gateway_subnet = fixed_ip.get(RouterMapper.REST_ROUTER_SUBNET_ID)
        gateway_ip = fixed_ip.get(RouterMapper.REST_ROUTER_IP_ADDRESS)
        return network_id, gateway_subnet, gateway_ip

    @staticmethod
    def row2rest(row):
        if not row:
            return {}

        result = {
            RouterMapper.REST_ROUTER_ID: str(row.uuid),
            RouterMapper.REST_ROUTER_NAME: row.name,
            RouterMapper.REST_ROUTER_ADMIN_STATE_UP:
                row.enabled[0] if row.enabled else True,
            RouterMapper.REST_ROUTER_STATUS:
                RouterMapper.ROUTER_STATUS_ACTIVE
                if row.enabled else RouterMapper.ROUTER_STATUS_INACTIVE,
            RouterMapper.REST_ROUTER_ROUTES: [],
            RouterMapper.REST_TENANT_ID: tenant_id(),
        }
        RouterMapper._get_external_gateway_from_row(result, row)

        return result

    @staticmethod
    def _get_external_gateway_from_row(result, row):
        network = row.external_ids.get(
            RouterMapper.OVN_ROUTER_GATEWAY_NETWORK
        )

        if network:
            gateway = {
                RouterMapper.REST_ROUTER_NETWORK_ID: network
            }
            result[RouterMapper.REST_ROUTER_EXTERNAL_GATEWAY_INFO] = gateway

            subnet = row.external_ids.get(
                RouterMapper.OVN_ROUTER_GATEWAY_SUBNET
            )
            if subnet:
                external_ips = {
                    RouterMapper.REST_ROUTER_SUBNET_ID: subnet
                }
                gateway[RouterMapper.REST_ROUTER_FIXED_IPS] = [external_ips]

                ip = row.external_ids.get(
                    RouterMapper.OVN_ROUTER_GATEWAY_IP
                )
                if ip:
                    external_ips[RouterMapper.REST_ROUTER_IP_ADDRESS] = ip
        else:
            result[RouterMapper.REST_ROUTER_EXTERNAL_GATEWAY_INFO] = None

    @staticmethod
    def validate_add_rest_input(rest_data):
        RouterMapper._validate_external_gateway_info(rest_data)

    @staticmethod
    def validate_update_rest_input(rest_data):
        RouterMapper._validate_external_gateway_info(rest_data)

    @staticmethod
    def _validate_external_gateway_info(rest_data):
        gateway_info = rest_data.get(
            RouterMapper.REST_ROUTER_EXTERNAL_GATEWAY_INFO, {})
        if gateway_info:
            message = '{key} missing in the external gateway information.'
            if RouterMapper.REST_ROUTER_NETWORK_ID not in gateway_info:
                raise RestDataError(
                    message.format(key=RouterMapper.REST_ROUTER_NETWORK_ID)
                )
            if RouterMapper.REST_ROUTER_FIXED_IPS not in gateway_info:
                raise RestDataError(
                    message.format(key=RouterMapper.REST_ROUTER_FIXED_IPS)
                )
            fixed_ips = gateway_info.get(
                RouterMapper.REST_ROUTER_FIXED_IPS
            )
            if not fixed_ips or len(fixed_ips) > 1:
                raise RestDataError(
                   '{key} must have exactly one element'.format(
                       key=RouterMapper.REST_ROUTER_FIXED_IPS
                    )
                )
            if RouterMapper.REST_ROUTER_SUBNET_ID not in fixed_ips[0]:
                raise RestDataError(
                    message.format(key=RouterMapper.REST_ROUTER_SUBNET_ID)
                )
            if RouterMapper.REST_ROUTER_IP_ADDRESS not in fixed_ips[0]:
                raise RestDataError(
                    message.format(key=RouterMapper.REST_ROUTER_IP_ADDRESS)
                )
            enable_snat = gateway_info.get(
                RouterMapper.REST_ROUTER_ENABLE_SNAT,
                True
            )
            if enable_snat:
                raise NotImplementedError(
                    '{key} must set be false'.format(
                        key=RouterMapper.REST_ROUTER_ENABLE_SNAT
                    )
                )


class BaseRouterInterfaceMapper(Mapper):
    REST_ROUTERINTERFACE_ID = 'id'
    REST_ROUTERINTERFACE_SUBNET_ID = 'subnet_id'
    REST_ROUTERINTERFACE_PORT_ID = 'port_id'
    REST_ROUTERINTERFACE_SUBNET_IDS = 'subnet_ids'
    REST_ROUTERINTERFACE_NETWORK_ID = 'network_id'

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, router_id):
        subnet = rest_data.get(
            BaseRouterInterfaceMapper.REST_ROUTERINTERFACE_SUBNET_ID
        )
        port = rest_data.get(
            BaseRouterInterfaceMapper.REST_ROUTERINTERFACE_PORT_ID
        )
        return func(
            wrapped_self, router_id=router_id, subnet_id=subnet, port_id=port
        )

    @staticmethod
    def validate_add_rest_input(rest_data):
        raise MethodNotAllowedError(
            'add_router_interface POST requests are not supported'
        )

    @staticmethod
    def _validate_update(rest_data):
        subnet = rest_data.get(
            BaseRouterInterfaceMapper.REST_ROUTERINTERFACE_SUBNET_ID
        )
        port = rest_data.get(
            BaseRouterInterfaceMapper.REST_ROUTERINTERFACE_PORT_ID
        )
        if not subnet and not port:
            raise RestDataError(
                'Either {subnet} or {port} must be specified.'
                .format(
                    subnet=RouterMapper.REST_ROUTERINTERFACE_SUBNET_ID,
                    port=RouterMapper.REST_ROUTERINTERFACE_PORT_ID
                )
            )
        return subnet, port


class AddRouterInterfaceMapper(BaseRouterInterfaceMapper):

    @staticmethod
    def row2rest(row):
        if not row:
            return {}

        router_id, network_id, port_id, subnet_id = row

        return {
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_ID: router_id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_NETWORK_ID:
                network_id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_PORT_ID: port_id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_SUBNET_ID:
                subnet_id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_SUBNET_IDS: [
                subnet_id
            ],
            AddRouterInterfaceMapper.REST_TENANT_ID: tenant_id(),
        }

    @staticmethod
    def validate_update_rest_input(rest_data):
        subnet, port = BaseRouterInterfaceMapper._validate_update(rest_data)
        if subnet and port:
            raise RestDataError(
                'Subnet and port can not both be set at the same time'
            )


class RemoveRouterInterfaceMapper(BaseRouterInterfaceMapper):

    @staticmethod
    def validate_update_rest_input(rest_data):
        BaseRouterInterfaceMapper._validate_update(rest_data)


class RestDataError(BadRequestError):
    def __init__(self, message):
        self.message = message


class NetworkNameRequiredDataError(RestDataError):
    message = 'Network name is a required parameter'

    def __init__(self):
        super(NetworkNameRequiredDataError, self).__init__(self.message)


class PhysicalNetworkProviderDataError(RestDataError):
    pass


class NetworkIdRequiredForPortDataError(RestDataError):
    message = 'Network_id is a required parameter'

    def __init__(self):
        super(NetworkIdRequiredForPortDataError, self).__init__(self.message)


class PortDeviceIdRequiredDataError(RestDataError):
    message = 'Port device id must be specified to create a port'

    def __init__(self):
        super(PortDeviceIdRequiredDataError, self).__init__(self.message)


class SecurityGroupsNotSupportedDataError(RestDataError):
    message = 'Port security_groups are not supported'

    def __init__(self):
        super(SecurityGroupsNotSupportedDataError, self).__init__(self.message)


class PortSecurityNotSupportedDataError(RestDataError):
    message = 'Port port_security_enabled is not supported'

    def __init__(self):
        super(PortSecurityNotSupportedDataError, self).__init__(self.message)


class SubnetConfigError(BadRequestError):
    pass


class UnsupportedDataValueError(RestDataError):
    message = 'Setting {key} value to {value} is not supported'

    def __init__(self, key, value):
        error_message = self.message.format(key=key, value=value)
        super(UnsupportedDataValueError, self).__init__(error_message)
