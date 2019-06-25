# Copyright 2019 Red Hat, Inc.
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


import contextlib
import requests
import pytest
from time import sleep

from lib.ansiblelib import get_playbook
from lib.api_lib import get_network_by_name
from lib.api_lib import get_router_by_name
from lib.api_lib import update_and_assert
from lib.dockerlib import inner_ping
from lib.dockerlib import get_container_id_from_img_name
from lib.dockerlib import reconfigure_interface

CONTROLLER_CONTAINER_ID = get_container_id_from_img_name(
        'tripleomaster/centos-binary-ovn-controller:current-tripleo-rdo'
)
PROVIDER_CONTAINER_ID = get_container_id_from_img_name(
            'maiqueb/ovirt_provider_ovn'
) or get_container_id_from_img_name(
            'maiqueb/ovirt_provider_ovn_fedora'
)

SAME_SUBNET = {
    'network_points': [
        {
            'name': 'lport1',
            'subnet_name': 'subnet1',
            'cidr': 'bef0:1234:a890:5678::/64',
            'mac': '00:00:00:11:11:11',
            'network': 'net1',
            'ns': 'ns1',
            'ip_version': 6
        },
        {
            'name': 'lport2',
            'subnet_name': 'subnet1',
            'cidr': 'bef0:1234:a890:5678::/64',
            'mac': '00:00:00:22:22:22',
            'network': 'net1',
            'ns': 'ns2',
            'ip_version': 6
        },
    ],
    'provider_container_id': PROVIDER_CONTAINER_ID,
    'controller_container_id': CONTROLLER_CONTAINER_ID
}

MULTIPLE_SUBNETS_STATELESS = {
    'network_points': [
        {
            'name': 'lport1',
            'subnet_name': 'subnet1',
            'cidr': 'bef0:1234:a890:5678::/64',
            'mac': '00:00:00:33:33:33',
            'network': 'net1',
            'ns': 'ns1',
            'ip_version': 6,
            'gateway_ip': 'bef0:1234:a890:5678::1',
            'ipv6_address_mode': 'dhcpv6_stateless'
        },
        {
            'name': 'lport2',
            'subnet_name': 'subnet2',
            'cidr': 'def0:abcd::/64',
            'mac': '00:00:00:44:44:44',
            'network': 'net2',
            'ns': 'ns2',
            'ip_version': 6,
            'gateway_ip': 'def0:abcd::1',
            'ipv6_address_mode': 'dhcpv6_stateless'
        },
    ],
    'routers': [
        {
            'name': 'router0',
            'interfaces': [
                'subnet1',
                'subnet2'
            ]
        }
    ],
    'provider_container_id': PROVIDER_CONTAINER_ID,
    'controller_container_id': CONTROLLER_CONTAINER_ID
}

MULTIPLE_SUBNETS_STATEFUL = {
    'network_points': [
        {
            'name': 'lport1',
            'subnet_name': 'subnet1',
            'cidr': 'bef0:1234:a890:5678::/64',
            'mac': '00:00:00:55:55:55',
            'network': 'net1',
            'ns': 'ns1',
            'ip_version': 6,
            'gateway_ip': 'bef0:1234:a890:5678::1'
        },
        {
            'name': 'lport2',
            'subnet_name': 'subnet2',
            'cidr': 'def0:abcd::/64',
            'mac': '00:00:00:66:66:66',
            'network': 'net2',
            'ns': 'ns2',
            'ip_version': 6,
            'gateway_ip': 'def0:abcd::1'
        },
    ],
    'routers': [
        {
            'name': 'router0',
            'interfaces': [
                'subnet1',
                'subnet2'
            ]
        }
    ],
    'provider_container_id': PROVIDER_CONTAINER_ID,
    'controller_container_id': CONTROLLER_CONTAINER_ID
}

MULTIPLE_SUBNETS_STATEFUL_NO_ROUTER = {
    'network_points': [
        {
            'name': 'lport1',
            'subnet_name': 'subnet1',
            'cidr': 'bef0:1234:a890:5678::/64',
            'mac': '00:00:00:55:55:55',
            'network': 'net1',
            'ns': 'ns1',
            'ip_version': 6,
            'gateway_ip': 'bef0:1234:a890:5678::1'
        },
        {
            'name': 'lport2',
            'subnet_name': 'subnet2',
            'cidr': 'def0:abcd::/64',
            'mac': '00:00:00:66:66:66',
            'network': 'net2',
            'ns': 'ns2',
            'ip_version': 6,
            'gateway_ip': 'def0:abcd::1'
        },
    ],
    'provider_container_id': PROVIDER_CONTAINER_ID,
    'controller_container_id': CONTROLLER_CONTAINER_ID
}

SINGLE_SUBNET_STATEFUL_WEIRD_PREFIX = {
    'network_points': [
        {
            'name': 'lport1',
            'subnet_name': 'subnet1',
            'ip': 'fc00::10',
            'cidr': 'fc00::/96',
            'mac': '00:00:00:55:55:55',
            'network': 'net1',
            'ns': 'ns1',
            'ip_version': 6,
            'gateway_ip': 'fc00::1'
        },
        {
            'name': 'lport2',
            'subnet_name': 'subnet1',
            'ip': 'fc00::20',
            'cidr': 'fc00::/96',
            'mac': '00:00:00:66:66:66',
            'network': 'net1',
            'ns': 'ns2',
            'ip_version': 6,
            'gateway_ip': 'fc00::1'
        },
    ],
    'provider_container_id': PROVIDER_CONTAINER_ID,
    'controller_container_id': CONTROLLER_CONTAINER_ID
}

PROVIDER_URL = 'http://localhost:9696/v2.0/'


@pytest.fixture
def setup_dataplane_single_subnet():
    get_playbook('create_l2l3_scenario.yml', SAME_SUBNET).run(
        enable_idempotency_checker=False
    )
    try:
        yield
    finally:
        get_playbook('reset_scenario.yml', SAME_SUBNET).run(
            enable_idempotency_checker=False
        )


@pytest.fixture
def setup_dataplane_multiple_subnet():
    get_playbook('create_l2l3_scenario.yml', MULTIPLE_SUBNETS_STATELESS).run(
        enable_idempotency_checker=False
    )
    try:
        yield
    finally:
        get_playbook('reset_scenario.yml', MULTIPLE_SUBNETS_STATELESS).run(
            enable_idempotency_checker=False
        )


@pytest.fixture
def setup_dataplane_multiple_subnet_stateful_no_router():
    get_playbook(
        'create_l2l3_scenario.yml', MULTIPLE_SUBNETS_STATEFUL_NO_ROUTER
    ).run(enable_idempotency_checker=False)
    try:
        yield
    finally:
        get_playbook(
            'reset_scenario.yml', MULTIPLE_SUBNETS_STATEFUL_NO_ROUTER
        ).run(enable_idempotency_checker=False)


@pytest.fixture
def setup_dataplane_multiple_subnet_stateful_with_router():
    get_playbook(
        'create_l2l3_scenario.yml', MULTIPLE_SUBNETS_STATEFUL
    ).run(enable_idempotency_checker=False)
    try:
        yield
    finally:
        get_playbook(
            'reset_scenario.yml', MULTIPLE_SUBNETS_STATEFUL
        ).run(enable_idempotency_checker=False)


@pytest.fixture
def setup_dataplane_single_subnet_weird_prefix():
    get_playbook(
        'create_l2l3_scenario.yml', SINGLE_SUBNET_STATEFUL_WEIRD_PREFIX
    ).run(enable_idempotency_checker=False)
    try:
        yield
    finally:
        get_playbook(
            'reset_scenario.yml', SINGLE_SUBNET_STATEFUL_WEIRD_PREFIX
        ).run(enable_idempotency_checker=False)


def test_single_subnet(setup_dataplane_single_subnet):
    icmp_src_conf = SAME_SUBNET['network_points'][0]
    icmp_dst_conf = SAME_SUBNET['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=0, ip_version=6
    )


def test_single_subnet_weird_prefix(
        setup_dataplane_single_subnet_weird_prefix
):
    icmp_src_conf = SINGLE_SUBNET_STATEFUL_WEIRD_PREFIX['network_points'][0]
    icmp_dst_conf = SINGLE_SUBNET_STATEFUL_WEIRD_PREFIX['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    sleep(5)
    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=0, ip_version=6
    )


def test_multiple_subnets(setup_dataplane_multiple_subnet):
    icmp_src_conf = MULTIPLE_SUBNETS_STATELESS['network_points'][0]
    icmp_dst_conf = MULTIPLE_SUBNETS_STATELESS['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    assert len(_get_routers()) == 1
    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=0, ip_version=6
    )


def test_multiple_subnets_stateful(
        setup_dataplane_multiple_subnet_stateful_with_router
):
    icmp_src_conf = MULTIPLE_SUBNETS_STATEFUL['network_points'][0]
    icmp_dst_conf = MULTIPLE_SUBNETS_STATEFUL['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    assert len(_get_routers()) == 1
    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=0, ip_version=6
    )


def test_multiple_subnets_stateful_no_connectivity(
        setup_dataplane_multiple_subnet_stateful_no_router
):
    icmp_src_conf = MULTIPLE_SUBNETS_STATEFUL_NO_ROUTER['network_points'][0]
    icmp_dst_conf = MULTIPLE_SUBNETS_STATEFUL_NO_ROUTER['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    assert len(_get_routers()) == 0
    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=2, ip_version=6
    )


def test_configure_network_mtu_via_ras(setup_dataplane_multiple_subnet):
    icmp_src_conf = MULTIPLE_SUBNETS_STATELESS['network_points'][0]
    icmp_dst_conf = MULTIPLE_SUBNETS_STATELESS['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    assert len(_get_routers()) == 1
    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=0, ip_version=6,
        data_size=1301
    )

    # update the network MTU
    network = get_network_by_name(icmp_dst_conf.get('network'))
    assert network
    _update_network_mtu(network['id'], 1300)
    reconfigure_interface(
        CONTROLLER_CONTAINER_ID, icmp_dst_conf['ns'], icmp_dst_conf['name']
    )
    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=1, ip_version=6,
        data_size=1301
    )


def test_disable_router(setup_dataplane_multiple_subnet):
    icmp_src_conf = MULTIPLE_SUBNETS_STATELESS['network_points'][0]
    icmp_dst_conf = MULTIPLE_SUBNETS_STATELESS['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=0, ip_version=6
    )

    router_name = MULTIPLE_SUBNETS_STATELESS['routers'][0]['name']
    router_uuid = _get_router_uuid(router_name)
    with disable_router(router_uuid):
        inner_ping(
            container_name=CONTROLLER_CONTAINER_ID,
            source_namespace=icmp_src_conf['ns'],
            target_ip=destination_ip, expected_result=1, ip_version=6
        )


def _get_port_ip_by_name(port_name):
    port_data = _get_networking_api_port_data(port_name)
    return (
        port_data['fixed_ips'][0].get('ip_address')
        if 'fixed_ips' in port_data else None
    )


def _get_networking_api_port_data(port_name):
    reply = requests.get(PROVIDER_URL + 'ports')
    return list(
        filter(
            lambda port: port.get('name') == port_name,
            reply.json().get('ports')
        )
    )[0]


def _get_routers():
    return requests.get(PROVIDER_URL + 'routers').json().get('routers')


def _update_network_mtu(network_uuid, mtu):
    payload = {
        'network': {'mtu': mtu}
    }
    reply = requests.put(
        PROVIDER_URL + 'networks/' + network_uuid, json=payload
    )
    if reply.status_code not in (200, 204):
        raise Exception(
            'Could not update network MTU for network: '.format(network_uuid)
        )


def _get_router_uuid(router_name):
    router_data = get_router_by_name(router_name)
    assert router_data
    return router_data['id']


@contextlib.contextmanager
def disable_router(router_uuid):
    _update_router(router_uuid, {'router': {'admin_state_up': False}})
    try:
        yield
    finally:
        _update_router(router_uuid, {'router': {'admin_state_up': True}})


def _update_router(router_uuid, router_payload):
    update_and_assert('routers', router_uuid, router_payload)
