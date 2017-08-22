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

from uuid import UUID
import mock

import ovirt_provider_config
from ovirt_provider_config import CONFIG_SECTION_PROVIDER
from ovirt_provider_config import KEY_OPENSTACK_TENANT_ID
from ovirt_provider_config import DEFAULT_OPENSTACK_TENANT_ID
from ovndb.ovn_north import OvnNorth
from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import SubnetMapper

from ovntestlib import OvnNetworkRow
from ovntestlib import OvnPortRow
from ovntestlib import OvnSubnetRow


def _tenant_id():
    return ovirt_provider_config.get(
        CONFIG_SECTION_PROVIDER,
        KEY_OPENSTACK_TENANT_ID,
        DEFAULT_OPENSTACK_TENANT_ID
    )


@mock.patch('ovsdbapp.backend.ovs_idl.connection', autospec=False)
class TestOvnNorth(object):
    MAC_ADDRESS = '01:00:00:00:00:11'
    DEVICE_ID = 'device-id-123456'
    NIC_NAME = 'port_name'
    NETWORK_NAME = 'test_net'

    NETWORK_ID10 = UUID(int=10)
    NETWORK_ID11 = UUID(int=11)
    NETWORK_NAME10 = 'name10'
    NETWORK_NAME11 = 'name11'

    PORT_ID01 = UUID(int=1)
    PORT_ID02 = UUID(int=2)
    PORT_NAME01 = 'port1'
    PORT_NAME02 = 'port2'

    PORT_1 = OvnPortRow(
        PORT_ID01,
        addresses=MAC_ADDRESS,
        external_ids={
            PortMapper.OVN_NIC_NAME: PORT_NAME01,
            PortMapper.OVN_DEVICE_ID: str(PORT_ID01),
            PortMapper.OVN_DEVICE_OWNER: PortMapper.DEVICE_OWNER_OVIRT,
        }
    )
    PORT_2 = OvnPortRow(
        PORT_ID02,
        addresses=MAC_ADDRESS,
        external_ids={
            PortMapper.OVN_NIC_NAME: PORT_NAME02,
            PortMapper.OVN_DEVICE_ID: str(PORT_ID02),
            PortMapper.OVN_DEVICE_OWNER: PortMapper.DEVICE_OWNER_OVIRT,
        }
    )

    SUBNET_ID101 = UUID(int=101)
    SUBNET_ID102 = UUID(int=102)

    SUBNET_101 = OvnSubnetRow(SUBNET_ID101, network_id=str(NETWORK_ID10))
    SUBNET_102 = OvnSubnetRow(SUBNET_ID102)

    ports = [PORT_1, PORT_2]

    networks = [
        OvnNetworkRow(NETWORK_ID10, NETWORK_NAME10),
        OvnNetworkRow(NETWORK_ID11, NETWORK_NAME11, ports=[PORT_1, PORT_2]),
    ]

    subnets = [SUBNET_101, SUBNET_102]

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand',
        autospec=False
    )
    def test_get_networks(self, mock_ls_list, mock_connection):
        mock_ls_list.return_value.execute.return_value = TestOvnNorth.networks

        ovn_north = OvnNorth()
        result = ovn_north.list_networks()

        assert len(result) == 2
        assert result[0]['id'] == str(TestOvnNorth.NETWORK_ID10)
        assert result[0]['name'] == TestOvnNorth.NETWORK_NAME10
        assert result[0]['tenant_id'] == _tenant_id()
        assert mock_ls_list.call_count == 1
        assert mock_ls_list.return_value.execute.call_count == 1

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand',
        autospec=False
    )
    def test_get_network(self, mock_ls_get, mock_connection):
        mock_ls_get.return_value.execute.return_value = (
            OvnNetworkRow(
                TestOvnNorth.NETWORK_ID10,
                TestOvnNorth.NETWORK_NAME10
            )
        )

        ovn_north = OvnNorth()
        result = ovn_north.get_network(str(self.NETWORK_ID10))
        assert result['id'] == str(self.NETWORK_ID10)
        assert result['name'] == self.NETWORK_NAME10
        assert result['tenant_id'] == _tenant_id()
        assert mock_ls_get.call_count == 1
        assert mock_ls_get.return_value.execute.call_count == 1
        expected_ls_get_call = mock.call(ovn_north.idl, str(self.NETWORK_ID10))
        assert mock_ls_get.mock_calls[0] == expected_ls_get_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsAddCommand',
        autospec=False
    )
    def test_add_network(self, mock_add_command, mock_connection):
        mock_add_command.return_value.execute.return_value = (
            OvnNetworkRow(
                TestOvnNorth.NETWORK_ID10,
                TestOvnNorth.NETWORK_NAME10
            )
        )
        ovn_north = OvnNorth()
        rest_data = {
            NetworkMapper.REST_NETWORK_NAME: TestOvnNorth.NETWORK_NAME10
        }
        result = ovn_north.add_network(rest_data)
        assert result['id'] == str(TestOvnNorth.NETWORK_ID10)
        assert result['name'] == TestOvnNorth.NETWORK_NAME10
        assert mock_add_command.call_count == 1
        expected_add_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.NETWORK_NAME10,
            False
        )
        assert mock_add_command.mock_calls[0] == expected_add_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda x: OvnNetworkRow(
            TestOvnNorth.NETWORK_ID10,
            TestOvnNorth.NETWORK_NAME10
        )
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand',
        autospec=False
    )
    def test_update_network(self, mock_set_command, mock_connection):
        ovn_north = OvnNorth()
        rest_data = {
            NetworkMapper.REST_NETWORK_NAME: TestOvnNorth.NETWORK_NAME10
        }
        result = ovn_north.update_network(rest_data, TestOvnNorth.NETWORK_ID10)
        assert result['id'] == str(TestOvnNorth.NETWORK_ID10)
        assert result['name'] == TestOvnNorth.NETWORK_NAME10
        assert mock_set_command.call_count == 1
        expected_set_call = mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LS,
            TestOvnNorth.NETWORK_ID10,
            (NetworkMapper.REST_NETWORK_NAME, TestOvnNorth.NETWORK_NAME10)
        )
        assert mock_set_command.mock_calls[0] == expected_set_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda x: OvnNetworkRow(
            TestOvnNorth.NETWORK_ID10,
            TestOvnNorth.NETWORK_NAME10
        )
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsDelCommand',
        autospec=False
    )
    def test_delete_network(self, mock_del_command, mock_connection):
        ovn_north = OvnNorth()
        ovn_north.delete_network(TestOvnNorth.NETWORK_ID10)
        assert mock_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.NETWORK_ID10,
            False
        )
        assert mock_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand.execute',
        lambda x: TestOvnNorth.networks
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspGetCommand.execute',
        lambda x: TestOvnNorth.PORT_1
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda x: []
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspAddCommand',
        autospec=False
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand',
        autospec=False
    )
    def test_add_port(self, mock_db_set, mock_add_command, mock_connection):
        mock_add_command.return_value.execute.return_value = (
            OvnPortRow(
                TestOvnNorth.PORT_ID01,
                external_ids={
                    PortMapper.OVN_NIC_NAME: TestOvnNorth.PORT_NAME01,
                    PortMapper.OVN_DEVICE_ID: str(TestOvnNorth.PORT_ID01),
                    PortMapper.OVN_DEVICE_OWNER: PortMapper.DEVICE_OWNER_OVIRT,
                }
            )
        )
        ovn_north = OvnNorth()
        rest_data = {
            PortMapper.REST_PORT_NAME: TestOvnNorth.PORT_NAME01,
            PortMapper.REST_PORT_NETWORK_ID: str(TestOvnNorth.NETWORK_ID10),
            PortMapper.REST_PORT_DEVICE_ID: TestOvnNorth.DEVICE_ID,
            PortMapper.REST_PORT_DEVICE_OWNER: PortMapper.DEVICE_OWNER_OVIRT,
            PortMapper.REST_PORT_ADMIN_STATE_UP: True,
            PortMapper.REST_PORT_MAC_ADDRESS: TestOvnNorth.MAC_ADDRESS
        }
        ovn_north.add_port(rest_data)
        assert mock_add_command.call_count == 1
        mock_add_command.assert_called_with(
            ovn_north.idl,
            str(TestOvnNorth.NETWORK_ID10),
            TestOvnNorth.PORT_NAME01,
            None,
            None,
            False
        )

        assert mock_db_set.call_count == 6

        # mock_db_set.mock_calls[1, 3, 5, ...] is for execute() - no parameters
        assert mock_db_set.mock_calls[0] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LSP,
            str(TestOvnNorth.PORT_ID01),
            (
                OvnNorth.ROW_LSP_NAME,
                str(TestOvnNorth.PORT_ID01)
            )
        )
        assert mock_db_set.mock_calls[2] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LSP,
            TestOvnNorth.PORT_ID01,
            (
                OvnNorth.ROW_LSP_ADDRESSES,
                [TestOvnNorth.MAC_ADDRESS]
            )
        )
        assert mock_db_set.mock_calls[4] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LSP,
            TestOvnNorth.PORT_ID01,
            (
                OvnNorth.ROW_LSP_EXTERNAL_IDS,
                {PortMapper.OVN_DEVICE_ID: TestOvnNorth.DEVICE_ID}
            )
        )
        assert mock_db_set.mock_calls[6] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LSP,
            TestOvnNorth.PORT_ID01,
            (
                OvnNorth.ROW_LSP_EXTERNAL_IDS,
                {PortMapper.OVN_NIC_NAME: TestOvnNorth.PORT_NAME01}
            )
        )
        assert mock_db_set.mock_calls[8] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LSP,
            TestOvnNorth.PORT_ID01,
            (
                OvnNorth.ROW_LSP_EXTERNAL_IDS,
                {PortMapper.OVN_DEVICE_OWNER: PortMapper.DEVICE_OWNER_OVIRT}
            )
        )
        assert mock_db_set.mock_calls[10] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LSP,
            TestOvnNorth.PORT_ID01,
            (OvnNorth.ROW_LSP_ENABLED, True)
        )

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand.execute',
        lambda x: TestOvnNorth.networks
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspListCommand.execute',
        lambda x: TestOvnNorth.ports
    )
    def test_list_ports(self, mock_connection):
        ovn_north = OvnNorth()
        ports = ovn_north.list_ports()
        assert len(ports) == 2
        assert ports[0]['id'] == str(TestOvnNorth.PORT_ID01)
        assert ports[1]['id'] == str(TestOvnNorth.PORT_ID02)
        assert ports[0]['network_id'] == str(TestOvnNorth.NETWORK_ID11)
        assert ports[1]['network_id'] == str(TestOvnNorth.NETWORK_ID11)
        assert ports[0]['name'] == TestOvnNorth.PORT_NAME01
        assert ports[1]['name'] == TestOvnNorth.PORT_NAME02
        assert ports[0]['device_id'] == str(TestOvnNorth.PORT_ID01)
        assert ports[1]['device_id'] == str(TestOvnNorth.PORT_ID02)
        assert ports[0]['security_groups'] == []
        assert ports[1]['port_security_enabled'] is False
        assert ports[0]['tenant_id'] == _tenant_id()
        assert ports[1]['tenant_id'] == _tenant_id()
        assert ports[0]['fixed_ips'] == []
        assert ports[1]['fixed_ips'] == []

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspDelCommand',
        autospec=False
    )
    def test_delete_port(self, mock_del_command, mock_connection):
        ovn_north = OvnNorth()
        ovn_north.delete_port(TestOvnNorth.PORT_ID01)
        assert mock_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.PORT_ID01,
            None,
            False
        )
        assert mock_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda x: TestOvnNorth.subnets
    )
    def test_list_subnets(self, mock_connection):
        ovn_north = OvnNorth()
        result = ovn_north.list_subnets()
        assert len(result) == 2
        assert result[0]['id'] == str(TestOvnNorth.SUBNET_ID101)
        assert result[0]['network_id'] == str(TestOvnNorth.NETWORK_ID10)
        assert result[0]['tenant_id'] == _tenant_id()

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda x: TestOvnNorth.SUBNET_101
    )
    def test_get_subnets(self, mock_connection):
        ovn_north = OvnNorth()
        result = ovn_north.get_subnet(TestOvnNorth.SUBNET_ID101)
        assert result['id'] == str(TestOvnNorth.SUBNET_ID101)
        assert result['network_id'] == str(TestOvnNorth.NETWORK_ID10)

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsDelCommand',
        autospec=False
    )
    def test_delete_subnet(self, mock_del_command, mock_connection):
        ovn_north = OvnNorth()
        ovn_north.delete_subnet(TestOvnNorth.SUBNET_ID101)
        assert mock_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.SUBNET_ID101,
        )
        assert mock_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda x: TestOvnNorth.SUBNET_102
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand',
        autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsAddCommand',
        autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsSetOptionsCommand',
        autospec=False
    )
    def test_add_subnet(self, mock_setoptions_command, mock_add_command,
                        mock_dbset_command, mock_connection):
        new_subnet_id = 7
        mock_add_command.return_value.execute.return_value = new_subnet_id
        subnet_cidr = '1.1.1.0/24'
        ovn_north = OvnNorth()
        input = {
            SubnetMapper.REST_SUBNET_NAME: 'subnet_name',
            SubnetMapper.REST_SUBNET_CIDR: subnet_cidr,
            SubnetMapper.REST_SUBNET_NETWORK_ID:
                str(TestOvnNorth.NETWORK_ID10),
            SubnetMapper.REST_SUBNET_DNS_NAMESERVERS: ['1.1.1.1'],
            SubnetMapper.REST_SUBNET_GATEWAY_IP: '1.1.1.0',
        }
        result = ovn_north.add_subnet(input)
        assert result['id'] == str(TestOvnNorth.SUBNET_ID102)
        assert mock_dbset_command.call_count == 1
        assert mock_add_command.call_count == 1
        assert mock_setoptions_command.call_count == 1

        expected_dbset_call = mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LS,
            str(TestOvnNorth.NETWORK_ID10),
            (
                OvnNorth.ROW_LS_OTHER_CONFIG,
                {NetworkMapper.OVN_SUBNET: subnet_cidr}
            ),
        )
        assert mock_dbset_command.mock_calls[0] == expected_dbset_call

        expected_add_call = mock.call(
            ovn_north.idl,
            subnet_cidr,
            ovirt_name='subnet_name',
            ovirt_network_id=str(TestOvnNorth.NETWORK_ID10)
        )
        assert mock_add_command.mock_calls[0] == expected_add_call

        expected_options_call = mock.call(
            ovn_north.idl,
            new_subnet_id,
            dns_server='1.1.1.1',
            lease_time=OvnNorth._dhcp_lease_time(),
            router='1.1.1.0',
            server_id='1.1.1.0',
            server_mac=OvnNorth._dhcp_server_mac(),
            mtu=OvnNorth._dhcp_mtu()
        )
        assert mock_setoptions_command.mock_calls[0] == expected_options_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand.execute',
        lambda x: TestOvnNorth.networks
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspGetCommand.execute',
        lambda x: TestOvnNorth.PORT_1
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda x: []
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand',
        autospec=False
    )
    def test_update_subnet(self, mock_db_set, mock_connection):

        ovn_north = OvnNorth()
        rest_data = {
           SubnetMapper.REST_SUBNET_NAME: 'subnet_name',
           SubnetMapper.REST_SUBNET_ENABLE_DHCP: True,
           SubnetMapper.REST_SUBNET_NETWORK_ID: TestOvnNorth.NETWORK_ID10,
           SubnetMapper.REST_SUBNET_DNS_NAMESERVERS: ['8.8.8.8'],
           SubnetMapper.REST_SUBNET_GATEWAY_IP: '172.16.0.254',
           SubnetMapper.REST_SUBNET_IP_VERSION: 4,
           SubnetMapper.REST_SUBNET_CIDR: '172.16.0.0/24'
        }
        ovn_north.update_subnet(rest_data, TestOvnNorth.SUBNET_ID101)

        assert mock_db_set.call_count == 2

        assert mock_db_set.mock_calls[0] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_LS,
            TestOvnNorth.NETWORK_ID10,
            (
                OvnNorth.ROW_LS_OTHER_CONFIG,
                {NetworkMapper.OVN_SUBNET:
                    rest_data[SubnetMapper.REST_SUBNET_CIDR]}
            )
        )

        assert mock_db_set.mock_calls[2] == mock.call(
            ovn_north.idl,
            OvnNorth.TABLE_DHCP_Options,
            TestOvnNorth.SUBNET_ID101,
            (
                OvnNorth.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_SERVER_ID:
                    rest_data[SubnetMapper.REST_SUBNET_CIDR].split('/', 1)[0]}
            ),
            (
                OvnNorth.ROW_DHCP_CIDR,
                rest_data[SubnetMapper.REST_SUBNET_CIDR]
            ),
            (
                OvnNorth.ROW_DHCP_EXTERNAL_IDS,
                {SubnetMapper.OVN_NAME:
                    rest_data[SubnetMapper.REST_SUBNET_NAME]}
            ),
            (
                OvnNorth.ROW_DHCP_EXTERNAL_IDS,
                {SubnetMapper.OVN_NETWORK_ID:
                    rest_data[SubnetMapper.REST_SUBNET_NETWORK_ID]}
            ),
            (
                OvnNorth.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_GATEWAY:
                    rest_data[SubnetMapper.REST_SUBNET_GATEWAY_IP]}
            ),
            (
                OvnNorth.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DNS_SERVER:
                    rest_data[SubnetMapper.REST_SUBNET_DNS_NAMESERVERS][0]}
            ),
            (
                OvnNorth.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_LEASE_TIME: OvnNorth._dhcp_lease_time()}
            ),
            (
                OvnNorth.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_SERVER_MAC: OvnNorth._dhcp_server_mac()}
            )
        )
