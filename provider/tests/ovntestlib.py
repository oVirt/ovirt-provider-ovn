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

from ovirt_provider_config_common import tenant_id

from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import SubnetMapper
import ovndb.constants as ovnconst

TABLES = [['table0', ['column0', 'column1']]]
REMOTE = 'address://url'
SCHEMA_FILE = '/path/to/schema'


class OvnTable(object):
    def __init__(self, rows):
        self.rows = rows


class OvnRow(object):

    def __init__(self):
        self.deleted = False

    def verify(self, parent_children_column):
        pass

    def setkey(self, column_name, key, value):
        getattr(self, column_name)[key] = value

    def delete(self):
        self.deleted = True


class OvnNetworkRow(OvnRow):
    def __init__(self, uuid, name=None, other_config=None, external_ids=None,
                 ports=None):
        self.uuid = uuid
        self.name = name
        self.other_config = other_config or {}
        self.external_ids = external_ids or {}
        self.ports = ports or []


def assert_network_equal(rest_data, network):
    assert network.ls
    assert rest_data['id'] == str(network.ls.uuid)
    assert rest_data['name'] == network.ls.name
    assert rest_data['tenant_id'] == tenant_id()
    if network.localnet_lsp:
        assert_lsp_equal(rest_data, network.localnet_lsp)


def assert_lsp_equal(rest_data, localnet_lsp):
    options = localnet_lsp.options
    physical_network = options.get(ovnconst.LSP_OPTION_NETWORK_NAME)
    if physical_network:
        assert physical_network == \
               rest_data.get(NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK)
        vlan_tag = localnet_lsp.tag
        network_type = rest_data.get(NetworkMapper.REST_PROVIDER_NETWORK_TYPE)
        if vlan_tag:
            vlan_id = rest_data[NetworkMapper.REST_PROVIDER_SEGMENTATION_ID]
            assert vlan_tag[0] == vlan_id
            assert network_type == NetworkMapper.NETWORK_TYPE_VLAN
        else:
            assert network_type == NetworkMapper.NETWORK_TYPE_FLAT


class OvnPortRow(OvnRow):
    def __init__(self, uuid, name=None, external_ids=None, device_id=None,
                 addresses=None, port_type=None, options=None,
                 tag=None):
        self.uuid = uuid
        self.name = name
        self.external_ids = external_ids or {
            PortMapper.OVN_DEVICE_ID: device_id
        }
        self.dhcpv4_options = None
        self.addresses = addresses or ['unknown']
        self.up = None
        self.enabled = None
        self.type = port_type
        self.options = options if options else {}
        self.tag = [tag] if tag else []


class OvnSubnetRow(OvnRow):
    def __init__(self, uuid, name=None, cidr=None, external_ids=None,
                 options=None, network_id=None):
        self.uuid = uuid
        self.name = name
        self.cidr = cidr
        self.external_ids = external_ids or {
            SubnetMapper.OVN_NAME: 'OVN_NAME',
            SubnetMapper.OVN_NETWORK_ID: '1'
        }
        self.options = options or {
            'router': '1.1.1.1',
            'dns_server': '8.8.8.8'
        }
        self.external_ids[SubnetMapper.OVN_NETWORK_ID] = network_id or '0'


def assert_subnet_equal(actual, subnet_row):
    assert actual['id'] == str(subnet_row.uuid)
    assert actual['cidr'] == subnet_row.cidr
    assert actual.get('name') == subnet_row.external_ids.get(
        SubnetMapper.OVN_NAME
    )
    assert actual['network_id'] == subnet_row.external_ids.get(
        SubnetMapper.OVN_NETWORK_ID
    )
    assert actual['ip_version'] == SubnetMapper.IP_VERSION
    assert actual.get('enable_dhcp')
    ovn_dns_server = [subnet_row.options.get(SubnetMapper.OVN_DNS_SERVER)]
    actual_dns_nameservers = actual.get('dns_nameservers')
    if actual_dns_nameservers or ovn_dns_server:
        assert actual_dns_nameservers == ovn_dns_server
    assert actual.get('gateway_ip') == subnet_row.options.get(
        SubnetMapper.OVN_GATEWAY
    )
    assert actual.get('allocation_pools')


class OvnRouterRow(OvnRow):
    def __init__(self, uuid, name=None, external_ids=None, ports=None):
        self.uuid = uuid
        self.name = name
        self.enabled = [True]
        self.external_ids = external_ids or {}
        self.ports = ports or []


class OvnRouterPort(object):
    pass
