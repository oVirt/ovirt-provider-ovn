# coding=utf-8
# Copyright 2017-2021 Red Hat, Inc.
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
import unittest.mock as mock
import pytest

from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound
import constants as ovnconst
from handlers.base_handler import BadRequestError
from handlers.base_handler import ConflictError
import neutron.constants as neutron_constants
from neutron.neutron_api_mappers import InvalidRestData
from neutron.neutron_api_mappers import MandatoryDataMissing
from neutron.neutron_api_mappers import Network
from neutron.neutron_api_mappers import NetworkMapper
from neutron.neutron_api_mappers import NetworkPort
from neutron.neutron_api_mappers import PortMapper
from neutron.neutron_api_mappers import SecurityGroup
from neutron.neutron_api_mappers import SecurityGroupRule
from neutron.neutron_api_mappers import SecurityGroupMapper
from neutron.neutron_api_mappers import SecurityGroupRuleMapper
from neutron.neutron_api_mappers import SubnetConfigError
from neutron.neutron_api_mappers import SubnetMapper
from neutron.neutron_api_mappers import UnsupportedDataValueError
from neutron.neutron_api import NeutronApi
from ovirt_provider_config_common import dhcp_lease_time
from ovirt_provider_config_common import dhcp_mtu
from ovirt_provider_config_common import dhcp_server_mac
from ovirt_provider_config_common import tenant_id

from ovntestlib import assert_network_equal
from ovntestlib import assert_port_equal
from ovntestlib import assert_security_group_equal
from ovntestlib import assert_security_group_rule_equal
from ovntestlib import assert_subnet_equal
from ovntestlib import NetworkApiInputMaker
from ovntestlib import PortApiInputMaker
from ovntestlib import SecurityGroupApiInputMaker
from ovntestlib import SecurityGroupRuleApiInputMaker
from ovntestlib import SubnetApiInputMaker
from ovntestlib import OvnNetworkRow
from ovntestlib import OvnPortRow
from ovntestlib import OvnRouterPort
from ovntestlib import OvnRouterRow
from ovntestlib import OvnSecurityGroupRow
from ovntestlib import OvnSecurityGroupRuleRow
from ovntestlib import OvnSubnetRow


@mock.patch('ovsdbapp.backend.ovs_idl.connection', autospec=False)
class TestOvnNorth(object):
    MAC_ADDRESS = '01:00:00:00:00:11'
    DEVICE_ID = 'device-id-123456'
    NIC_NAME = 'port_name'
    NETWORK_NAME = 'test_net'
    LOCALNET_NAME = 'localnet'
    LOCALNET_VLAN = 10
    DEVICE_OWNER_OVIRT = 'oVirt'
    SUBNET_CIDR = '1.1.1.0/24'
    SUBNET_IPV6_CIDR = 'bef0:1234:a890:5678::/64'
    SUBNET_IPV6_GATEWAY = 'bef0:1234:a890:5678::1'
    VALUE_NETWORK_MTU = 32854

    NETWORK_ID10 = UUID(int=10)
    NETWORK_ID11 = UUID(int=11)
    NETWORK_ID12 = UUID(int=12)
    NETWORK_IDMTU = UUID(int=123)
    NETWORK_ID_UNICODE = UUID(int=456)
    NETWORK_NAME10 = 'name10'
    NETWORK_NAME11 = 'name11'
    NETWORK_NAME12 = 'name12'
    NETWORK_NAMEMTU = 'nameMTU'
    NETWORK_NAME_UNICODE = u'רשתחיצונית'

    PORT_BINDING_ID = 'bee7-15900d-bee7-1590d'

    PORT_ID01 = UUID(int=1)
    PORT_ID02 = UUID(int=2)
    PORT_ID03 = UUID(int=3)
    PORT_NAME01 = 'port1'
    PORT_NAME02 = 'port2'
    PORT_NAME03 = 'port3'

    PORT_NAME01_FIXED_IP = "1.1.1.1"
    PORT_NAME01_FIXED_IPS = [
        {PortMapper.REST_PORT_IP_ADDRESS: PORT_NAME01_FIXED_IP}
    ]

    PORT_1 = OvnPortRow(
        PORT_ID01,
        addresses=MAC_ADDRESS,
        external_ids={
            PortMapper.OVN_NIC_NAME: PORT_NAME01,
            PortMapper.OVN_DEVICE_ID: str(PORT_ID01),
            PortMapper.OVN_DEVICE_OWNER: DEVICE_OWNER_OVIRT,
        },
    )
    PORT_2 = OvnPortRow(
        PORT_ID02,
        addresses=MAC_ADDRESS,
        external_ids={
            PortMapper.OVN_NIC_NAME: PORT_NAME02,
            PortMapper.OVN_DEVICE_ID: str(PORT_ID02),
            PortMapper.OVN_DEVICE_OWNER: DEVICE_OWNER_OVIRT,
        },
    )

    PORT_3 = OvnPortRow(
        PORT_ID03,
        addresses=MAC_ADDRESS,
        external_ids={
            PortMapper.OVN_NIC_NAME: PORT_NAME03,
            PortMapper.OVN_DEVICE_ID: str(PORT_ID03),
            PortMapper.OVN_DEVICE_OWNER: DEVICE_OWNER_OVIRT,
        },
        port_type=ovnconst.LSP_TYPE_LOCALNET,
        options={ovnconst.LSP_OPTION_NETWORK_NAME: LOCALNET_NAME},
        tag=LOCALNET_VLAN,
    )

    SUBNET_ID101 = UUID(int=101)
    SUBNET_ID102 = UUID(int=102)
    SUBNET_IDMTU = UUID(int=987)
    SUBNET_IDV6 = UUID(int=6)

    SUBNET_101 = OvnSubnetRow(
        SUBNET_ID101, network_id=str(NETWORK_ID10), cidr=SUBNET_CIDR
    )

    SUBNET_102 = OvnSubnetRow(SUBNET_ID102, cidr=SUBNET_CIDR)

    SUBNET_MTU = OvnSubnetRow(
        SUBNET_IDMTU, network_id=str(NETWORK_IDMTU), cidr=SUBNET_CIDR
    )

    SUBNET_IPV6 = OvnSubnetRow(
        SUBNET_IDV6, cidr=SUBNET_IPV6_CIDR, ip_version=6
    )

    NETWORK_10 = OvnNetworkRow(NETWORK_ID10, NETWORK_NAME10)
    NETWORK_11 = OvnNetworkRow(
        NETWORK_ID11, NETWORK_NAME11, ports=[PORT_1, PORT_2]
    )
    NETWORK_12 = OvnNetworkRow(NETWORK_ID12, NETWORK_NAME12)
    NETWORK_LOCALNET_12 = OvnNetworkRow(
        NETWORK_ID12, NETWORK_NAME12, ports=[PORT_3]
    )
    NETWORK_MTU = OvnNetworkRow(
        NETWORK_IDMTU,
        NETWORK_NAMEMTU,
        external_ids={NetworkMapper.REST_MTU: str(VALUE_NETWORK_MTU)},
    )

    NETWORK_UNICODE = OvnNetworkRow(NETWORK_ID_UNICODE, NETWORK_NAME_UNICODE)

    ROUTER_ID20 = UUID(int=20)
    ROUTER_NAME20 = 'router20'

    ROUTER_20 = OvnRouterRow(ROUTER_ID20, ROUTER_NAME20)

    SECURITY_GROUP_ID = UUID(int=666)
    SECURITY_GROUP_NAME = u'ultra-mega-security-弹射'
    SECURITY_GROUP_DESCRIPTION = 'as safe as it gets'
    SECURITY_GROUP = OvnSecurityGroupRow(
        SECURITY_GROUP_ID,
        str(SECURITY_GROUP_ID),
        external_ids={
            SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION: SECURITY_GROUP_DESCRIPTION,  # noqa: E501
            SecurityGroupMapper.OVN_SECURITY_GROUP_CREATE_TS: '',
            SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS: '',
            SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: '1',
            SecurityGroupMapper.OVN_SECURITY_GROUP_TENANT: tenant_id(),
            SecurityGroupMapper.OVN_SECURITY_GROUP_PROJECT: tenant_id(),
            SecurityGroupMapper.OVN_SECURITY_GROUP_NAME: SECURITY_GROUP_NAME,
        },
    )
    DEFAULT_SECURITY_GROUP = OvnSecurityGroupRow(
        SECURITY_GROUP_ID,
        'Default',
        external_ids={
            SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION: SECURITY_GROUP_DESCRIPTION,  # noqa: E501
            SecurityGroupMapper.OVN_SECURITY_GROUP_CREATE_TS: '',
            SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS: '',
            SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: '1',
            SecurityGroupMapper.OVN_SECURITY_GROUP_TENANT: tenant_id(),
            SecurityGroupMapper.OVN_SECURITY_GROUP_PROJECT: tenant_id(),
        },
    )

    SECURITY_GROUP_RULE_ID_01 = UUID(int=1)
    SECURITY_GROUP_RULE_ID_02 = UUID(int=2)
    SECURITY_GROUP_RULE_ID_03 = UUID(int=3)
    SECURITY_GROUP_RULE_01_EXT_IDS = {
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID: str(
            SECURITY_GROUP_ID
        ),
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_PROTOCOL: neutron_constants.PROTO_NAME_TCP,  # noqa: E501
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_ETHERTYPE: neutron_constants.IPV4_ETHERTYPE,  # noqa: E501
    }
    SECURITY_GROUP_RULE_02_EXT_IDS = {
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID: str(
            SECURITY_GROUP_ID
        ),
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_PROTOCOL: 'udp',
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_ETHERTYPE: 'IPv6',
    }
    SECURITY_GROUP_RULE_03_EXT_IDS = {
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID: str(
            SECURITY_GROUP_ID
        ),
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_PROTOCOL: 'udp',
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_ETHERTYPE: 'IPv4',
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_MIN_PORT: '161',
    }
    SECURITY_GROUP_RULE_01 = OvnSecurityGroupRuleRow(
        SECURITY_GROUP_RULE_ID_01,
        str(SECURITY_GROUP_RULE_ID_01),
        'from-lport',
        'ip4 && tcp',
        1001,
        str(SECURITY_GROUP_ID),
        'allow',
        SECURITY_GROUP_RULE_01_EXT_IDS,
    )

    SECURITY_GROUP_RULE_02 = OvnSecurityGroupRuleRow(
        SECURITY_GROUP_RULE_ID_02,
        str(SECURITY_GROUP_RULE_ID_02),
        'to-lport',
        'ip6 && udp',
        1000,
        str(SECURITY_GROUP_ID),
        'drop',
        SECURITY_GROUP_RULE_02_EXT_IDS,
    )
    SECURITY_GROUP_RULE_03 = OvnSecurityGroupRuleRow(
        SECURITY_GROUP_RULE_ID_03,
        str(SECURITY_GROUP_RULE_ID_03),
        'from-lport',
        'ip4 && udp && udp.dst == 161',
        1001,
        str(SECURITY_GROUP_ID),
        'allow',
        SECURITY_GROUP_RULE_03_EXT_IDS,
    )

    ports = [PORT_1, PORT_2, PORT_3]

    networks = [NETWORK_10, NETWORK_11, NETWORK_LOCALNET_12]

    subnets = [SUBNET_101, SUBNET_102]

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand', autospec=False
    )
    def test_get_networks(self, mock_ls_list, mock_connection):
        mock_ls_list.return_value.execute.return_value = TestOvnNorth.networks

        ovn_north = NeutronApi()
        result = ovn_north.list_networks()

        assert len(result) == 3
        assert_network_equal(
            result[0], Network(ls=TestOvnNorth.NETWORK_10, localnet_lsp=None)
        )
        assert_network_equal(
            result[1], Network(ls=TestOvnNorth.NETWORK_11, localnet_lsp=None)
        )
        localnet_network = TestOvnNorth.NETWORK_LOCALNET_12
        assert_network_equal(
            result[2],
            Network(
                ls=localnet_network, localnet_lsp=localnet_network.ports[0]
            ),
        )
        assert mock_ls_list.call_count == 1
        assert mock_ls_list.return_value.execute.call_count == 1

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand', autospec=False
    )
    def test_get_network(self, mock_ls_get, mock_connection):
        mock_ls_get.return_value.execute.return_value = TestOvnNorth.NETWORK_10
        ovn_north = NeutronApi()
        result = ovn_north.get_network(str(TestOvnNorth.NETWORK_ID10))

        network = Network(ls=TestOvnNorth.NETWORK_10, localnet_lsp=None)
        assert_network_equal(result, network)
        assert mock_ls_get.call_count == 1
        assert mock_ls_get.return_value.execute.call_count == 1
        assert mock_ls_get.mock_calls[0] == mock.call(
            ovn_north.idl, str(TestOvnNorth.NETWORK_ID10)
        )

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_10,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsAddCommand', autospec=False
    )
    def test_add_network(self, mock_add_command, mock_connection):
        self._test_add_network(mock_add_command, TestOvnNorth.NETWORK_10)

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_UNICODE,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsAddCommand', autospec=False
    )
    def test_add_network_with_unicode_name(
        self, mock_add_command, mock_connection
    ):
        self._test_add_network(mock_add_command, TestOvnNorth.NETWORK_UNICODE)

    def _test_add_network(self, mock_add_command, network_row):
        mock_add_command.return_value.execute.return_value = network_row
        ovn_north = NeutronApi()
        rest_data = NetworkApiInputMaker(network_row.name).get()
        result = ovn_north.add_network(rest_data)

        network = Network(ls=network_row, localnet_lsp=None)
        assert_network_equal(result, network)
        assert mock_add_command.call_count == 1
        assert mock_add_command.mock_calls[0] == mock.call(
            ovn_north.idl,
            mock.ANY,
            False,
            external_ids={
                NetworkMapper.OVN_NETWORK_NAME: (network_row.name),
                NetworkMapper.OVN_NETWORK_PORT_SECURITY: 'False',
            },
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch('ovsdbapp.schema.ovn_northbound.commands.LsAddCommand')
    @mock.patch('ovsdbapp.schema.ovn_northbound.commands.LsGetCommand')
    @mock.patch('ovsdbapp.schema.ovn_northbound.commands.LspAddCommand')
    @mock.patch('ovsdbapp.backend.ovs_idl.command.DbSetCommand')
    def test_add_localnet_network(
        self,
        mock_db_set_command,
        mock_lsp_add_command,
        mock_ls_get_command,
        mock_ls_add_command,
        mock_connection,
    ):
        mock_ls_get_command.return_value.execute.return_value = (
            TestOvnNorth.NETWORK_LOCALNET_12
        )
        mock_ls_add_command.return_value.execute.return_value = (
            TestOvnNorth.NETWORK_LOCALNET_12
        )
        ovn_north = NeutronApi()
        rest_data = NetworkApiInputMaker(
            TestOvnNorth.NETWORK_NAME12,
            provider_type=NetworkMapper.NETWORK_TYPE_VLAN,
            provider_physical_network=TestOvnNorth.LOCALNET_NAME,
            vlan_tag=TestOvnNorth.LOCALNET_VLAN,
        ).get()
        result = ovn_north.add_network(rest_data)

        localnet_network = TestOvnNorth.NETWORK_LOCALNET_12
        assert_network_equal(
            result,
            Network(
                ls=localnet_network, localnet_lsp=localnet_network.ports[0]
            ),
        )
        assert mock_ls_add_command.call_count == 1
        assert mock_ls_add_command.mock_calls[0] == mock.call(
            ovn_north.idl,
            mock.ANY,
            False,
            external_ids={
                NetworkMapper.OVN_NETWORK_NAME: (TestOvnNorth.NETWORK_NAME12),
                NetworkMapper.OVN_NETWORK_PORT_SECURITY: 'False',
            },
        )
        assert mock_lsp_add_command.call_count == 1
        assert mock_lsp_add_command.mock_calls[0] == mock.call(
            ovn_north.idl,
            mock.ANY,
            mock.ANY,
            None,
            None,
            False,
            external_ids={
                'ovirt_nic_name': ovnconst.LOCALNET_SWITCH_PORT_NAME
            },
        )
        assert mock_db_set_command.call_count == 1
        assert mock_ls_get_command.call_count == 1

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_MTU,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsAddCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_MTU,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsAddCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_MTU,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_MTU,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsSetOptionsCommand',
        autospec=False,
    )
    def test_add_network_with_mtu(
        self, mock_setoptions_command, mock_dbset_command, mock_connection
    ):
        ovn_north = NeutronApi()
        network_rest_data = NetworkApiInputMaker(
            TestOvnNorth.NETWORK_NAMEMTU, mtu=TestOvnNorth.VALUE_NETWORK_MTU
        ).get()
        network_creation_result = ovn_north.add_network(network_rest_data)
        assert_network_equal(
            network_creation_result,
            Network(ls=TestOvnNorth.NETWORK_MTU, localnet_lsp=None),
        )

        # create a subnet associated with the above network
        subnet_rest_data = SubnetApiInputMaker(
            TestOvnNorth.SUBNET_102.external_ids.get(SubnetMapper.OVN_NAME),
            cidr=TestOvnNorth.SUBNET_CIDR,
            network_id=str(TestOvnNorth.NETWORK_IDMTU),
            dns_nameservers=['1.1.1.1'],
            gateway_ip='1.1.1.0',
            ip_version=4,
        ).get()

        expected_options_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.SUBNET_IDMTU,
            dns_server='1.1.1.1',
            lease_time=dhcp_lease_time(),
            router='1.1.1.0',
            server_id='1.1.1.0',
            server_mac=dhcp_server_mac(),
            mtu=str(TestOvnNorth.VALUE_NETWORK_MTU),
        )

        subnet_creation_result = ovn_north.add_subnet(subnet_rest_data)
        assert mock_setoptions_command.call_count == 1
        assert mock_setoptions_command.mock_calls[0] == expected_options_call
        assert mock_dbset_command.call_count == 1
        assert_subnet_equal(subnet_creation_result, TestOvnNorth.SUBNET_MTU)

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_MTU,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsAddCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_MTU,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsAddCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_MTU,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_MTU,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsSetOptionsCommand',
        autospec=False,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand'
    )
    def test_update_networks_mtu(
        self,
        mock_dhcp_list_command,
        mock_setoptions_command,
        mock_dbset_command,
        mock_connection,
    ):
        mock_dhcp_list_command.return_value.execute.return_value = []

        ovn_north = NeutronApi()
        network_rest_data = NetworkApiInputMaker(
            TestOvnNorth.NETWORK_NAMEMTU, mtu=TestOvnNorth.VALUE_NETWORK_MTU
        ).get()
        ovn_north.add_network(network_rest_data)

        # create a subnet associated with the above network
        subnet_rest_data = SubnetApiInputMaker(
            TestOvnNorth.SUBNET_102.external_ids.get(SubnetMapper.OVN_NAME),
            cidr=TestOvnNorth.SUBNET_CIDR,
            network_id=str(TestOvnNorth.NETWORK_IDMTU),
            dns_nameservers=['1.1.1.1'],
            gateway_ip='1.1.1.0',
            ip_version=4,
        ).get()

        ovn_north.add_subnet(subnet_rest_data)
        new_mtu = 14999
        mtu_update = NetworkApiInputMaker(
            TestOvnNorth.NETWORK_NAMEMTU, mtu=new_mtu
        ).get()

        assert mock_setoptions_command.call_count == 1
        mock_dhcp_list_command.return_value.execute.return_value = [
            TestOvnNorth.SUBNET_MTU
        ]

        ovn_north.update_network(mtu_update, TestOvnNorth.NETWORK_IDMTU)
        expected_external_ids_update = mock.call(
            ovn_north.idl,
            ovnconst.TABLE_LS,
            TestOvnNorth.NETWORK_IDMTU,
            (
                ovnconst.ROW_LS_EXTERNAL_IDS,
                {
                    NetworkMapper.OVN_NETWORK_NAME: (
                        TestOvnNorth.NETWORK_NAMEMTU
                    ),
                    NetworkMapper.REST_MTU: str(new_mtu),
                },
            ),
        )
        expected_network_mtu_update = mock.call(
            ovn_north.idl,
            ovnconst.TABLE_DHCP_Options,
            TestOvnNorth.SUBNET_IDMTU,
            (
                ovnconst.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_MTU: str(new_mtu)},
            ),
        )
        assert expected_external_ids_update in mock_dbset_command.mock_calls
        assert expected_network_mtu_update in mock_dbset_command.mock_calls

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: OvnNetworkRow(
            TestOvnNorth.NETWORK_ID10, TestOvnNorth.NETWORK_NAME10
        ),
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    def test_update_network(self, mock_set_command, mock_connection):
        ovn_north = NeutronApi()
        rest_data = NetworkApiInputMaker(TestOvnNorth.NETWORK_NAME10).get()
        result = ovn_north.update_network(rest_data, TestOvnNorth.NETWORK_ID10)

        network = Network(ls=TestOvnNorth.NETWORK_10, localnet_lsp=None)
        assert_network_equal(result, network)
        assert mock_set_command.call_count == 1
        assert mock_set_command.mock_calls[0] == mock.call(
            ovn_north.idl,
            ovnconst.TABLE_LS,
            TestOvnNorth.NETWORK_ID10,
            (
                ovnconst.ROW_LS_EXTERNAL_IDS,
                {
                    NetworkMapper.OVN_NETWORK_NAME: (
                        TestOvnNorth.NETWORK_NAME10
                    )
                },
            ),
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch('ovsdbapp.schema.ovn_northbound.commands.LsGetCommand')
    @mock.patch('ovsdbapp.backend.ovs_idl.command.DbSetCommand')
    def test_update_localnet_network(
        self, mock_set_command, mock_ls_get_command, mock_connection
    ):
        mock_ls_get_command.return_value.execute.return_value = (
            TestOvnNorth.NETWORK_LOCALNET_12
        )
        ovn_north = NeutronApi()
        rest_data = NetworkApiInputMaker(
            TestOvnNorth.NETWORK_NAME12,
            provider_type=NetworkMapper.NETWORK_TYPE_VLAN,
            provider_physical_network=TestOvnNorth.LOCALNET_NAME,
            vlan_tag=TestOvnNorth.LOCALNET_VLAN,
        ).get()
        result = ovn_north.update_network(rest_data, TestOvnNorth.NETWORK_ID12)

        localnet_network = TestOvnNorth.NETWORK_LOCALNET_12
        assert_network_equal(
            result,
            Network(
                ls=localnet_network, localnet_lsp=localnet_network.ports[0]
            ),
        )
        assert mock_set_command.call_count == 2
        assert mock_set_command.mock_calls[0] == mock.call(
            ovn_north.idl,
            ovnconst.TABLE_LS,
            TestOvnNorth.NETWORK_ID12,
            (
                ovnconst.ROW_LS_EXTERNAL_IDS,
                {
                    NetworkMapper.OVN_NETWORK_NAME: (
                        TestOvnNorth.NETWORK_NAME12
                    )
                },
            ),
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_10,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsDelCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [],
    )
    def test_delete_network(self, mock_del_command, mock_connection):
        ovn_north = NeutronApi()
        ovn_north.delete_network(TestOvnNorth.NETWORK_ID10)
        assert mock_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl, TestOvnNorth.NETWORK_ID10, False
        )
        assert mock_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand.execute',
        lambda cmd, check_error: TestOvnNorth.networks,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.PORT_1,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [TestOvnNorth.SUBNET_101],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_10,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbClearCommand.execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspAddCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch('neutron.neutron_api.ovs_version_29', lambda: True)
    def test_add_port(self, mock_db_set, mock_add_command, mock_connection):
        mock_add_command.return_value.execute.return_value = (
            TestOvnNorth.PORT_1
        )
        ovn_north = NeutronApi()
        rest_data = PortApiInputMaker(
            TestOvnNorth.PORT_NAME01,
            str(TestOvnNorth.NETWORK_ID10),
            device_id=TestOvnNorth.DEVICE_ID,
            device_owner=TestOvnNorth.DEVICE_OWNER_OVIRT,
            admin_state_up=True,
            mac_address=TestOvnNorth.MAC_ADDRESS,
            fixed_ips=TestOvnNorth.PORT_NAME01_FIXED_IPS,
            binding_host_id=TestOvnNorth.PORT_BINDING_ID,
        ).get()
        result = ovn_north.add_port(rest_data)

        # ID11 because this network has the port in TestOvnNorth.networks
        logical_switch = OvnNetworkRow(
            TestOvnNorth.NETWORK_ID11,
            name=TestOvnNorth.NETWORK_NAME11,
            ports=[TestOvnNorth.PORT_1],
        )
        port = NetworkPort(
            lsp=TestOvnNorth.PORT_1,
            ls=logical_switch,
            dhcp_options=None,
            lrp=None,
        )
        assert_port_equal(result, port)

        assert mock_add_command.call_count == 1
        mock_add_command.assert_called_with(
            ovn_north.idl,
            str(TestOvnNorth.NETWORK_ID10),
            mock.ANY,
            None,
            None,
            False,
            external_ids={
                'ovirt_nic_name': TestOvnNorth.PORT_NAME01,
            },
        )

        assert mock_db_set.call_count == 4

        assert (
            mock.call(
                ovn_north.idl,
                ovnconst.TABLE_LSP,
                mock.ANY,
                (
                    ovnconst.ROW_LSP_EXTERNAL_IDS,
                    {PortMapper.OVN_DEVICE_ID: TestOvnNorth.DEVICE_ID},
                ),
                (
                    ovnconst.ROW_LSP_EXTERNAL_IDS,
                    {PortMapper.OVN_NIC_NAME: TestOvnNorth.PORT_NAME01},
                ),
                (
                    ovnconst.ROW_LSP_EXTERNAL_IDS,
                    {
                        PortMapper.OVN_DEVICE_OWNER: TestOvnNorth.DEVICE_OWNER_OVIRT  # noqa: E501
                    },
                ),
                (ovnconst.ROW_LSP_ENABLED, True),
                (
                    ovnconst.ROW_LSP_OPTIONS,
                    {
                        PortMapper.OVN_REQUESTED_CHASSIS: TestOvnNorth.PORT_BINDING_ID  # noqa: E501
                    },
                ),
            )
            in mock_db_set.mock_calls
        )

        assert (
            mock.call(
                ovn_north.idl,
                ovnconst.TABLE_LSP,
                mock.ANY,
                (ovnconst.ROW_LSP_DHCPV4_OPTIONS, TestOvnNorth.SUBNET_ID101),
                (
                    ovnconst.ROW_LSP_ADDRESSES,
                    [
                        '{mac_address} {ip_address}'.format(
                            mac_address=TestOvnNorth.MAC_ADDRESS,
                            ip_address=TestOvnNorth.PORT_NAME01_FIXED_IP,
                        )
                    ],
                ),
            )
            in mock_db_set.mock_calls
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbClearCommand.execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspGetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand',
        autospec=False,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspAddCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch('neutron.neutron_api.ovs_version_29', lambda: True)
    def test_add_port_subnet(
        self,
        mock_db_set,
        mock_add_command,
        mock_get_dhcp_options,
        mock_ls_get,
        mock_lsp_get,
        mock_ls_list,
        mock_connection,
    ):
        networkd_uuid = UUID(int=505)
        subnet_cidr = '192.168.14.0/24'
        subnet_uuid = UUID(int=606)
        port_name = 'mega-port'
        port_uuid = UUID(int=707)

        subnet = OvnSubnetRow(
            subnet_uuid, network_id=str(networkd_uuid), cidr=subnet_cidr
        )
        port_fixed_ips = [{PortMapper.REST_PORT_SUBNET_ID: str(subnet_uuid)}]
        ovn_port = OvnPortRow(
            port_uuid,
            addresses=[TestOvnNorth.MAC_ADDRESS, '192.168.14.2'],
            external_ids={
                PortMapper.OVN_NIC_NAME: port_name,
                PortMapper.OVN_DEVICE_ID: str(port_uuid),
                PortMapper.OVN_DEVICE_OWNER: TestOvnNorth.DEVICE_OWNER_OVIRT,
            },
        )
        port_network = OvnNetworkRow(networkd_uuid, 'net4', ports=[ovn_port])
        mock_add_command.return_value.execute.return_value = ovn_port
        mock_get_dhcp_options.return_value.execute.return_value = [subnet]
        mock_ls_get.return_value.execute.return_value = port_network
        mock_lsp_get.return_value.execute.return_value = ovn_port
        mock_ls_list.return_value.execute.return_value = [port_network]

        ovn_north = NeutronApi()
        rest_data = PortApiInputMaker(
            port_name,
            str(networkd_uuid),
            device_id=TestOvnNorth.DEVICE_ID,
            device_owner=TestOvnNorth.DEVICE_OWNER_OVIRT,
            admin_state_up=True,
            mac_address=TestOvnNorth.MAC_ADDRESS,
            fixed_ips=port_fixed_ips,
            binding_host_id=TestOvnNorth.PORT_BINDING_ID,
        ).get()
        result = ovn_north.add_port(rest_data)

        port = NetworkPort(
            lsp=ovn_port, ls=port_network, dhcp_options=subnet, lrp=None
        )
        assert_port_equal(result, port)

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand.execute',
        lambda cmd, check_error: TestOvnNorth.networks,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspListCommand.execute',
        lambda cmd, check_error: TestOvnNorth.ports,
    )
    def test_list_ports(self, mock_connection):
        ovn_north = NeutronApi()
        ports = ovn_north.list_ports()
        assert len(ports) == 3
        logical_switch = OvnNetworkRow(
            TestOvnNorth.NETWORK_ID11,
            name=TestOvnNorth.NETWORK_NAME11,
            ports=[TestOvnNorth.PORT_1, TestOvnNorth.PORT_2],
        )
        first_port = NetworkPort(
            lsp=TestOvnNorth.PORT_1,
            ls=logical_switch,
            dhcp_options=None,
            lrp=None,
        )
        second_port = NetworkPort(
            lsp=TestOvnNorth.PORT_2,
            ls=logical_switch,
            dhcp_options=None,
            lrp=None,
        )

        third_port = NetworkPort(
            lsp=TestOvnNorth.PORT_3,
            ls=OvnNetworkRow(TestOvnNorth.NETWORK_ID12),
            dhcp_options=None,
            lrp=None,
        )

        assert_port_equal(ports[0], first_port)
        assert_port_equal(ports[1], second_port)
        assert_port_equal(ports[2], third_port)

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: None,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspGetCommand.' 'execute',
        lambda cmd, check_error: OvnPortRow(
            TestOvnNorth.PORT_ID01,
            external_ids={
                PortMapper.OVN_DEVICE_OWNER: TestOvnNorth.DEVICE_OWNER_OVIRT
            },
        ),
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspDelCommand', autospec=False
    )
    def test_delete_port(self, mock_del_command, mock_connection):
        ovn_north = NeutronApi()
        ovn_north.delete_port(TestOvnNorth.PORT_ID01)
        assert mock_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl, TestOvnNorth.PORT_ID01, None, False
        )
        assert mock_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspGetCommand.' 'execute',
        lambda cmd, check_error: OvnPortRow(
            TestOvnNorth.PORT_ID01,
            external_ids={
                PortMapper.OVN_DEVICE_OWNER: PortMapper.DEVICE_OWNER_ROUTER
            },
        ),
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspDelCommand', autospec=False
    )
    def test_delete_router_port(self, mock_del_command, mock_connection):
        ovn_north = NeutronApi()
        with pytest.raises(ConflictError):
            ovn_north.delete_port(TestOvnNorth.PORT_ID01)
        assert mock_del_command.call_count == 0

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.subnets,
    )
    def test_list_subnets(self, mock_connection):
        ovn_north = NeutronApi()
        result = ovn_north.list_subnets()
        assert len(result) == 2
        assert result[0]['id'] == str(TestOvnNorth.SUBNET_ID101)
        assert result[0]['network_id'] == str(TestOvnNorth.NETWORK_ID10)
        assert result[0]['tenant_id'] == tenant_id()

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_101,
    )
    def test_get_subnet(self, mock_connection):
        ovn_north = NeutronApi()
        result = ovn_north.get_subnet(TestOvnNorth.SUBNET_ID101)
        assert result['id'] == str(TestOvnNorth.SUBNET_ID101)
        assert result['network_id'] == str(TestOvnNorth.NETWORK_ID10)
        gateway_ip = TestOvnNorth.SUBNET_101.options['router']
        assert result['gateway_ip'] == gateway_ip

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsDelCommand',
        autospec=False,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_101,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_10,
    )
    def test_delete_subnet(self, mock_del_command, mock_connection):
        ovn_north = NeutronApi()
        ovn_north.delete_subnet(TestOvnNorth.SUBNET_ID101)
        assert mock_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.SUBNET_ID101,
        )
        assert mock_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_10,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_102,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsAddCommand',
        autospec=False,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsSetOptionsCommand',
        autospec=False,
    )
    def test_add_subnet(
        self,
        mock_setoptions_command,
        mock_add_command,
        mock_dbset_command,
        mock_connection,
    ):
        add_execute = mock_add_command.return_value.execute
        add_execute.return_value = TestOvnNorth.SUBNET_102
        ovn_north = NeutronApi()
        rest_data = SubnetApiInputMaker(
            TestOvnNorth.SUBNET_102.external_ids.get(SubnetMapper.OVN_NAME),
            cidr=TestOvnNorth.SUBNET_CIDR,
            ip_version=4,
            network_id=str(TestOvnNorth.NETWORK_ID10),
            dns_nameservers=['1.1.1.1'],
            gateway_ip='1.1.1.0',
        ).get()
        result = ovn_north.add_subnet(rest_data)
        assert_subnet_equal(result, TestOvnNorth.SUBNET_102)
        assert mock_dbset_command.call_count == 1
        assert mock_add_command.call_count == 1
        assert mock_setoptions_command.call_count == 1

        expected_dbset_call = mock.call(
            ovn_north.idl,
            ovnconst.TABLE_LS,
            str(TestOvnNorth.NETWORK_ID10),
            (
                ovnconst.ROW_LS_OTHER_CONFIG,
                {NetworkMapper.OVN_SUBNET: TestOvnNorth.SUBNET_CIDR},
            ),
        )
        assert mock_dbset_command.mock_calls[0] == expected_dbset_call

        expected_add_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.SUBNET_CIDR,
            ovirt_name=TestOvnNorth.SUBNET_102.external_ids.get(
                SubnetMapper.OVN_NAME
            ),
            ovirt_network_id=str(TestOvnNorth.NETWORK_ID10),
            ip_version='4',
        )
        assert mock_add_command.mock_calls[0] == expected_add_call

        expected_options_call = mock.call(
            ovn_north.idl,
            TestOvnNorth.SUBNET_ID102,
            dns_server='1.1.1.1',
            lease_time=dhcp_lease_time(),
            router='1.1.1.0',
            server_id='1.1.1.0',
            server_mac=dhcp_server_mac(),
            mtu=dhcp_mtu(),
        )
        assert mock_setoptions_command.mock_calls[0] == expected_options_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_10,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_102,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsAddCommand',
        autospec=False,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsSetOptionsCommand',
        autospec=False,
    )
    def test_add_subnet_no_dns(
        self,
        mock_setoptions_command,
        mock_add_command,
        mock_dbset_command,
        mock_connection,
    ):
        add_execute = mock_add_command.return_value.execute
        add_execute.return_value = TestOvnNorth.SUBNET_102
        ovn_north = NeutronApi()
        rest_data = SubnetApiInputMaker(
            'subnet_name',
            cidr=TestOvnNorth.SUBNET_CIDR,
            network_id=str(TestOvnNorth.NETWORK_ID10),
            dns_nameservers=[],
            gateway_ip='1.1.1.0',
            ip_version=4,
        ).get()
        result = ovn_north.add_subnet(rest_data)
        assert_subnet_equal(result, TestOvnNorth.SUBNET_102)
        assert mock_dbset_command.call_count == 1
        assert mock_add_command.call_count == 1
        assert mock_setoptions_command.call_count == 1

    """
    TODO: This test causes Jenkins to get stuck. Commenting out until the
    issue is solved.

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand.execute',
        lambda cmd, check_error: TestOvnNorth.networks
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.PORT_1
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: []
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
                {SubnetMapper.OVN_DHCP_LEASE_TIME: dhcp_lease_time()}
            ),
            (
                OvnNorth.ROW_DHCP_OPTIONS,
                {SubnetMapper.OVN_DHCP_SERVER_MAC: dhcp_server_mac()}
            )
        )
    """

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: OvnNetworkRow(
            TestOvnNorth.NETWORK_ID10, TestOvnNorth.NETWORK_NAME10
        ),
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.subnets,
    )
    def test_subnet_add_duplicate_network(self, mock_connection):
        ovn_north = NeutronApi()
        rest_data = SubnetApiInputMaker(
            'subnet_name',
            cidr=TestOvnNorth.SUBNET_CIDR,
            ip_version=4,
            network_id=str(TestOvnNorth.NETWORK_ID10),
            gateway_ip='1.1.1.0',
        ).get()
        with pytest.raises(SubnetConfigError):
            ovn_north.add_subnet(rest_data)

    def test_subnet_dhcp_enabled_false(self, mock_connection):
        ovn_north = NeutronApi()
        rest_data = SubnetApiInputMaker(
            'subnet_name',
            cidr=TestOvnNorth.SUBNET_CIDR,
            network_id='',
            dns_nameservers=['1.1.1.1'],
            gateway_ip='1.1.1.0',
            enable_dhcp=False,
            ip_version=4,
        ).get()
        with pytest.raises(UnsupportedDataValueError):
            ovn_north.add_subnet(rest_data)

    @mock.patch('ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute')
    def test_subnet_add_invalid_network(
        self, mock_ls_get_cmd, mock_connection
    ):
        mock_ls_get_cmd.side_effect = RowNotFound()
        ovn_north = NeutronApi()
        rest_data = SubnetApiInputMaker(
            'subnet_name',
            cidr=TestOvnNorth.SUBNET_CIDR,
            network_id=7,
            dns_nameservers=['1.1.1.1'],
            gateway_ip='1.1.1.0',
            ip_version=4,
        ).get()
        with pytest.raises(SubnetConfigError):
            ovn_north.add_subnet(rest_data)

    def test_port_admin_state_up_none_enabled_none(self, mock_connection):
        self._port_admin_state(mock_connection, None, None, False)

    def test_port_admin_state_up_true_enabled_none(self, mock_connection):
        self._port_admin_state(mock_connection, [True], None, True)

    def test_port_admin_state_up_false_enabled_none(self, mock_connection):
        self._port_admin_state(mock_connection, [False], None, False)

    def test_port_admin_state_up_none_enabled_true(self, mock_connection):
        self._port_admin_state(mock_connection, None, [True], False)

    def test_port_admin_state_up_true_enabled_true(self, mock_connection):
        self._port_admin_state(mock_connection, [True], [True], True)

    def test_port_admin_state_up_false_enabled_true(self, mock_connection):
        self._port_admin_state(mock_connection, [False], [True], False)

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand',
    )
    @mock.patch('ovsdbapp.schema.ovn_northbound.commands.LspGetCommand')
    def _port_admin_state(
        self,
        mock_connection,
        is_up,
        is_enabled,
        result,
        mock_lsp_get,
        mock_ls_list,
    ):
        port_row = OvnPortRow(
            TestOvnNorth.PORT_ID01,
            external_ids={
                PortMapper.OVN_NIC_NAME: TestOvnNorth.PORT_NAME01,
                PortMapper.OVN_DEVICE_ID: str(TestOvnNorth.PORT_ID01),
                PortMapper.OVN_DEVICE_OWNER: TestOvnNorth.DEVICE_OWNER_OVIRT,
            },
        )
        port_row.up = is_up
        port_row.enabled = is_enabled

        mock_lsp_get.return_value.execute.return_value = port_row
        mock_ls_list.return_value.execute.return_value = [
            OvnNetworkRow(TestOvnNorth.NETWORK_ID11, ports=[port_row])
        ]

        ovn_north = NeutronApi()
        port = ovn_north.get_port(TestOvnNorth.PORT_ID01)
        assert port[PortMapper.REST_PORT_ADMIN_STATE_UP] == result

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
    )
    def test_get_router(self, mock_lookup, mock_connection):
        mock_lookup.return_value = TestOvnNorth.ROUTER_20
        ovn_north = NeutronApi()
        result = ovn_north.get_router(str(TestOvnNorth.ROUTER_ID20))

        assert result['id'] == str(TestOvnNorth.ROUTER_ID20)
        assert result['name'] == str(TestOvnNorth.ROUTER_NAME20)

        assert mock_lookup.call_args == mock.call(
            ovnconst.TABLE_LR, str(TestOvnNorth.ROUTER_ID20)
        )

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LrDelCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
    )
    def test_delete_router(
        self, mock_lookup, mock_del_command, mock_connection
    ):
        mock_lookup.return_value = TestOvnNorth.ROUTER_20
        ovn_north = NeutronApi()

        ovn_north.delete_router(str(TestOvnNorth.ROUTER_ID20))

        assert mock_lookup.call_args == mock.call(
            ovnconst.TABLE_LR, str(TestOvnNorth.ROUTER_ID20)
        )

        assert mock_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl, str(TestOvnNorth.ROUTER_ID20), False
        )
        assert mock_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LrDelCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
    )
    def test_delete_router_fail(
        self, mock_lookup, mock_del_command, mock_connection
    ):
        mock_lookup.return_value = OvnRouterRow(
            TestOvnNorth.ROUTER_ID20, ports=[OvnRouterPort()]
        )
        ovn_north = NeutronApi()
        with pytest.raises(ConflictError):
            ovn_north.delete_router(str(TestOvnNorth.ROUTER_ID20))

        assert mock_lookup.call_args == mock.call(
            ovnconst.TABLE_LR, str(TestOvnNorth.ROUTER_ID20)
        )
        assert mock_del_command.call_count == 0

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda command, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    def test_get_security_group(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        result = ovn_north.get_security_group(
            str(TestOvnNorth.SECURITY_GROUP_ID)
        )
        assert_security_group_equal(
            result,
            SecurityGroup(
                sec_group=TestOvnNorth.SECURITY_GROUP, sec_group_rules=[]
            ),
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda idl, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: TestOvnNorth.SECURITY_GROUP,
        [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAclAddCommand.execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.add',
        lambda cmd, check_error: TestOvnNorth.SECURITY_GROUP,
    )
    def test_add_security_group(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        rest_data = SecurityGroupApiInputMaker(
            TestOvnNorth.SECURITY_GROUP_NAME,
            tenant_id(),
            tenant_id(),
            description=TestOvnNorth.SECURITY_GROUP_DESCRIPTION,
        ).get()

        result = ovn_north.add_security_group(rest_data)
        security_group = SecurityGroup(
            sec_group=TestOvnNorth.SECURITY_GROUP, sec_group_rules=[]
        )
        assert_security_group_equal(result, security_group)

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda idl, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: TestOvnNorth.SECURITY_GROUP,
        [],
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbCreateCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAclAddCommand.execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAddCommand.execute',
        lambda cmd, check_error: TestOvnNorth.SECURITY_GROUP,
    )
    def test_add_security_group_optional_data(
        self, db_create_mock, mock_connection
    ):
        ovn_north = NeutronApi(sec_group_support=True)
        rest_data = SecurityGroupApiInputMaker(
            TestOvnNorth.SECURITY_GROUP_NAME
        ).get()

        result = ovn_north.add_security_group(rest_data)
        security_group = SecurityGroup(
            sec_group=TestOvnNorth.SECURITY_GROUP, sec_group_rules=[]
        )
        assert_security_group_equal(result, security_group)

    def test_add_security_group_validator(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        rest_data = SecurityGroupApiInputMaker(
            TestOvnNorth.SECURITY_GROUP_NAME,
            tenant_id(),
            tenant_id(),
            description=TestOvnNorth.SECURITY_GROUP_DESCRIPTION,
        ).get()

        with pytest.raises(InvalidRestData) as invalid_data:
            rest_data.update({'peanut-butter': 32})
            ovn_north.add_security_group(rest_data)
        assert 'Invalid data found: peanut-butter' == str(invalid_data.value)

    def test_add_security_group_validator_data_missing(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        rest_data = SecurityGroupApiInputMaker(
            TestOvnNorth.SECURITY_GROUP_NAME,
            tenant_id(),
            tenant_id(),
            description=TestOvnNorth.SECURITY_GROUP_DESCRIPTION,
        ).get()

        with pytest.raises(MandatoryDataMissing) as invalid_data:
            rest_data.pop('name')
            ovn_north.add_security_group(rest_data)
        assert 'Mandatory data name is missing' == str(invalid_data.value)

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgDelCommand', autospec=False
    )
    def test_delete_security_group(self, mock_pg_del_command, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)

        ovn_north.delete_security_group(str(TestOvnNorth.SECURITY_GROUP_ID))
        assert mock_pg_del_command.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl, str(TestOvnNorth.SECURITY_GROUP_ID), if_exists=False
        )
        assert mock_pg_del_command.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda idl, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: TestOvnNorth.SECURITY_GROUP,
        [],
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbCreateCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAclAddCommand.execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda command, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda self, table, the_id: TestOvnNorth.SECURITY_GROUP,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAddCommand.execute',
        lambda cmd, check_error: TestOvnNorth.SECURITY_GROUP,
    )
    def test_update_security_group(
        self, mock_db_update, db_create_mock, mock_connection
    ):
        ovn_north = NeutronApi(sec_group_support=True)
        rest_data = SecurityGroupApiInputMaker(
            TestOvnNorth.SECURITY_GROUP_NAME,
            tenant_id(),
            tenant_id(),
            description=TestOvnNorth.SECURITY_GROUP_DESCRIPTION,
        ).get()

        ovn_north.add_security_group(rest_data)

        # update the security group with other stuff
        new_name = 'new_way_cuter_name'
        new_description = 'this thing is waaaay better now'

        ovn_north.update_security_group(
            SecurityGroupApiInputMaker(
                new_name, description=new_description
            ).get(),
            str(TestOvnNorth.SECURITY_GROUP_ID),
        )

        assert mock_db_update.call_count == 1

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: TestOvnNorth.SECURITY_GROUP,
        [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda self, table, the_id: TestOvnNorth.DEFAULT_SECURITY_GROUP,
    )
    def test_update_default_sec_group(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)

        # update the default security group
        new_name = 'new_way_cuter_name'
        new_description = 'this thing is waaaay better now'

        with pytest.raises(BadRequestError):
            ovn_north.update_security_group(
                SecurityGroupApiInputMaker(
                    new_name, description=new_description
                ).get(),
                str(TestOvnNorth.SECURITY_GROUP_ID),
            )

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: (
            TestOvnNorth.SECURITY_GROUP
            if table == 'Port_Group'
            else TestOvnNorth.SECURITY_GROUP_RULE_01
        ),
    )
    def test_get_security_group_rule(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        result = ovn_north.get_security_group_rule(
            TestOvnNorth.SECURITY_GROUP_RULE_ID_01
        )
        assert_security_group_rule_equal(
            result, TestOvnNorth.SECURITY_GROUP_RULE_01
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda command, check_error: [TestOvnNorth.SECURITY_GROUP_RULE_01],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    def test_get_security_group_with_rules(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        result = ovn_north.get_security_group(
            str(TestOvnNorth.SECURITY_GROUP_ID)
        )
        assert_security_group_equal(
            result,
            SecurityGroup(
                sec_group=TestOvnNorth.SECURITY_GROUP,
                sec_group_rules=[
                    SecurityGroupRule(
                        TestOvnNorth.SECURITY_GROUP_RULE_01,
                        TestOvnNorth.SECURITY_GROUP,
                    )
                ],
            ),
        )

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAclAddCommand.execute',
        lambda cmd, check_error: TestOvnNorth.SECURITY_GROUP_RULE_01,
    )
    def test_add_security_group_rules(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        rest_data = SecurityGroupRuleApiInputMaker(
            'ingress',
            str(TestOvnNorth.SECURITY_GROUP_ID),
            ether_type='IPv4',
            protocol='tcp',
        ).get()

        result = ovn_north.add_security_group_rule(rest_data)
        assert_security_group_rule_equal(
            result, TestOvnNorth.SECURITY_GROUP_RULE_01
        )

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup'
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAclDelCommand',
        autospec=False,
    )
    def test_delete_security_group_rule(
        self, mock_delete_rule, mock_ovn_getter, mock_connection
    ):
        mock_ovn_getter.side_effect = [
            TestOvnNorth.SECURITY_GROUP_RULE_01,
            TestOvnNorth.SECURITY_GROUP,
        ]
        ovn_north = NeutronApi(sec_group_support=True)
        ovn_north.delete_security_group_rule(
            TestOvnNorth.SECURITY_GROUP_RULE_ID_01
        )
        assert mock_delete_rule.call_count == 1
        expected_del_call = mock.call(
            ovn_north.idl,
            str(TestOvnNorth.SECURITY_GROUP_ID),
            'from-lport',
            1001,
            'ip4 && tcp',
        )
        assert mock_delete_rule.mock_calls[0] == expected_del_call

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda command, check_error: [
            TestOvnNorth.SECURITY_GROUP_RULE_01,
            TestOvnNorth.SECURITY_GROUP_RULE_02,
        ],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    def test_filter_out_drop_security_rules(self, mock_connection):
        ovn_north = NeutronApi(sec_group_support=True)
        result = ovn_north.get_security_group(
            str(TestOvnNorth.SECURITY_GROUP_ID)
        )
        assert_security_group_equal(
            result,
            SecurityGroup(
                sec_group=TestOvnNorth.SECURITY_GROUP,
                sec_group_rules=[
                    SecurityGroupRule(
                        TestOvnNorth.SECURITY_GROUP_RULE_01,
                        TestOvnNorth.SECURITY_GROUP,
                    )
                ],
            ),
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda idl, check_error: [
            TestOvnNorth.SECURITY_GROUP_RULE_01,
            TestOvnNorth.SECURITY_GROUP_RULE_03,
        ],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup',
        lambda idl, table, uuid: TestOvnNorth.SECURITY_GROUP,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda x: TestOvnNorth.SECURITY_GROUP,
        [SECURITY_GROUP_RULE_01, SECURITY_GROUP_RULE_03],
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbCreateCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.PgAclAddCommand.execute'
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.add',
        lambda cmd, check_error: TestOvnNorth.SECURITY_GROUP,
    )
    def test_add_security_group_automatic_rule_install(
        self, mock_ovn_getter, db_create_mock, mock_connection
    ):
        ovn_north = NeutronApi(sec_group_support=True)
        mock_ovn_getter.side_effect = [
            TestOvnNorth.SECURITY_GROUP_RULE_01,
            TestOvnNorth.SECURITY_GROUP_RULE_03,
        ]
        rest_data = SecurityGroupApiInputMaker(
            TestOvnNorth.SECURITY_GROUP_NAME,
            tenant_id(),
            tenant_id(),
            description=TestOvnNorth.SECURITY_GROUP_DESCRIPTION,
        ).get()

        result = ovn_north.add_security_group(rest_data)
        security_group = SecurityGroup(
            sec_group=TestOvnNorth.SECURITY_GROUP,
            sec_group_rules=[
                SecurityGroupRule(
                    TestOvnNorth.SECURITY_GROUP_RULE_01,
                    TestOvnNorth.SECURITY_GROUP,
                ),
                SecurityGroupRule(
                    TestOvnNorth.SECURITY_GROUP_RULE_03,
                    TestOvnNorth.SECURITY_GROUP,
                ),
            ],
        )
        assert_security_group_equal(result, security_group)

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.impl_idl.OvnNbApiIdlImpl.lookup'
    )
    def test_cannot_delete_assigned_sec_group(
        self, mock_lookup, mock_connection
    ):
        security_group_id = UUID(int=101)
        port_01_id = UUID(int=4)

        port_01 = OvnPortRow(
            port_01_id,
            external_ids={
                PortMapper.OVN_NIC_NAME: TestOvnNorth.PORT_NAME01,
                PortMapper.OVN_DEVICE_ID: str(port_01_id),
                PortMapper.OVN_DEVICE_OWNER: TestOvnNorth.DEVICE_OWNER_OVIRT,
                PortMapper.OVN_SECURITY_GROUPS: str(security_group_id),
            },
        )

        security_group_with_ports = OvnSecurityGroupRow(
            security_group_id,
            TestOvnNorth.SECURITY_GROUP_NAME,
            external_ids={
                SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION: '',
                SecurityGroupMapper.OVN_SECURITY_GROUP_CREATE_TS: '',
                SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS: '',
                SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: '1',
                SecurityGroupMapper.OVN_SECURITY_GROUP_TENANT: tenant_id(),
                SecurityGroupMapper.OVN_SECURITY_GROUP_PROJECT: tenant_id(),
            },
            ports=[port_01],
        )

        mock_lookup.return_value = security_group_with_ports
        ovn_north = NeutronApi(sec_group_support=True)
        with pytest.raises(BadRequestError) as ex:
            ovn_north.delete_security_group(str(security_group_id))
        assert 'Security Group {} in use'.format(security_group_id) == str(
            ex.value
        )

    def test_sec_group_rules_ip_prefix_requires_ethertype(
        self, mock_connection
    ):
        ovn_north = NeutronApi(sec_group_support=True)
        ip_prefix = '192.168.14.0/24'
        rest_data = SecurityGroupRuleApiInputMaker(
            'ingress', TestOvnNorth.SECURITY_GROUP_ID, ip_prefix=ip_prefix
        ).get()

        with pytest.raises(BadRequestError) as exception:
            ovn_north.add_security_group_rule(rest_data)
        assert 'Conflicting value ethertype {} for CIDR {}'.format(
            None, ip_prefix
        ) == str(exception.value)

    def test_invalid_v6_cidr(self, mock_connection):
        ovn_north = NeutronApi()
        rest_data = SubnetApiInputMaker(
            TestOvnNorth.SUBNET_102.external_ids.get(SubnetMapper.OVN_NAME),
            cidr=TestOvnNorth.SUBNET_CIDR,
            network_id=str(TestOvnNorth.NETWORK_ID10),
            dns_nameservers=['1.1.1.1'],
            gateway_ip='1.1.1.0',
            ip_version=6,
        ).get()
        with pytest.raises(BadRequestError) as exception:
            ovn_north.add_subnet(rest_data)
        assert str(exception.value) == (
            'The provided ip_version [6] does not match the supplied '
            'cidr=1.1.1.0/24 or gateway=1.1.1.0'
        )

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsGetCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_IPV6,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsAddCommand.'
        'execute',
        lambda cmd, check_error: TestOvnNorth.SUBNET_IPV6,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsAddCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_MTU,
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsGetCommand.execute',
        lambda cmd, check_error: TestOvnNorth.NETWORK_MTU,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsSetOptionsCommand',
        autospec=False,
    )
    def test_ipv6_support(
        self, mock_setoptions_command, mock_dbset_command, mock_connection
    ):
        for mode in [
            None,
            'dhcpv6-stateful',
            'dhcpv6-stateless',
            'dhcpv6_stateful',
            'dhcpv6_stateless',
        ]:
            ovn_north = NeutronApi()
            rest_data = SubnetApiInputMaker(
                TestOvnNorth.SUBNET_IPV6.external_ids.get(
                    SubnetMapper.OVN_NAME
                ),
                cidr=TestOvnNorth.SUBNET_IPV6_CIDR,
                network_id=str(TestOvnNorth.NETWORK_IDMTU),
                gateway_ip=TestOvnNorth.SUBNET_IPV6_GATEWAY,
                ip_version=6,
                address_mode=mode,
            ).get()

            created_subnet = ovn_north.add_subnet(rest_data)
            assert_subnet_equal(created_subnet, TestOvnNorth.SUBNET_IPV6)

    def test_ipv6_allowed_ra_modes(self, mock_connection):
        ovn_north = NeutronApi()
        slaac_rest_data = SubnetApiInputMaker(
            TestOvnNorth.SUBNET_IPV6.external_ids.get(SubnetMapper.OVN_NAME),
            cidr=TestOvnNorth.SUBNET_IPV6_CIDR,
            network_id=str(TestOvnNorth.NETWORK_IDMTU),
            gateway_ip=TestOvnNorth.SUBNET_IPV6_GATEWAY,
            ip_version=6,
            address_mode='slaac',
        ).get()

        with pytest.raises(UnsupportedDataValueError) as error:
            ovn_north.add_subnet(slaac_rest_data)
        assert str(error.value) == (
            'Setting ipv6_address_mode value to slaac is not supported. '
            'Allowed values are: [\'dhcpv6-stateful\', \'dhcpv6-stateless\','
            ' \'dhcpv6_stateful\', \'dhcpv6_stateless\']'
        )

    def test_v4_subnet_having_v6_attributes(self, mock_connection):
        ovn_north = NeutronApi()
        rest_data = SubnetApiInputMaker(
            TestOvnNorth.SUBNET_102.external_ids.get(SubnetMapper.OVN_NAME),
            cidr=TestOvnNorth.SUBNET_CIDR,
            network_id=str(TestOvnNorth.NETWORK_ID10),
            dns_nameservers=['1.1.1.1'],
            gateway_ip='1.1.1.0',
            ip_version=4,
            address_mode='dhcpv6-stateful',
        ).get()

        with pytest.raises(BadRequestError) as bre:
            ovn_north.add_subnet(rest_data)
        assert str(bre.value) == (
            'The \'ipv6_address_mode\' parameter can only be used '
            'when \'ip_version\' == 6'
        )

    def test_ipv6_subnet_stateless_mode_invalid_prefix(self, mock_connection):
        ovn_north = NeutronApi()
        stateless_dhcpv6_rest_data = SubnetApiInputMaker(
            TestOvnNorth.SUBNET_102.external_ids.get(SubnetMapper.OVN_NAME),
            cidr='bef0:1234:a890:5678::/96',
            network_id=str(TestOvnNorth.NETWORK_IDMTU),
            gateway_ip=TestOvnNorth.SUBNET_IPV6_GATEWAY,
            ip_version=6,
            address_mode='dhcpv6-stateless',
        ).get()

        with pytest.raises(BadRequestError) as bre:
            ovn_north.add_subnet(stateless_dhcpv6_rest_data)
        assert str(bre.value) == (
            'Invalid CIDR bef0:1234:a890:5678::/96 for IPv6 address mode. '
            'OVN uses the EUI-64 address format, which requires the prefix '
            'to be /64'
        )

    @mock.patch(
        'ovsdbapp.backend.ovs_idl.transaction.Transaction.commit',
        lambda tx: None,
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbSetCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspAddCommand', autospec=False
    )
    @mock.patch(
        'ovsdbapp.backend.ovs_idl.command.DbListCommand.execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LspListCommand.' 'execute',
        lambda cmd, check_error: [],
    )
    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.DhcpOptionsListCommand.'
        'execute',
        lambda cmd, check_error: [
            OvnSubnetRow(
                TestOvnNorth.SUBNET_IDV6,
                cidr=TestOvnNorth.SUBNET_IPV6_CIDR,
                ip_version=6,
                network_id=str(TestOvnNorth.NETWORK_IDMTU),
                external_ids={
                    SubnetMapper.OVN_IPV6_ADDRESS_MODE: SubnetMapper.IPV6_ADDRESS_MODE_STATELESS  # noqa: E501
                },
            )
        ],
    )
    def test_create_port_fixed_ip_on_stateless_subnet(
        self, mock_add_port, mock_update_port, mock_connection
    ):
        ovn_north = NeutronApi()
        port_rest_data = PortApiInputMaker(
            TestOvnNorth.PORT_NAME01,
            str(TestOvnNorth.NETWORK_IDMTU),
            fixed_ips=[
                {
                    PortMapper.REST_PORT_IP_ADDRESS: 'bef0:1234:a890:5678::3',
                    PortMapper.REST_PORT_SUBNET_ID: str(
                        TestOvnNorth.SUBNET_IDV6
                    ),
                }
            ],
        ).get()

        with pytest.raises(BadRequestError) as bre:
            ovn_north.add_port(port_rest_data)
        assert str(bre.value) == (
            'IPv6 address bef0:1234:a890:5678::3 cannot be directly assigned '
            'to a port on subnet 00000000-0000-0000-0000-000000000006 as the '
            'subnet is configured for automatic addresses'
        )
