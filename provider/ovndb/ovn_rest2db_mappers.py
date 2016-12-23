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

from ovndb.ovsdb_api import RestToDbRowMapper


EXTERNAL_IDS = 'external_ids'


class NetworkMapper(RestToDbRowMapper):

    SUBNET = 'subnet'

    @staticmethod
    def rest2row(rest_network_data, network_row):
        if 'name' in rest_network_data:
            network_row.name = rest_network_data['name']
        return network_row

    @staticmethod
    def row2rest(network_row):
        if not network_row:
            return {}
        return {
            'id': str(network_row.uuid),
            'name': str(network_row.name)
        }


class PortMapper(RestToDbRowMapper):

    DEVICE_OWNER_OVIRT = 'oVirt'
    DEVICE_ID = 'ovirt_device_id'
    REST_DEVICE_ID = 'device_id'
    NIC_NAME = 'ovirt_nic_name'
    REST_NAME = 'name'
    REST_NETWORK_ID = 'network_id'

    @staticmethod
    def rest2row(rest_data, port_row):

        # Temporary value, will be set to the same value as uuid later
        port_row.name = rest_data.get(PortMapper.REST_DEVICE_ID)
        up = rest_data.get('up')
        port_row.up = up if up is not None else True

        if 'mac_address' in rest_data:
            port_row.addresses = [rest_data['mac_address']]

        if 'enabled' in rest_data:
            port_row.enabled = rest_data['enabled']

        external_ids = getattr(port_row, EXTERNAL_IDS, {})
        if PortMapper.REST_DEVICE_ID in rest_data:
            rest_device_id = rest_data[PortMapper.REST_DEVICE_ID]
            external_ids[PortMapper.DEVICE_ID] = rest_device_id
        if PortMapper.REST_NAME in rest_data:
            external_ids[PortMapper.NIC_NAME] = rest_data[PortMapper.REST_NAME]
        setattr(port_row, EXTERNAL_IDS, external_ids)

    @staticmethod
    def row2rest(row):
        if not row:
            return {}
        port, network = row
        rest_port_data = {
            'id': str(port.uuid),
            'name': port.name,
            'device_id': str(port.external_ids[PortMapper.DEVICE_ID]),
            'device_owner': PortMapper.DEVICE_OWNER_OVIRT,
            'network_id': str(network.uuid)
        }
        if port.addresses:
            rest_port_data['mac_address'] = port.addresses[0]
        return rest_port_data


class SubnetMapper(RestToDbRowMapper):

    GATEWAY_IP = 'gateway_ip'
    CIDR = 'cidr'
    DNS = 'dns_nameservers'

    NAME = 'ovirt_name'
    NETWORK_ID = 'ovirt_network_id'
    REST_NAME = 'name'
    REST_NETWORK_ID = 'network_id'

    @staticmethod
    def rest2row(rest_subnet_data, row):
        SubnetMapper._validate_rest_input(rest_subnet_data)

        options = {
            'server_id': rest_subnet_data[SubnetMapper.CIDR].split('/', 1)[0],
            'router': rest_subnet_data[SubnetMapper.GATEWAY_IP],
        }
        if SubnetMapper.DNS in rest_subnet_data:
            dns_servers = rest_subnet_data[SubnetMapper.DNS]
            if len(dns_servers) == 1:
                options['dns_server'] = dns_servers[0]

        external_ids = {
            SubnetMapper.NAME: rest_subnet_data[SubnetMapper.REST_NAME],
            SubnetMapper.NETWORK_ID:
                rest_subnet_data[SubnetMapper.REST_NETWORK_ID]
        }

        row.cidr = rest_subnet_data['cidr']
        row.options = options
        row.external_ids = external_ids

        # TODO: add support for IP v6
        # rest_subnet_data['ip_version']
        # The current status in OVN (2016-09-30) is that
        # LS.other_config.subnet is only for IPv4

    @staticmethod
    def row2rest(row):
        if not row:
            return {}
        options = row.options
        external_ids = row.external_ids
        result = {
            'id': str(row.uuid),
            'cidr': row.cidr,
            SubnetMapper.REST_NETWORK_ID:
                external_ids[SubnetMapper.NETWORK_ID],
            'enable_dhcp': 'true',
            SubnetMapper.REST_NAME: external_ids[SubnetMapper.NAME],
            'ip_version': 4,
            'gateway_ip': options['router']
        }
        if 'dns_server' in options:
            result['dns_nameservers'] = [options['dns_server']]
        return result

    @staticmethod
    def _validate_rest_input(rest_data):
        if SubnetMapper.GATEWAY_IP not in rest_data:
            raise RestDataError('Default gateway must be specified to create'
                                ' a subnet')

        if SubnetMapper.CIDR not in rest_data:
            raise RestDataError('Cidr must be specified to create a subnet')

        if (SubnetMapper.DNS in rest_data and
                len(rest_data[SubnetMapper.DNS]) > 1):
            raise RestDataError('Only one DNS can be specified.')


class RestDataError(Exception):
    pass
