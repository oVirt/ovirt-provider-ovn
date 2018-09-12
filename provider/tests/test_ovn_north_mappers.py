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
from datetime import datetime

import pytest

from constants import LSP_OPTION_NETWORK_NAME
from ovirt_provider_config_common import tenant_id

import neutron.constants as neutron_constants
from neutron.neutron_api_mappers import Network
from neutron.neutron_api_mappers import NetworkMapper
from neutron.neutron_api_mappers import NetworkPort
from neutron.neutron_api_mappers import PortMapper
from neutron.neutron_api_mappers import SubnetMapper
from neutron.neutron_api_mappers import RestDataError
from neutron.neutron_api_mappers import Router
from neutron.neutron_api_mappers import RouterMapper
from neutron.neutron_api_mappers import SecurityGroup
from neutron.neutron_api_mappers import SecurityGroupMapper
from neutron.neutron_api_mappers import SecurityGroupRuleMapper


from ovntestlib import assert_network_equal
from ovntestlib import assert_port_equal
from ovntestlib import assert_subnet_equal
from ovntestlib import assert_router_equal
from ovntestlib import assert_security_group_equal
from ovntestlib import assert_security_group_rule_equal
from ovntestlib import OvnSubnetRow
from ovntestlib import OvnNetworkRow
from ovntestlib import OvnPortRow
from ovntestlib import OvnRouterRow
from ovntestlib import OvnSecurityGroupRow
from ovntestlib import OvnSecurityGroupRuleRow
from ovntestlib import StaticRouteRow


FIXED_IP_ADDRESS = '1.1.1.1'
MAC_ADDRESS = '01:00:00:00:00:11'
NETWORK_ID1 = '1'
NETWORK_UUID = UUID(int=606)
NETWORK_NAME = 'skynet'
PORT_NAME = 'port1'
PORT_UUID = UUID(int=101)
SECURITY_GROUP_UUID = UUID(int=100)
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

    def test_port_to_rest_port_security(self):
        port_data = OvnPortRow(
            PORT_UUID,
            addresses=['{} {}'.format(MAC_ADDRESS, FIXED_IP_ADDRESS)],
            name=PORT_NAME,
            external_ids={
                PortMapper.OVN_NIC_NAME: PORT_NAME,
                PortMapper.OVN_DEVICE_ID: str(PORT_UUID),
                PortMapper.OVN_DEVICE_OWNER: 'ovirt',
            },
            options={LSP_OPTION_NETWORK_NAME: PORT_NAME},
            port_security=[MAC_ADDRESS]
        )
        self.__assert_port_data_equal(port_data)

    def test_router_to_rest_minimal(self):
        row = OvnRouterRow(SUBNET_ID102, external_ids={
            SubnetMapper.OVN_NETWORK_ID: NETWORK_ID1
        })
        router = Router(
            lr=row, ext_gw_ls_id=NETWORK_ID1,
            ext_gw_dhcp_options_id=SUBNET_ID102, gw_ip='1.1.1.1'
        )
        router_rest = RouterMapper.row2rest(router)
        assert_router_equal(router_rest, router)

    def test_router_to_rest_with_routes(self):
        row = OvnRouterRow(
            SUBNET_ID102,
            external_ids={
                SubnetMapper.OVN_NETWORK_ID: NETWORK_ID1
            },
            static_routes=[
                StaticRouteRow(ip_prefix='0.0.0.0/24', nexthop='1.1.1.1')
            ]
        )
        router = Router(
            lr=row, ext_gw_ls_id=NETWORK_ID1,
            ext_gw_dhcp_options_id=SUBNET_ID102, gw_ip='1.1.1.1',
        )
        router_rest = RouterMapper.row2rest(router)
        assert_router_equal(router_rest, router)

    def test_is_bool(self):
        NetworkMapper._boolean_or_exception('', True)
        NetworkMapper._boolean_or_exception('', False)
        with pytest.raises(RestDataError) as expected_exception:
            NetworkMapper._boolean_or_exception('attr1', 'boloni')
        assert expected_exception.value.message == 'attr1 must be of type bool'
        with pytest.raises(RestDataError) as expected_exception:
            NetworkMapper._boolean_or_exception('attr2', [])
        assert expected_exception.value.message == 'attr2 must be of type bool'

    def test_acl_to_rest_minimal(self):
        name = 'sec1'
        desc = 'lotsofsafety'
        timestamp = datetime.utcnow().isoformat()
        external_ids = {
            SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION: desc,
            SecurityGroupMapper.OVN_SECURITY_GROUP_CREATE_TS: timestamp,
            SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS: timestamp,
            SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: '1',
            SecurityGroupMapper.OVN_SECURITY_GROUP_PROJECT: tenant_id(),
            SecurityGroupMapper.OVN_SECURITY_GROUP_TENANT: tenant_id()
        }
        row = OvnSecurityGroupRow(
            SECURITY_GROUP_UUID, name=name, external_ids=external_ids
        )

        sec_group = SecurityGroup(row, [])
        sec_group_rest = SecurityGroupMapper.row2rest(sec_group)
        assert_security_group_equal(sec_group_rest, sec_group)

    def test_acl_to_rest_with_optionals(self):
        rule_id = str(UUID(int=1))
        group_id = str(UUID(int=3))
        acl_external_ids = {
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID: group_id,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_ETHERTYPE:
                neutron_constants.IPV4_ETHERTYPE,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_PROTOCOL:
                neutron_constants.PROTO_NAME_UDP,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_MIN_PORT: 6780,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_MAX_PORT: 6799,
        }
        security_group_rule = OvnSecurityGroupRuleRow(
            rule_id,
            'from-lport', 'ip4 && udp && ', 1001, group_id, 'allow',
            acl_external_ids
        )
        assert_security_group_rule_equal(
            SecurityGroupRuleMapper.row2rest(security_group_rule),
            security_group_rule
        )

    def test_port_group_to_rest_with_rules(self):
        name = 'sec1'
        desc = 'lotsofsafety'
        timestamp = datetime.utcnow().isoformat()
        external_ids = {
            SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION: desc,
            SecurityGroupMapper.OVN_SECURITY_GROUP_CREATE_TS: timestamp,
            SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS: timestamp,
            SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: '1',
            SecurityGroupMapper.OVN_SECURITY_GROUP_PROJECT: tenant_id(),
            SecurityGroupMapper.OVN_SECURITY_GROUP_TENANT: tenant_id()
        }
        row = OvnSecurityGroupRow(
            SECURITY_GROUP_UUID, name=name, external_ids=external_ids
        )
        rule_id = str(UUID(int=1))
        acl_external_ids = {
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID:
                SECURITY_GROUP_UUID,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_ETHERTYPE:
                neutron_constants.IPV4_ETHERTYPE,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_PROTOCOL:
                neutron_constants.PROTO_NAME_UDP,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_MIN_PORT: 6780,
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_MAX_PORT: 6799,
        }
        security_group_rule = OvnSecurityGroupRuleRow(
            rule_id,
            'to-lport', 'ip4 && udp && ', 1001, SECURITY_GROUP_UUID, 'allow',
            acl_external_ids
        )

        sec_group = SecurityGroup(row, [security_group_rule])
        sec_group_rest = SecurityGroupMapper.row2rest(sec_group)
        assert_security_group_equal(sec_group_rest, sec_group)
