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


class NetworkMapper(RestToDbRowMapper):

    @staticmethod
    def rest2row(rest_network_data, network_row):
        if 'name' in rest_network_data:
            network_row.name = rest_network_data['name']
        return network_row

    @staticmethod
    def row2rest(network_row):
        return {
            'id': str(network_row.uuid),
            'name': str(network_row.name)
        }


class PortMapper(RestToDbRowMapper):

    DEVICE_OWNER_OVIRT = 'oVirt'
    DEVICE_ID = 'device_id'
    NIC_NAME = 'nic_name'
    NAME = 'name'
    NETWORK_ID = 'network_id'

    @staticmethod
    def rest2row(rest_data, port_row):

        # Temporary value, will be set to the same value as uuid later
        port_row.name = rest_data.get(PortMapper.DEVICE_ID)
        up = rest_data.get('up')
        port_row.up = up if up is not None else True

        if 'mac_address' in rest_data:
            port_row.addresses = [rest_data['mac_address']]

        if 'enabled' in rest_data:
            port_row.enabled = rest_data['enabled']

        # For a new row 'options' will be None
        options = getattr(port_row, 'options', {})

        if PortMapper.DEVICE_ID in rest_data:
            options[PortMapper.DEVICE_ID] = rest_data[PortMapper.DEVICE_ID]
        if PortMapper.NAME in rest_data:
            options[PortMapper.NIC_NAME] = rest_data[PortMapper.NAME]
        setattr(port_row, 'options', options)

    @staticmethod
    def row2rest(row):
        port, network = row
        rest_port_data = {
            'id': str(port.uuid),
            'name': port.name,
            'device_id': str(port.options[PortMapper.DEVICE_ID]),
            'device_owner': PortMapper.DEVICE_OWNER_OVIRT,
            'network_id': str(network.uuid)
        }
        if port.addresses:
            rest_port_data['mac_address'] = port.addresses[0]
        return rest_port_data
