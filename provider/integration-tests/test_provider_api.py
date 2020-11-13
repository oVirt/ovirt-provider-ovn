# Copyright 2018-2020 Red Hat, Inc.
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
#

import contextlib
import json

import pytest
import six.moves.http_client as http_client
import requests

from lib.api_lib import update_and_assert
from lib.api_lib import SecurityGroup
from lib.api_lib import SecurityGroupRule


ENDPOINT_HOST = 'localhost:9696'
ENDPOINT_PATH = '/v2.0/'
ENDPOINT = 'http://' + ENDPOINT_HOST + ENDPOINT_PATH
SUBNET_ENDPOINT = ENDPOINT + 'subnets/'
PORT_ENDPOINT = ENDPOINT + 'ports/'


EXT_NET_NAME = 'extnet'
EXT_NET_NAME1 = 'extnet1'
PROVIDER_TYPE = 'vlan'
VLAN_ID = 666
VLAN_ID_25 = 25


@pytest.fixture(scope='module')
def logical_switch():
    with _network('ls0') as network:
        yield network


@pytest.fixture
def ext_net_logical_switch():
    with _network('pls0', localnet=EXT_NET_NAME, vlan_id=VLAN_ID) as network:
        yield network


@pytest.fixture(scope='module')
def subnet(logical_switch):
    with _subnet(logical_switch) as subnet:
        yield subnet


@pytest.fixture(scope='module')
def logical_port(logical_switch, subnet):
    payload = {
        'port': {
            'admin_state_up': True,
            'fixed_ips': [
                {
                    'subnet_id': subnet['id']
                }
            ],
            'mac_address': 'fa:16:3e:c9:cb:f0',
            'name': 'private-port',
            'network_id': logical_switch['id'],
            'port_security_enabled': True,
            'project_id': 'd6700c0c9ffa4f1cb322cd4a1f3906fa',
            'tenant_id': 'd6700c0c9ffa4f1cb322cd4a1f3906fa',
        }
    }
    response = requests.post(
        'http://localhost:9696/v2.0/ports/', json=payload
    )
    if response.status_code not in range(200, 205):
        raise Exception('could not create port')
    try:
        yield response.json()['port']
    finally:
        requests.delete(
            'http://localhost:9696/v2.0/ports/' +
            response.json()['port']['id']
        )


@pytest.fixture(scope='module')
def broken_port(logical_switch, subnet):
    invalid_mac = 'fa:16:3e:c9:cb:xx'
    payload = {
        'port': {
            'admin_state_up': True,
            'fixed_ips': [
                {
                    'subnet_id': subnet['id']
                }
            ],
            'mac_address': invalid_mac,
            'name': 'broken-port',
            'network_id': logical_switch['id'],
            'port_security_enabled': True,
            'project_id': 'd6700c0c9ffa4f1cb322cd4a1f3906fa',
            'tenant_id': 'd6700c0c9ffa4f1cb322cd4a1f3906fa',
        }
    }
    response = requests.post(
        'http://localhost:9696/v2.0/ports/', json=payload
    )
    _expect_failure(
        response, 400,
        'Invalid input for mac_address. Reason: \'fa:16:3e:c9:cb:xx\' '
        'is not a valid MAC address.'.format(invalid_mac)
    )


@pytest.fixture(
    scope='module', params=[True, False], ids=['with_subnet', 'without_subnet']
)
def broken_port_sec_group(request, logical_switch, subnet):
    nonexistent_sec_group = '2d6a7cf1-0105-4864-b94b-8ff0b30c41a7'
    payload = {
        'port': {
            'admin_state_up': True,
            'mac_address': 'fa:16:3e:c9:cb:f0',
            'name': 'broken-port',
            'network_id': logical_switch['id'],
            'port_security_enabled': True,
            'project_id': 'd6700c0c9ffa4f1cb322cd4a1f3906fa',
            'security_groups': [
                nonexistent_sec_group
            ],
            'tenant_id': 'd6700c0c9ffa4f1cb322cd4a1f3906fa',
        }
    }
    if request.param:
        payload['fixed_ips'] = {'subnet_id': subnet['id']}

    response = requests.post(
        'http://localhost:9696/v2.0/ports/', json=payload
    )
    _expect_failure(
        response, 500,
        'Port group {} does not exist'.format(nonexistent_sec_group)
    )


@pytest.fixture(scope='module')
def icmp_group():
    with SecurityGroup('icmp_group', None) as sec_group:
        yield sec_group


@pytest.fixture(scope='module')
def limited_access_group(icmp_group):
    with SecurityGroup(
            'limited_access',
            'only members of the icmp group will access'
    ) as limited_group:
        with SecurityGroupRule(
                limited_group.id, 'ingress',
                ether_type='IPv4', protocol='icmp',
                remote_group_id=icmp_group.id):
            yield limited_group


def test_get_network(logical_switch):
    networks = _get_and_assert('networks')
    assert len(networks) == 1
    assert networks.pop()['name'] == logical_switch['name']


def test_get_physnet(ext_net_logical_switch):
    networks = _get_and_assert(
        'networks', filter_key='name', filter_value='pls0'
    )
    assert len(networks) == 1
    physnet = networks.pop()
    assert physnet['name'] == ext_net_logical_switch['name']
    assert physnet['provider:physical_network'] == EXT_NET_NAME
    assert physnet['provider:network_type'] == PROVIDER_TYPE
    assert physnet['provider:segmentation_id'] == VLAN_ID


def test_update_physnet(ext_net_logical_switch):
    networks = _get_and_assert(
        'networks', filter_key='name', filter_value='pls0'
    )
    assert len(networks) == 1
    physnet = networks.pop()
    update_network_data = {
        'network': {
            'provider:physical_network': EXT_NET_NAME1,
            'provider:network_type': PROVIDER_TYPE,
            'provider:segmentation_id': VLAN_ID_25,
        }
    }
    update_and_assert('networks', physnet['id'], update_network_data)


def test_filter(logical_switch):
    networks = _get_and_assert('networks', 'name', 'ls0')
    assert len(networks) == 1
    assert networks.pop()['name'] == logical_switch['name']
    assert len(_get_and_assert('networks', 'name', 'kangaroo')) == 0


def test_limiter(logical_switch):
    networks = _get_and_assert('networks', 'limit', '1000')
    assert len(networks) == 1
    assert networks.pop()['name'] == logical_switch['name']


def test_get_subnet(subnet):
    subnets = _get_and_assert('subnets')
    assert len(subnets) == 1
    api_subnet = subnets.pop()
    assert api_subnet['network_id'] == subnet['network_id']
    assert api_subnet['ip_version'] == subnet['ip_version']
    assert api_subnet['cidr'] == subnet['cidr']
    assert api_subnet['gateway_ip'] == subnet['gateway_ip']
    assert api_subnet['ipv6_address_mode'] == subnet['ipv6_address_mode']


def test_ipv6_address_mode_not_updateable(subnet):
    url = SUBNET_ENDPOINT + subnet['id']
    update_payload = {
        'subnet': {'ipv6_address_mode': 'dhcpv6-stateful'}
    }
    r = requests.put(url, json=update_payload)
    _expect_failure(r, 400, 'Invalid data found: ipv6_address_mode')


def test_get_port(subnet, logical_port):
    ports = _get_and_assert('ports')
    assert len(ports) == 1
    assert ports[0]['id'] == logical_port['id']
    assert ports[0]['mac_address'] == logical_port['mac_address']
    assert ports[0]['fixed_ips'][0]['subnet_id'] == subnet['id']


def test_update_port(subnet, logical_port):
    update_port_data = {"port": {"port_security_enabled": True}}

    update_and_assert('ports', logical_port['id'], update_port_data)


def test_update_network_mtu():
    with _network('update_mtu_network') as network:
        update_network_data = {'network': {'mtu': 1501}}
        update_and_assert('networks', network['id'], update_network_data)


def test_update_network_with_subnet_mtu(logical_switch, subnet):
    orig_mtu = logical_switch['mtu']
    update_network_data = {'network': {'mtu': 1501}}
    try:
        update_and_assert('networks', logical_switch['id'],
                          update_network_data)
    finally:
        update_network_data['network']['mtu'] = orig_mtu
        update_and_assert('networks', logical_switch['id'],
                          update_network_data)


def test_create_invalid_port_with_mac(subnet, broken_port):
    json_response = _get_and_assert('ports')
    assert json_response[0]['name'] == 'private-port'

    private_port_data = _get_and_assert(
        'ports', filter_key='name', filter_value='private-port'
    )
    assert json_response == private_port_data

    _expect_no_leftovers('broken-port')


def test_create_port_with_nonexisting_sec_group(
    broken_port_sec_group
):
    json_response = _get_and_assert('ports')
    assert json_response[0]['name'] == 'private-port'

    private_port_data = _get_and_assert(
        'ports', filter_key='name', filter_value='private-port'
    )
    assert json_response == private_port_data

    _expect_no_leftovers('broken-port')


class TestSecurityGroupsApi(object):
    def test_rule_to_group_association(self, icmp_group):
        with SecurityGroupRule(
                icmp_group.id, 'ingress',
                ether_type='IPv4', protocol='icmp'
        ) as sec_group_rule:
            assert icmp_group.id == sec_group_rule.security_group_id

    def test_rule_to_group_association_with_remote_group_id(self, icmp_group):
        limited_access_group = SecurityGroup(
            'limited_access',
            'only members of the icmp group will access'
        )
        with limited_access_group as limited_group:
            with SecurityGroupRule(
                    limited_group.id, 'ingress',
                    ether_type='IPv4', protocol='icmp',
                    remote_group_id=icmp_group.id
            ) as sec_group_rule:
                assert limited_group.id == sec_group_rule.security_group_id
                assert icmp_group.id == sec_group_rule.remote_group_id

    def test_rule_to_group_association_with_remote_group_id_on_get(
            self, icmp_group, limited_access_group
    ):
        enabling_group = SecurityGroup.get_security_group_by_name(
            'icmp_group'
        )
        limited_group = SecurityGroup.get_security_group_by_name(
            'limited_access'
        )

        limited_group_rules = limited_group.rules
        remote_group_rule = [
            rule for rule in limited_group_rules
            if rule.get('remote_group_id')
        ][0]
        assert remote_group_rule['remote_group_id'] == enabling_group.id
        for group in (enabling_group, limited_group):
            for rule in group.rules:
                assert rule['security_group_id'] == group.id


def test_not_found_escape():
    conn = http_client.HTTPConnection(ENDPOINT_HOST)
    conn.request(
        'GET',
        ENDPOINT_PATH + 'xxx../","message":"<injected_message>'
    )
    response = conn.getresponse()
    expected_code = 404
    assert response.status == expected_code
    data = json.loads(response.read())
    assert data['error']['code'] == expected_code
    assert data['error']['message'].startswith('Incorrect path')


def _expect_no_leftovers(broken_port_name):
    broken_port_data = _get_and_assert(
        'ports', filter_key='name', filter_value=broken_port_name,
    )
    assert not broken_port_data


def _get_and_assert(entity_type, filter_key=None, filter_value=None):
    url = ENDPOINT + entity_type + (
        '?{key}={value}'.format(key=filter_key, value=filter_value)
        if filter_key and filter_value else ''
    )
    r = requests.get(url)
    assert r.status_code == 200
    return r.json()[entity_type]


def _expect_failure(response, expected_status_code, expected_error_message):
    assert response.status_code == expected_status_code
    assert response.json()['error']['message'] == expected_error_message


@contextlib.contextmanager
def _network(name, localnet=None, vlan_id=None):
    network_data = {'name': name}
    if localnet:
        network_data['provider:physical_network'] = localnet
    if vlan_id:
        network_data['provider:network_type'] = 'vlan'
        network_data['provider:segmentation_id'] = vlan_id
    payload = {
        'network': network_data
    }
    response = requests.post(
        'http://localhost:9696/v2.0/networks/', json=payload
    )
    if response.status_code not in range(200, 205):
        raise Exception('could not create network')
    try:
        yield response.json()['network']
    finally:
        requests.delete(
            'http://localhost:9696/v2.0/networks/' +
            response.json()['network']['id']
        )


@contextlib.contextmanager
def _subnet(network):
    payload = {
        'subnet': {
            'network_id': network['id'],
            'ip_version': 6,
            'cidr': '1234::/64',
            'gateway_ip': '1234::1',
            'ipv6_address_mode': 'dhcpv6-stateless'
        }
    }
    response = requests.post(
        'http://localhost:9696/v2.0/subnets/', json=payload
    )
    if response.status_code not in range(200, 205):
        raise Exception('could not create subnet')
    try:
        yield response.json()['subnet']
    finally:
        requests.delete(
            'http://localhost:9696/v2.0/subnets/' +
            response.json()['subnet']['id']
        )
