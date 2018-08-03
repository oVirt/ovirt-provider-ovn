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
from ovirt_provider_config_common import dhcp_mtu

import constants as ovnconst
import neutron.ip as ip_utils

from neutron.neutron_api_mappers import NetworkMapper
from neutron.neutron_api_mappers import PortMapper
from neutron.neutron_api_mappers import SubnetMapper

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
    assert rest_data['mtu'] == int(
        network.ls.external_ids.get(NetworkMapper.OVN_MTU, dhcp_mtu())
    )
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


def assert_port_equal(rest_data, port):
    assert rest_data['id'] == str(port.lsp.uuid)
    assert rest_data['network_id'] == str(port.ls.uuid)
    assert rest_data['name'] == port.lsp.external_ids[PortMapper.OVN_NIC_NAME]
    device_owner = port.lsp.external_ids.get(PortMapper.OVN_DEVICE_OWNER)
    assert rest_data.get(PortMapper.REST_PORT_DEVICE_OWNER) == device_owner
    device_id = port.lsp.external_ids[PortMapper.OVN_DEVICE_ID]
    assert rest_data['device_id'] == device_id
    assert rest_data['security_groups'] == []
    assert rest_data['port_security_enabled'] is False
    assert rest_data['tenant_id'] == tenant_id()
    assert rest_data.get('fixed_ips') == PortMapper.get_fixed_ips(
        port.lsp, port.dhcp_options, port.lrp
    )
    assert rest_data.get('mac_address') == ip_utils.get_port_mac(port.lsp)


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
    def __init__(self, uuid, name=None, external_ids=None, ports=None,
                 static_routes=None):
        self.uuid = uuid
        self.name = name
        self.enabled = [True]
        self.external_ids = external_ids or {}
        self.ports = ports or []
        self.static_routes = static_routes or []


class StaticRouteRow(OvnRow):
    def __init__(self, ip_prefix=None, nexthop=None):
        self.ip_prefix = ip_prefix
        self.nexthop = nexthop


def assert_router_equal(rest_data, router):
    lr = router.lr
    assert lr
    assert rest_data['id'] == str(lr.uuid)
    assert rest_data['name'] == lr.name
    rest_state = rest_data['admin_state_up']
    assert rest_state == lr.enabled[0] if lr.enabled else rest_state is True
    if router.ext_gw_ls_id:
        gw_info = rest_data['external_gateway_info']

        assert gw_info['network_id'] == router.ext_gw_ls_id
        fixed_ips = gw_info['external_fixed_ips'][0]
        assert fixed_ips['subnet_id'] == router.ext_gw_dhcp_options_id
        assert fixed_ips['ip_address'] == router.gw_ip
    if lr.static_routes:
        assert_static_routes_equal(
            rest_data['routes'], lr.static_routes)


def assert_static_routes_equal(rest_data, routes):
    new_routes, removed_routes = ip_utils.diff_routes(rest_data, routes)
    assert not new_routes
    assert not removed_routes


class OvnRouterPort(object):
    pass


class ApiInputMaker(object):
    def get(self):
        """
        Creates dicts meant to be used in unit tests, where the only
        present keys will feature non-null values.
        Each subclass has to implement its constructor, defaulting the optional
        values to None.
        :return: a dict with all the non-null attributes key-value pairs
        """
        return {
            v[0]: v[1] for (_, v) in self.__dict__.items()
            if v[1] is not None
        }


class NetworkApiInputMaker(ApiInputMaker):
    def __init__(
            self,
            name,
            provider_type=None,
            provider_physical_network=None,
            vlan_tag=None,
            mtu=None
    ):
        self._name = (NetworkMapper.REST_NETWORK_NAME, name)
        self._provider_type = (
            NetworkMapper.REST_PROVIDER_NETWORK_TYPE, provider_type
        )
        self._provider_network = (
            NetworkMapper.REST_PROVIDER_PHYSICAL_NETWORK,
            provider_physical_network
        )
        self._vlan_tag = (
            NetworkMapper.REST_PROVIDER_SEGMENTATION_ID, vlan_tag
        )
        self.mtu = (NetworkMapper.REST_MTU, mtu)


class SubnetApiInputMaker(ApiInputMaker):
    def __init__(
            self,
            name,
            cidr=None,
            network_id=None,
            dns_nameservers=None,
            gateway_ip=None,
            enable_dhcp=None
    ):
        self._name = (SubnetMapper.REST_SUBNET_NAME, name)
        self._cidr = (SubnetMapper.REST_SUBNET_CIDR, cidr)
        self._network_id = (SubnetMapper.REST_SUBNET_NETWORK_ID, network_id)
        self._dns_servers = (
            SubnetMapper.REST_SUBNET_DNS_NAMESERVERS, dns_nameservers
        )
        self._gateway_ip = (SubnetMapper.REST_SUBNET_GATEWAY_IP, gateway_ip)
        self._enable_dhcp = (SubnetMapper.REST_SUBNET_ENABLE_DHCP, enable_dhcp)


class PortApiInputMaker(ApiInputMaker):
    def __init__(
            self,
            name,
            network_id,
            device_id=None,
            device_owner=None,
            admin_state_up=None,
            mac_address=None,
            fixed_ips=None,
            binding_host_id=None
    ):
        self._name = (PortMapper.REST_PORT_NAME, name)
        self._network_id = (PortMapper.REST_PORT_NETWORK_ID, network_id)
        self._device_id = (PortMapper.REST_PORT_DEVICE_ID, device_id)
        self._device_owner = (PortMapper.REST_PORT_DEVICE_OWNER, device_owner)
        self._port_up = (PortMapper.REST_PORT_ADMIN_STATE_UP, admin_state_up)
        self._mac_address = (PortMapper.REST_PORT_MAC_ADDRESS, mac_address)
        self._fixed_ips = (PortMapper.REST_PORT_FIXED_IPS, fixed_ips)
        self._binding_host_id = (
            PortMapper.REST_PORT_BINDING_HOST, binding_host_id
        )
