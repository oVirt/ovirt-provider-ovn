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

import abc
from collections import namedtuple
from functools import wraps

from netaddr import AddrFormatError
from netaddr import IPNetwork
import six

import constants as ovnconst
import neutron.constants as neutron_constants
import neutron.ip as ip_utils
from ovirt_provider_config_common import dhcp_mtu
from ovirt_provider_config_common import tenant_id
from ovirt_provider_config_common import max_allowed_mtu
from handlers.base_handler import MethodNotAllowedError
from handlers.base_handler import BadRequestError


NetworkPort = namedtuple('NetworkPort', ['lsp', 'ls', 'dhcp_options', 'lrp'])
Network = namedtuple('Network', ['ls', 'localnet_lsp'])
Router = namedtuple(
    'Router', ['lr', 'ext_gw_ls_id', 'ext_gw_dhcp_options_id', 'gw_ip']
)
RouterInterface = namedtuple(
    'RouterInterface', ['id', 'ls_id', 'lsp_id', 'dhcp_options_id']
)
SecurityGroup = namedtuple('SecurityGroup', ['sec_group', 'sec_group_rules'])


@six.add_metaclass(abc.ABCMeta)
class Mapper(object):

    REST_TENANT_ID = 'tenant_id'
    REST_PROJECT_ID = 'project_id'

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
    def validate_keys(input_keys, mandatory_data, optional_data):
        missing_data = mandatory_data - input_keys
        all_allowed_data = mandatory_data | optional_data
        invalid_data = input_keys - all_allowed_data
        if missing_data:
            raise MandatoryDataMissing(missing_data)
        elif invalid_data:
            raise InvalidRestData(invalid_data)

    @staticmethod
    def validate_add_rest_input(rest_data):
        raise NotImplementedError()

    @staticmethod
    def validate_update_rest_input(rest_data):
        raise NotImplementedError()

    @staticmethod
    def _boolean_or_exception(attribute_name, boolean_value):
        if not isinstance(boolean_value, bool):
            raise RestDataError('{attr} must be of type bool'.format(
                attr=attribute_name
            ))

    @staticmethod
    def _str2bool(boolean_string):
        return boolean_string.lower() == 'true'

    @staticmethod
    def set_from_external_ids(external_ids, mappings):
        return {
            rest_key: external_ids.get(ext_id_key)
            for rest_key, ext_id_key in mappings.items()
        }


class NetworkMapper(Mapper):
    # The names of properties received/sent in a REST request
    REST_MTU = 'mtu'
    REST_NETWORK_ID = 'id'
    REST_NETWORK_NAME = 'name'
    REST_STATUS = 'status'
    REST_PROVIDER_NETWORK_TYPE = 'provider:network_type'
    REST_PROVIDER_PHYSICAL_NETWORK = 'provider:physical_network'
    REST_PROVIDER_SEGMENTATION_ID = 'provider:segmentation_id'
    REST_PORT_SECURITY_ENABLED = 'port_security_enabled'

    OVN_MTU = 'mtu'
    OVN_NETWORK_NAME = 'ovirt_network_name'
    OVN_NETWORK_PORT_SECURITY = 'ovirt_port_security'
    NETWORK_TYPE_FLAT = 'flat'
    NETWORK_TYPE_VLAN = 'vlan'

    OVN_SUBNET = 'subnet'
    OVN_IPV6_PREFIX = 'ipv6_prefix'

    NETWORK_STATUS_ACTIVE = 'ACTIVE'

    @staticmethod
    def rest2row(wrapped_self, func, rest_network_data, network_id):
        network_name = rest_network_data.get(NetworkMapper.REST_NETWORK_NAME)
        provider_physical_network = rest_network_data.get(
            NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK)
        provider_segmentation_id = rest_network_data.get(
            NetworkMapper.REST_PROVIDER_SEGMENTATION_ID)
        mtu = rest_network_data.get(NetworkMapper.REST_MTU)
        port_security = rest_network_data.get(
            NetworkMapper.REST_PORT_SECURITY_ENABLED
        )
        if network_id:
            return func(
                wrapped_self,
                network_id,
                name=network_name,
                localnet=provider_physical_network,
                vlan=provider_segmentation_id,
                mtu=mtu,
                port_security_enabled=port_security
            )
        return func(
            wrapped_self,
            name=network_name,
            localnet=provider_physical_network,
            vlan=provider_segmentation_id,
            mtu=mtu,
            port_security_enabled=port_security
        )

    @staticmethod
    def row2rest(network):
        if not network:
            return {}
        ls, localnet_lsp = network.ls, network.localnet_lsp
        network_name = ls.external_ids.get(
            NetworkMapper.OVN_NETWORK_NAME
        )
        result = {
            NetworkMapper.REST_NETWORK_ID: str(ls.uuid),
            NetworkMapper.REST_NETWORK_NAME: network_name or ls.name,
            NetworkMapper.REST_TENANT_ID: tenant_id(),
            NetworkMapper.REST_STATUS: NetworkMapper.NETWORK_STATUS_ACTIVE,
            NetworkMapper.REST_PORT_SECURITY_ENABLED: Mapper._str2bool(
                str(ls.external_ids.get(
                    NetworkMapper.OVN_NETWORK_PORT_SECURITY, False
                ))
            )
        }
        result[NetworkMapper.REST_MTU] = int(
            ls.external_ids.get(NetworkMapper.OVN_MTU, dhcp_mtu())
        )
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
        NetworkMapper._validate_rest_input(rest_data, check_name=False)

    @staticmethod
    def _validate_rest_input(rest_data, check_name=True):
        if check_name and NetworkMapper.REST_NETWORK_NAME not in rest_data:
            raise NetworkNameRequiredDataError()
        Mapper._boolean_or_exception(
            NetworkMapper.REST_PORT_SECURITY_ENABLED,
            rest_data.get(NetworkMapper.REST_PORT_SECURITY_ENABLED, False)
        )
        NetworkMapper._validate_rest_input_provider_network(rest_data)
        NetworkMapper._validate_rest_input_max_mtu(
            rest_data.get(NetworkMapper.REST_MTU)
        )

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

    @staticmethod
    def _validate_rest_input_max_mtu(mtu):
        configured_max_mtu = max_allowed_mtu()
        if configured_max_mtu != 0 and mtu > configured_max_mtu:
            raise InvalidMtuDataError(
                'Requested MTU is too big, maximum is {max_mtu}'.format(
                    max_mtu=configured_max_mtu
                )
            )


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
    OVN_SECURITY_GROUPS = 'ovirt_security_groups'
    DEVICE_OWNER_ROUTER = 'network:router_interface'
    DEVICE_OWNER_ROUTER_GATEWAY = 'network:router_gateway'

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
        port_security = rest_data.get(PortMapper.REST_PORT_SECURITY_ENABLED)
        security_groups = rest_data.get(PortMapper.REST_PORT_SECURITY_GROUPS)

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
                port_security=port_security,
                security_groups=security_groups
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
                port_security=port_security,
                security_groups=security_groups
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
            PortMapper.REST_PORT_SECURITY_GROUPS: lsp.external_ids.get(
                PortMapper.OVN_SECURITY_GROUPS, ''
            ).split(),
            PortMapper.REST_PORT_SECURITY_ENABLED: len(lsp.port_security) > 0,
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
            binding_host = lsp.options[PortMapper.OVN_REQUESTED_CHASSIS]
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
        Mapper._boolean_or_exception(
            PortMapper.REST_PORT_ADMIN_STATE_UP,
            rest_data.get(PortMapper.REST_PORT_ADMIN_STATE_UP, False)
        )
        Mapper._boolean_or_exception(
            PortMapper.REST_PORT_SECURITY_ENABLED,
            rest_data.get(PortMapper.REST_PORT_SECURITY_ENABLED, False)
        )

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
            ip_addr = fixed_ips[0].get(PortMapper.REST_PORT_IP_ADDRESS)
            if (
                    ip_addr is not None and
                    ip_utils.get_ip_version(ip_addr) is None
            ):
                raise RestDataError(
                    'Invalid IP address: {}'.format(ip_addr)
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
    REST_SUBNET_IPV6_ADDRESS_MODE = 'ipv6_address_mode'

    OVN_NAME = 'ovirt_name'
    OVN_NETWORK_ID = 'ovirt_network_id'
    OVN_DNS_SERVER = 'dns_server'
    OVN_GATEWAY = 'router'
    OVN_DHCP_SERVER_ID = 'server_id'
    OVN_DHCP_SERVER_MAC = 'server_mac'
    OVN_DHCP_LEASE_TIME = 'lease_time'
    OVN_DHCP_MTU = 'mtu'
    OVN_GATEWAY_ROUTER_ID = 'gateway_router'
    OVN_IP_VERSION = 'ip_version'
    OVN_IPV6_ADDRESS_MODE = 'ovirt_ipv6_address_mode'

    IP_VERSION_4 = 4
    IP_VERSION_6 = 6
    ALLOWED_IP_VERSIONS = [IP_VERSION_4, IP_VERSION_6]

    IPV6_ADDRESS_MODE_STATEFUL = 'dhcpv6_stateful'

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, subnet_id):
        name = rest_data.get(SubnetMapper.REST_SUBNET_NAME)
        cidr = rest_data.get(SubnetMapper.REST_SUBNET_CIDR)
        network_id = rest_data.get(SubnetMapper.REST_SUBNET_NETWORK_ID)
        dnses = rest_data.get(SubnetMapper.REST_SUBNET_DNS_NAMESERVERS)
        dns = dnses[0] if dnses else None
        gateway = rest_data.get(SubnetMapper.REST_SUBNET_GATEWAY_IP)
        ip_version = rest_data.get(SubnetMapper.REST_SUBNET_IP_VERSION)
        ipv6_address_mode = rest_data.get(
            SubnetMapper.REST_SUBNET_IPV6_ADDRESS_MODE
        )

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
                ip_version=ip_version,
                ipv6_address_mode=ipv6_address_mode
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
            SubnetMapper.REST_SUBNET_IP_VERSION: int(
                external_ids.get(
                    SubnetMapper.OVN_IP_VERSION,
                    SubnetMapper.IP_VERSION_4
                )
            ),
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
        if SubnetMapper.OVN_IPV6_ADDRESS_MODE in external_ids:
            result[SubnetMapper.REST_SUBNET_IPV6_ADDRESS_MODE] = external_ids[
                SubnetMapper.OVN_IPV6_ADDRESS_MODE
            ]

        return result

    @staticmethod
    def get_allocation_pool(cidr):
        ip_network = IPNetwork(cidr)
        if ip_network.size > 2:
            return {
                SubnetMapper.REST_SUBNET_ALLOCATION_POOLS_START:
                    str(ip_network[2]),
                SubnetMapper.REST_SUBNET_ALLOCATION_POOLS_STOP:
                    str(ip_network[-1])
            }

    @staticmethod
    def validate_add_rest_input(rest_data):
        SubnetMapper._validate_common(rest_data)
        if SubnetMapper.REST_SUBNET_IP_VERSION not in rest_data:
            raise BadRequestError('Missing \'ip_version\' attribute')
        SubnetMapper._validate_ip_version_consistency(
            rest_data.get(SubnetMapper.REST_SUBNET_IP_VERSION),
            cidr=rest_data.get(SubnetMapper.REST_SUBNET_CIDR),
            gateway=rest_data.get(SubnetMapper.REST_SUBNET_GATEWAY_IP)
        )

    @staticmethod
    def validate_update_rest_input(rest_data):
        SubnetMapper._validate_common(rest_data)

    @staticmethod
    def _validate_ip_version_consistency(ip_version, cidr, gateway):
        if ip_version not in SubnetMapper.ALLOWED_IP_VERSIONS:
            raise BadRequestError('\'ip_version\' must be either 4 or 6')
        cidr_ip_version = IPNetwork(cidr).version
        gateway_ip_version = IPNetwork(gateway).version if gateway else None
        if len(
                {
                    ip_version, cidr_ip_version,
                    gateway_ip_version or ip_version
                }
        ) is not 1:
            raise BadRequestError(
                'The provided ip_version [{ip}] does not match the supplied '
                'cidr={cidr} or gateway={gateway}'.format(
                    ip=ip_version, cidr=cidr, gateway=gateway
                )
            )

    @staticmethod
    def _validate_common(rest_data):
        if (SubnetMapper.REST_SUBNET_ENABLE_DHCP in rest_data and
           not rest_data[SubnetMapper.REST_SUBNET_ENABLE_DHCP]):
            raise UnsupportedDataValueError(
                SubnetMapper.REST_SUBNET_ENABLE_DHCP,
                False
            )
        if (SubnetMapper.REST_SUBNET_IPV6_ADDRESS_MODE in rest_data and
                rest_data.get(SubnetMapper.REST_SUBNET_IPV6_ADDRESS_MODE)
                != SubnetMapper.IPV6_ADDRESS_MODE_STATEFUL):
            raise UnsupportedDataValueError(
                SubnetMapper.REST_SUBNET_IPV6_ADDRESS_MODE,
                rest_data.get(SubnetMapper.REST_SUBNET_IPV6_ADDRESS_MODE),
                [SubnetMapper.IPV6_ADDRESS_MODE_STATEFUL]
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

    REST_ROUTER_ROUTES = 'routes'
    REST_ROUTER_DESTINATION = 'destination'
    REST_ROUTER_NEXTHOP = 'nexthop'

    OVN_ROUTER_GATEWAY_PORT = 'ovirt_gateway_port'

    ROUTER_STATUS_ACTIVE = 'ACTIVE'
    ROUTER_STATUS_INACTIVE = 'INACTIVE'

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, router_id):
        name = rest_data.get(RouterMapper.REST_ROUTER_NAME)
        enabled = rest_data.get(RouterMapper.REST_ROUTER_ADMIN_STATE_UP, True)
        routes = rest_data.get(RouterMapper.REST_ROUTER_ROUTES)

        network, subnet, ip = RouterMapper._get_external_gateway_from_rest(
            rest_data
        )

        if router_id:
            return func(
                wrapped_self, router_id=router_id, name=name, enabled=enabled,
                network_id=network, gateway_subnet=subnet,
                gateway_ip=ip, routes=routes
            )
        else:
            return func(
                wrapped_self, name=name, enabled=enabled,
                network_id=network, gateway_subnet=subnet,
                gateway_ip=ip, routes=routes
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
    def row2rest(router):
        if not router:
            return {}
        row = router.lr
        result = {
            RouterMapper.REST_ROUTER_ID: str(row.uuid),
            RouterMapper.REST_ROUTER_NAME: row.name,
            RouterMapper.REST_ROUTER_ADMIN_STATE_UP:
                row.enabled[0] if row.enabled else True,
            RouterMapper.REST_ROUTER_STATUS:
                RouterMapper.ROUTER_STATUS_ACTIVE
                if row.enabled else RouterMapper.ROUTER_STATUS_INACTIVE,
            RouterMapper.REST_TENANT_ID: tenant_id(),
            RouterMapper.REST_ROUTER_EXTERNAL_GATEWAY_INFO:
                RouterMapper._get_external_gateway_from_row(router),
            RouterMapper.REST_ROUTER_ROUTES:
                RouterMapper._get_routes_from_row(row.static_routes),
        }

        return result

    @staticmethod
    def _get_routes_from_row(routes):
        return [
            {
                RouterMapper.REST_ROUTER_DESTINATION:
                    route.ip_prefix,
                RouterMapper.REST_ROUTER_NEXTHOP:
                    route.nexthop
            }
            for route in routes
        ]

    @staticmethod
    def _get_external_gateway_from_row(router):
        if not router.ext_gw_ls_id:
            return None
        return {
            RouterMapper.REST_ROUTER_NETWORK_ID: router.ext_gw_ls_id,
            RouterMapper.REST_ROUTER_ENABLE_SNAT: False,
            RouterMapper.REST_ROUTER_FIXED_IPS: [
                {
                    RouterMapper.REST_ROUTER_SUBNET_ID:
                        router.ext_gw_dhcp_options_id,
                    RouterMapper.REST_ROUTER_IP_ADDRESS: router.gw_ip
                }
            ]
        }

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
        routes = rest_data.get(RouterMapper.REST_ROUTER_ROUTES)
        if routes:
            for route in routes:
                has_required_fields = (
                    type(route) is dict and
                    route.get(RouterMapper.REST_ROUTER_NEXTHOP) is not None and
                    route.get(RouterMapper.REST_ROUTER_DESTINATION) is not None
                )
                if not has_required_fields:
                    raise RestDataError(
                        'Static route must have {destination} and {nexthop} '
                        'specified.'.format(
                            destination=RouterMapper.REST_ROUTER_DESTINATION,
                            nexthop=RouterMapper.REST_ROUTER_NEXTHOP
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
    def row2rest(row):
        if not row:
            return {}

        return {
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_ID: row.id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_NETWORK_ID:
                row.ls_id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_PORT_ID: row.lsp_id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_SUBNET_ID:
                row.dhcp_options_id,
            AddRouterInterfaceMapper.REST_ROUTERINTERFACE_SUBNET_IDS: [
                row.dhcp_options_id
            ],
            AddRouterInterfaceMapper.REST_TENANT_ID: tenant_id(),
        }

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


class MandatoryDataMissing(RestDataError):
    message = 'Mandatory data {attributes} is missing'

    def __init__(self, missing_elements):
        super(MandatoryDataMissing, self).__init__(
            self.message.format(
                attributes=', '.join(missing_elements)
            )
        )


class InvalidRestData(RestDataError):
    message = 'Invalid data found: {attributes}'

    def __init__(self, invalid_elements):
        super(InvalidRestData, self).__init__(
            self.message.format(
                attributes=', '.join(invalid_elements)
            )
        )


class NetworkNameRequiredDataError(RestDataError):
    message = 'Network name is a required parameter'

    def __init__(self):
        super(NetworkNameRequiredDataError, self).__init__(self.message)


class InvalidMtuDataError(RestDataError):
    pass


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


class PortSecurityNotSupportedDataError(RestDataError):
    message = 'Port port_security_enabled is not supported'

    def __init__(self):
        super(PortSecurityNotSupportedDataError, self).__init__(self.message)


class SubnetConfigError(BadRequestError):
    pass


class UnsupportedDataValueError(RestDataError):
    message = 'Setting {key} value to {value} is not supported'
    extra_msg = '. Allowed values are: {allowed_values}'

    def __init__(self, key, value, supported_values=None):
        error_message = (
                self.message.format(key=key, value=value) +
                self.extra_msg.format(allowed_values=supported_values)
                if supported_values else ""
        )
        super(UnsupportedDataValueError, self).__init__(error_message)


class SecurityGroupMandatoryDataMissing(RestDataError):
    message = 'Mandatory data {} is missing'

    def __init__(self, missing_elements):
        super(SecurityGroupMandatoryDataMissing, self).__init__(
            self.message.format(', '.join(missing_elements))
        )


class SecurityGroupInvalidRestData(RestDataError):
    message = 'Invalid data found: {}'

    def __init__(self, invalid_elements):
        super(SecurityGroupInvalidRestData, self).__init__(
            self.message.format(', '.join(invalid_elements))
        )


class SecurityGroupMapper(Mapper):
    REST_SEC_GROUP_ID = 'id'
    REST_SEC_GROUP_NAME = 'name'

    REST_SEC_GROUP_DESC = 'description'

    REST_SEC_GROUP_CREATED_AT = 'created_at'
    REST_SEC_GROUP_UPDATED_AT = 'updated_at'
    REST_SEC_GROUP_REVISION_NR = 'revision_number'
    REST_SEC_GROUP_RULES = 'security_group_rules'
    REST_SEC_GROUP_TAGS = 'tags'

    OVN_SECURITY_GROUP_CREATE_TS = 'ovirt_created_at'
    OVN_SECURITY_GROUP_DESCRIPTION = 'ovirt_description'
    OVN_SECURITY_GROUP_NAME = 'ovirt_sec_group_name'
    OVN_SECURITY_GROUP_PROJECT = 'ovirt_project_id'
    OVN_SECURITY_GROUP_REV_NUMBER = 'ovirt_revision_number'
    OVN_SECURITY_GROUP_TENANT = 'ovirt_tenant_id'
    OVN_SECURITY_GROUP_UPDATE_TS = 'ovirt_updated_at'

    _mandatory_add_data = set([REST_SEC_GROUP_NAME])
    _optional_add_data = set(
        [REST_SEC_GROUP_DESC, Mapper.REST_TENANT_ID, Mapper.REST_PROJECT_ID]
    )
    _mandatory_update_data = set()
    _optional_update_data = set([REST_SEC_GROUP_NAME, REST_SEC_GROUP_DESC])
    optional_attr_ext_id_mapper = {
        REST_SEC_GROUP_CREATED_AT: OVN_SECURITY_GROUP_CREATE_TS,
        REST_SEC_GROUP_UPDATED_AT: OVN_SECURITY_GROUP_UPDATE_TS,
        Mapper.REST_PROJECT_ID: OVN_SECURITY_GROUP_PROJECT,
        Mapper.REST_TENANT_ID: OVN_SECURITY_GROUP_TENANT,
        REST_SEC_GROUP_DESC: OVN_SECURITY_GROUP_DESCRIPTION
    }

    @staticmethod
    def row2rest(security_group):
        if not security_group:
            return {}

        group_data = security_group.sec_group
        result = {
            SecurityGroupMapper.REST_SEC_GROUP_ID: str(group_data.uuid),
            SecurityGroupMapper.REST_SEC_GROUP_RULES: [
                SecurityGroupRuleMapper.row2rest(rule)
                for rule in security_group.sec_group_rules
            ],
            SecurityGroupMapper.REST_SEC_GROUP_TAGS: [],
            SecurityGroupMapper.REST_SEC_GROUP_REVISION_NR: int(
                group_data.external_ids[
                    SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER
                ]
            )
        }
        rest_optional_values = SecurityGroupMapper.set_from_external_ids(
            group_data.external_ids,
            SecurityGroupMapper.optional_attr_ext_id_mapper
        )
        result.update(rest_optional_values)
        result[SecurityGroupMapper.REST_SEC_GROUP_NAME] = (
            group_data.external_ids.get(
                SecurityGroupMapper.OVN_SECURITY_GROUP_NAME
            )
        )

        return result

    @staticmethod
    def rest2row(wrapped_self, func, rest_sec_group_data, security_group_id):
        if security_group_id:
            return func(
                wrapped_self,
                security_group_id,
                rest_sec_group_data[SecurityGroupMapper.REST_SEC_GROUP_NAME],
                rest_sec_group_data.get(
                    SecurityGroupMapper.REST_SEC_GROUP_DESC
                )
            )
        else:
            return func(
                wrapped_self,
                rest_sec_group_data[SecurityGroupMapper.REST_SEC_GROUP_NAME],
                rest_sec_group_data.get(
                    SecurityGroupMapper.REST_PROJECT_ID
                ),
                rest_sec_group_data.get(
                    SecurityGroupMapper.REST_TENANT_ID
                ),
                rest_sec_group_data.get(
                    SecurityGroupMapper.REST_SEC_GROUP_DESC
                )
            )

    @classmethod
    def validate_add_rest_input(cls, rest_data):
        cls.validate_keys(
            set(rest_data.keys()),
            cls._mandatory_add_data,
            cls._optional_add_data
        )

    @classmethod
    def validate_update_rest_input(cls, rest_data):
        cls.validate_keys(
            set(rest_data.keys()),
            cls._mandatory_update_data,
            cls._optional_update_data
        )


class SecurityGroupRuleMapper(Mapper):
    REST_SEC_GROUP_RULE_ID = 'id'
    REST_SEC_GROUP_RULE_DIRECTION = 'direction'
    REST_SEC_GROUP_RULE_PROTOCOL = 'protocol'
    REST_SEC_GROUP_RULE_ETHERTYPE = 'ethertype'
    REST_SEC_GROUP_RULE_PORT_RANGE_MAX = 'port_range_max'
    REST_SEC_GROUP_RULE_PORT_RANGE_MIN = 'port_range_min'
    REST_SEC_GROUP_RULE_IP_PREFIX = 'remote_ip_prefix'
    REST_SEC_GROUP_RULE_SEC_GROUP_ID = 'security_group_id'
    REST_SEC_GROUP_RULE_DESCRIPTION = 'description'
    REST_SEC_GROUP_RULE_REMOTE_GROUP = 'remote_group_id'

    OVN_SEC_GROUP_RULE_PROTOCOL = 'ovirt_protocol'
    OVN_SEC_GROUP_RULE_ETHERTYPE = 'ovirt_ethertype'
    OVN_SEC_GROUP_RULE_MAX_PORT = 'ovirt_max_port'
    OVN_SEC_GROUP_RULE_MIN_PORT = 'ovirt_min_port'
    OVN_SEC_GROUP_RULE_IP_PREFIX = 'ovirt_ip_prefix'
    OVN_SEC_GROUP_RULE_SEC_GROUP_ID = 'ovirt_port_group_id'
    OVN_SEC_GROUP_RULE_DESCRIPTION = 'ovirt_rule_description'
    OVN_SEC_GROUP_RULE_REMOTE_GROUP_ID = 'ovirt_remote_group_id'

    _mandatory_add_data = set(
        [REST_SEC_GROUP_RULE_DIRECTION, REST_SEC_GROUP_RULE_SEC_GROUP_ID]
    )
    _optional_add_data = set([
        REST_SEC_GROUP_RULE_PROTOCOL, REST_SEC_GROUP_RULE_ETHERTYPE,
        REST_SEC_GROUP_RULE_PORT_RANGE_MAX, REST_SEC_GROUP_RULE_PORT_RANGE_MIN,
        REST_SEC_GROUP_RULE_IP_PREFIX, REST_SEC_GROUP_RULE_DESCRIPTION,
        REST_SEC_GROUP_RULE_REMOTE_GROUP
    ])
    optional_attr_ext_id_mapper = {
        REST_SEC_GROUP_RULE_DESCRIPTION: OVN_SEC_GROUP_RULE_DESCRIPTION,
        REST_SEC_GROUP_RULE_ETHERTYPE: OVN_SEC_GROUP_RULE_ETHERTYPE,
        REST_SEC_GROUP_RULE_IP_PREFIX: OVN_SEC_GROUP_RULE_IP_PREFIX,
        REST_SEC_GROUP_RULE_PORT_RANGE_MAX: OVN_SEC_GROUP_RULE_MAX_PORT,
        REST_SEC_GROUP_RULE_PORT_RANGE_MIN: OVN_SEC_GROUP_RULE_MIN_PORT,
        REST_SEC_GROUP_RULE_PROTOCOL: OVN_SEC_GROUP_RULE_PROTOCOL,
        REST_SEC_GROUP_RULE_REMOTE_GROUP: OVN_SEC_GROUP_RULE_REMOTE_GROUP_ID
    }

    @staticmethod
    def row2rest(rule):
        if not rule:
            return {}

        result = {
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_ID:
                str(rule.uuid),
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_DIRECTION:
                neutron_constants.OVN_TO_API_DIRECTION_MAPPER[rule.direction],
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_SEC_GROUP_ID:
                rule.external_ids[
                    SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID
                ]
        }
        optional_rest_values = SecurityGroupRuleMapper.set_from_external_ids(
            rule.external_ids,
            SecurityGroupRuleMapper.optional_attr_ext_id_mapper
        )
        result.update(optional_rest_values)
        return result

    @classmethod
    def validate_add_rest_input(cls, rest_data):
        cls.validate_keys(
            set(rest_data.keys()),
            cls._mandatory_add_data,
            cls._optional_add_data
        )
        if (
                rest_data.get(
                    SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_IP_PREFIX
                ) and
                rest_data.get(
                    SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_REMOTE_GROUP
                )
        ):
            raise BadRequestError(
                'Only remote_ip_prefix or remote_group_id may be provided.'
            )
        prefix = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_IP_PREFIX
        )
        if prefix:
            try:
                addr_or_prefix = IPNetwork(prefix, implicit_prefix=True)
            except AddrFormatError as afe:
                raise BadRequestError(afe.message)

            ether_type = rest_data.get(
                    SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_ETHERTYPE
            )

            if ether_type != 'IPv{version}'.format(
                    version=addr_or_prefix.version
            ):
                raise BadRequestError(
                    'Conflicting value ethertype '
                    '{ether_type} for CIDR {cidr}'.format(
                        ether_type=ether_type, cidr=prefix
                    )
                )

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, entity_id):
        security_group_id = rest_data[
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_SEC_GROUP_ID
        ]
        direction = rest_data[
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_DIRECTION
        ]
        description = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_DESCRIPTION
        )
        ether_type = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_ETHERTYPE
        )
        rest_port_max = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_PORT_RANGE_MAX
        )
        port_max = int(rest_port_max) if rest_port_max else None
        rest_port_min = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_PORT_RANGE_MIN
        )
        port_min = int(rest_port_min) if rest_port_min else None
        protocol = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_PROTOCOL
        )
        ip_prefix = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_IP_PREFIX
        )
        remote_group_name = rest_data.get(
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_REMOTE_GROUP
        )
        return func(
            wrapped_self, security_group_id, direction, description,
            ether_type, port_min, port_max, ip_prefix, protocol,
            remote_group_name
        )
