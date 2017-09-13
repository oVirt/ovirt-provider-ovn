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

import six

from ovirt_provider_config_common import tenant_id
from handlers.base_handler import BadRequestError


NetworkPort = namedtuple('NetworkPort', ['port', 'network'])


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

    OVN_SUBNET = 'subnet'

    @staticmethod
    def rest2row(wrapped_self, func, rest_network_data, network_id):
        name = rest_network_data.get(NetworkMapper.REST_NETWORK_NAME)
        if network_id:
            return func(
                wrapped_self,
                network_id=network_id,
                name=name
            )
        else:
            return func(
                wrapped_self,
                name=name
            )

    @staticmethod
    def row2rest(network_row):
        if not network_row:
            return {}
        return {
            NetworkMapper.REST_NETWORK_ID: str(network_row.uuid),
            NetworkMapper.REST_NETWORK_NAME: network_row.name,
            NetworkMapper.REST_TENANT_ID: tenant_id()
        }

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

    OVN_DEVICE_ID = 'ovirt_device_id'
    OVN_NIC_NAME = 'ovirt_nic_name'
    OVN_DEVICE_OWNER = 'ovirt_device_owner'
    DEVICE_OWNER_OVIRT = 'oVirt'

    @staticmethod
    def rest2row(wrapped_self, func, rest_data, port_id):
        network_id = rest_data.get(PortMapper.REST_PORT_NETWORK_ID)
        name = rest_data.get(PortMapper.REST_PORT_NAME)
        mac = rest_data.get(PortMapper.REST_PORT_MAC_ADDRESS)
        is_enabled = rest_data.get(PortMapper.REST_PORT_ADMIN_STATE_UP)
        device_id = rest_data.get(PortMapper.REST_PORT_DEVICE_ID)
        device_owner = rest_data.get(PortMapper.REST_PORT_DEVICE_OWNER)

        if port_id:
            return func(
                wrapped_self,
                port_id=port_id,
                network_id=network_id,
                name=name,
                mac=mac,
                is_enabled=is_enabled,
                device_id=device_id,
                device_owner=device_owner
            )
        else:
            return func(
                wrapped_self,
                network_id=network_id,
                name=name,
                mac=mac,
                is_enabled=is_enabled,
                device_id=device_id,
                device_owner=device_owner
            )

    @staticmethod
    def row2rest(row):
        """
            Maps the db rows (port, network) to a Json representation of
            a port.
            The 'admin_state_up' property of the port is the product
            of two values:
            - port.up - managed internally by OVN, True only if
            set explicitly to [True]
            - port.enabled - set by the user, True if empty (None) or
            set to [True]
        """
        if not row:
            return {}
        port, network = row
        rest_data = {
            PortMapper.REST_PORT_ID: str(port.uuid),
            PortMapper.REST_PORT_NAME:
                port.external_ids[PortMapper.OVN_NIC_NAME],
            PortMapper.REST_PORT_DEVICE_ID:
                str(port.external_ids[PortMapper.OVN_DEVICE_ID]),
            PortMapper.REST_PORT_DEVICE_OWNER:
                port.external_ids[PortMapper.OVN_DEVICE_OWNER],
            PortMapper.REST_PORT_NETWORK_ID: str(network.uuid),
            PortMapper.REST_PORT_SECURITY_GROUPS: [],
            PortMapper.REST_PORT_SECURITY_ENABLED: False,
            PortMapper.REST_TENANT_ID: tenant_id(),
            PortMapper.REST_PORT_FIXED_IPS: [],
            PortMapper.REST_PORT_ADMIN_STATE_UP:
                (port.up is not None and port.up[0]) and
                (port.enabled is None or port.enabled[0])
        }
        if port.addresses:
            rest_data[PortMapper.REST_PORT_MAC_ADDRESS] = port.addresses[0]
        return rest_data

    @staticmethod
    def validate_add_rest_input(rest_data):
        if PortMapper.REST_PORT_DEVICE_ID not in rest_data:
            raise PortDeviceIdRequiredDataError()
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


class SubnetMapper(Mapper):
    REST_SUBNET_ID = 'id'
    REST_SUBNET_NAME = 'name'
    REST_SUBNET_CIDR = 'cidr'
    REST_SUBNET_NETWORK_ID = 'network_id'
    REST_SUBNET_DNS_NAMESERVERS = 'dns_nameservers'
    REST_SUBNET_GATEWAY_IP = 'gateway_ip'
    REST_SUBNET_ENABLE_DHCP = 'enable_dhcp'
    REST_SUBNET_IP_VERSION = 'ip_version'

    OVN_NAME = 'ovirt_name'
    OVN_NETWORK_ID = 'ovirt_network_id'
    OVN_DNS_SERVER = 'dns_server'
    OVN_GATEWAY = 'router'
    OVN_DHCP_SERVER_ID = 'server_id'
    OVN_DHCP_SERVER_MAC = 'server_mac'
    OVN_DHCP_LEASE_TIME = 'lease_time'
    OVN_DHCP_MTU = 'mtu'

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
                cidr=cidr,
                network_id=network_id,
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
            SubnetMapper.REST_SUBNET_NAME:
                external_ids[SubnetMapper.OVN_NAME],
            SubnetMapper.REST_SUBNET_CIDR: row.cidr,
            SubnetMapper.REST_SUBNET_NETWORK_ID:
                external_ids[SubnetMapper.OVN_NETWORK_ID],
            SubnetMapper.REST_SUBNET_IP_VERSION: SubnetMapper.IP_VERSION,
            SubnetMapper.REST_TENANT_ID: tenant_id()
        }
        if SubnetMapper.OVN_GATEWAY in options:
            result[SubnetMapper.REST_SUBNET_GATEWAY_IP] = (
                options[SubnetMapper.OVN_GATEWAY]
            )
        if SubnetMapper.REST_SUBNET_DNS_NAMESERVERS in options:
            result[SubnetMapper.REST_SUBNET_DNS_NAMESERVERS] = [
                options[SubnetMapper.OVN_DNS_SERVER]
            ]

        return result

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


class RestDataError(BadRequestError):
    def __init__(self, message):
        self.message = message


class NetworkNameRequiredDataError(RestDataError):
    message = 'Network name is a required parameter'

    def __init__(self):
        super(NetworkNameRequiredDataError, self).__init__(self.message)


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
