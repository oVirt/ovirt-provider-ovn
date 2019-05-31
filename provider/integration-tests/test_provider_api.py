# Copyright 2018 Red Hat, Inc.
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

import pytest
import requests


ENDPOINT = 'http://localhost:9696/v2.0/'
SUBNET_ENDPOINT = ENDPOINT + 'subnets/'
PORT_ENDPOINT = ENDPOINT + 'ports/'


@pytest.fixture(scope='module')
def logical_switch():
    payload = {
        'network': {'name': 'ls0'}
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


@pytest.fixture(scope='module')
def subnet(logical_switch):
    payload = {
        'subnet': {
            'network_id': logical_switch['id'],
            'ip_version': 6,
            'cidr': '1234::/64',
            'gateway_ip': '1234::1',
            'ipv6_address_mode': 'dhcpv6_stateless'
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


def test_get_network(logical_switch):
    networks = _get_and_assert('networks')
    assert len(networks) == 1
    assert networks.pop()['name'] == logical_switch['name']


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
        'subnet': {'ipv6_address_mode': 'dhcpv6_stateful'}
    }
    r = requests.put(url, json=update_payload)
    _expect_failure(r, 400, 'Invalid data found: ipv6_address_mode')


def test_get_port(subnet, logical_port):
    ports = _get_and_assert('ports')
    assert len(ports) == 1
    assert ports[0]['id'] == logical_port['id']
    assert ports[0]['mac_address'] == logical_port['mac_address']
    assert ports[0]['fixed_ips'][0]['subnet_id'] == subnet['id']


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
