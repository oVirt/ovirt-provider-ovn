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

from uuid import UUID

from ovndb.constants import LSP_OPTION_NETWORK_NAME
from ovndb.ovn_north_mappers import Network
from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import NetworkPort
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import SubnetMapper

from ovntestlib import assert_network_equal
from ovntestlib import assert_port_equal
from ovntestlib import assert_subnet_equal
from ovntestlib import OvnSubnetRow
from ovntestlib import OvnNetworkRow
from ovntestlib import OvnPortRow


FIXED_IP_ADDRESS = '1.1.1.1'
MAC_ADDRESS = '01:00:00:00:00:11'
NETWORK_ID1 = '1'
NETWORK_UUID = UUID(int=606)
NETWORK_NAME = 'skynet'
PORT_NAME = 'port1'
PORT_UUID = UUID(int=101)
SUBNET_ID102 = UUID(int=102)
SUBNET_CIDR = '1.1.1.0/24'


class TestOvnNorthMappers(object):
    def test_subnet_to_rest_minimal(self):
        row = OvnSubnetRow(SUBNET_ID102, cidr=SUBNET_CIDR, external_ids={
            SubnetMapper.OVN_NETWORK_ID: NETWORK_ID1
        })
        subnet = SubnetMapper.row2rest(row)
        assert_subnet_equal(subnet, row)

    def test_subnet_to_rest_with_name(self):
        row = OvnSubnetRow(SUBNET_ID102, cidr=SUBNET_CIDR)
        subnet = SubnetMapper.row2rest(row)
        assert_subnet_equal(subnet, row)

    def test_network_to_rest_minimal(self):
        ls = OvnNetworkRow(NETWORK_UUID, name=NETWORK_NAME)
        network = Network(ls=ls, localnet_lsp=None)
        network_rest_data = NetworkMapper.row2rest(network)
        assert_network_equal(network_rest_data, network)

    def test_network_to_rest_with_options(self):
        localnet_lsp = OvnPortRow(
            PORT_UUID, name=PORT_NAME,
            options={LSP_OPTION_NETWORK_NAME: PORT_NAME}
        )
        ls = OvnNetworkRow(
            NETWORK_UUID, name=NETWORK_NAME, ports=[localnet_lsp]
        )
        network = Network(ls, localnet_lsp)
        network_rest_data = NetworkMapper.row2rest(network)
        assert_network_equal(network_rest_data, network)

    def test_network_to_rest_with_tag(self):
        localnet_lsp = OvnPortRow(
            PORT_UUID, name=PORT_NAME,
            options={LSP_OPTION_NETWORK_NAME: PORT_NAME}, tag=2
        )
        ls = OvnNetworkRow(
            NETWORK_UUID, name=NETWORK_NAME, ports=[localnet_lsp]
        )
        network = Network(ls, localnet_lsp)
        network_rest_data = NetworkMapper.row2rest(network)
        assert_network_equal(network_rest_data, network)

    def test_network_to_rest_with_tag_missing_port_name(self):
        localnet_lsp = OvnPortRow(
            PORT_UUID, tag=2,
            options={LSP_OPTION_NETWORK_NAME: PORT_NAME}
        )
        ls = OvnNetworkRow(
            NETWORK_UUID, name=NETWORK_NAME, ports=[localnet_lsp]
        )
        network = Network(ls, localnet_lsp)
        network_rest_data = NetworkMapper.row2rest(network)
        assert_network_equal(network_rest_data, network)

    @staticmethod
    def __assert_port_data_equal(port_data):
        ls = OvnNetworkRow(
            NETWORK_UUID, name=NETWORK_NAME, ports=[port_data]
        )
        port = NetworkPort(port_data, ls, None, None)
        port_rest_data = PortMapper.row2rest(port)
        assert_port_equal(port_rest_data, port)

    def test_port_to_rest_minimal(self):
        port_data = OvnPortRow(
            PORT_UUID,
            name=PORT_NAME,
            external_ids={
                PortMapper.OVN_NIC_NAME: PORT_NAME,
                PortMapper.OVN_DEVICE_ID: str(PORT_UUID),
                PortMapper.OVN_DEVICE_OWNER: 'ovirt',
            },
            options={LSP_OPTION_NETWORK_NAME: PORT_NAME}
        )
        self.__assert_port_data_equal(port_data)

    def test_port_to_rest_mac_address(self):
        port_data = OvnPortRow(
            PORT_UUID,
            addresses=MAC_ADDRESS,
            name=PORT_NAME,
            external_ids={
                PortMapper.OVN_NIC_NAME: PORT_NAME,
                PortMapper.OVN_DEVICE_ID: str(PORT_UUID),
                PortMapper.OVN_DEVICE_OWNER: 'ovirt',
            },
            options={LSP_OPTION_NETWORK_NAME: PORT_NAME}
        )
        self.__assert_port_data_equal(port_data)

    def test_port_to_rest_fixed_ip(self):
        port_data = OvnPortRow(
            PORT_UUID,
            addresses=['{} {}'.format(MAC_ADDRESS, FIXED_IP_ADDRESS)],
            name=PORT_NAME,
            external_ids={
                PortMapper.OVN_NIC_NAME: PORT_NAME,
                PortMapper.OVN_DEVICE_ID: str(PORT_UUID),
                PortMapper.OVN_DEVICE_OWNER: 'ovirt',
            },
            options={LSP_OPTION_NETWORK_NAME: PORT_NAME}
        )
        self.__assert_port_data_equal(port_data)
