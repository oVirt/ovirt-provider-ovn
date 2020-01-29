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

import contextlib
import pytest

from lib.ansiblelib import get_playbook
from lib.api_lib import get_port_by_name
from lib.api_lib import update_and_assert
from lib.api_lib import SecurityGroup
from lib.api_lib import SecurityGroupRule
from lib.dockerlib import inner_ping
from lib.dockerlib import get_container_id_from_img_name

CONTROLLER_CONTAINER_ID = get_container_id_from_img_name(
        'tripleorocky/centos-binary-ovn-controller:current-tripleo-rdo'
)
PROVIDER_CONTAINER_ID = get_container_id_from_img_name(
            'quay.io/mdbarroso/ovirt_provider_ovn'
)

SAME_SUBNET = {
    'network_points': [
        {
            'name': 'lport1',
            'ip': '192.168.10.2',
            'mac': '00:00:00:11:11:11',
            'subnet_name': 'subnet1',
            'cidr': '192.168.10.0/24',
            'gateway_ip': '192.168.10.1',
            'network': 'net1',
            'ns': 'ns1'
        },
        {
            'name': 'lport2',
            'ip': '192.168.10.3',
            'mac': '00:00:00:22:22:22',
            'subnet_name': 'subnet1',
            'cidr': '192.168.10.0/24',
            'gateway_ip': '192.168.10.1',
            'network': 'net1',
            'ns': 'ns2'
        }
    ],
    'provider_container_id': PROVIDER_CONTAINER_ID,
    'controller_container_id': CONTROLLER_CONTAINER_ID
}


@pytest.fixture(scope='module')
def setup_dataplane():
    get_playbook('create_l2l3_scenario.yml', SAME_SUBNET).run(
        enable_idempotency_checker=False
    )
    try:
        yield
    finally:
        get_playbook('reset_scenario.yml', SAME_SUBNET).run(
            enable_idempotency_checker=False
        )


@pytest.fixture(scope='module')
def icmp_security_group_no_rules():
    with SecurityGroup('icmp_group', 'allow ICMP traffic') as icmp_group:
        yield icmp_group


@pytest.fixture(scope='module')
def icmp_security_group(icmp_security_group_no_rules):
    with SecurityGroupRule(
            icmp_security_group_no_rules.id, 'ingress',
            ether_type='IPv4', protocol='icmp'
    ):
        yield icmp_security_group_no_rules


@pytest.fixture(scope='module')
def limited_access_group_no_rules():
    with SecurityGroup(
            'remote_group', 'remote access requires \'icmp_group\' membership'
    ) as limited_access_group:
        yield limited_access_group


@pytest.fixture(scope='module')
def limited_access_group(limited_access_group_no_rules, icmp_security_group):
    with SecurityGroupRule(
        limited_access_group_no_rules.id, 'ingress',
        ether_type='IPv4', remote_group_id=icmp_security_group.id
    ):
        yield limited_access_group_no_rules


def test_port_security_default_group(setup_dataplane):
    icmp_client_conf = SAME_SUBNET['network_points'][0]
    icmp_server_conf = SAME_SUBNET['network_points'][1]
    icmp_client_port_id = _get_port_id(icmp_client_conf['name'])
    icmp_server_port_id = _get_port_id(icmp_server_conf['name'])

    with enable_port_security(icmp_client_port_id):
        with enable_port_security(icmp_server_port_id):
            inner_ping(
                CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
                icmp_server_conf['ip'], expected_result=0
            )


def test_port_security_without_default_group(setup_dataplane):
    icmp_client_conf = SAME_SUBNET['network_points'][0]
    icmp_server_conf = SAME_SUBNET['network_points'][1]
    icmp_client_port_id = _get_port_id(icmp_client_conf['name'])
    icmp_server_port_id = _get_port_id(icmp_server_conf['name'])

    with enable_port_security(icmp_server_port_id):
        with enable_port_security(icmp_client_port_id, security_groups=[]):
            inner_ping(
                CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
                icmp_server_conf['ip'], expected_result=1
            )


def test_created_group(setup_dataplane, icmp_security_group):
    icmp_client_conf = SAME_SUBNET['network_points'][0]
    icmp_server_conf = SAME_SUBNET['network_points'][1]
    icmp_client_port_id = _get_port_id(icmp_client_conf['name'])
    icmp_server_port_id = _get_port_id(icmp_server_conf['name'])

    configured_client = enable_port_security(
        icmp_client_port_id, security_groups=[icmp_security_group.id]
    )
    configured_server = enable_port_security(
        icmp_server_port_id,
        security_groups=[icmp_security_group.id]
    )

    with configured_client, configured_server:
        inner_ping(
            CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
            icmp_server_conf['ip'], expected_result=0
        )


def test_created_group_remote_group_id(
        setup_dataplane, icmp_security_group, limited_access_group
):
    icmp_client_conf = SAME_SUBNET['network_points'][0]
    icmp_server_conf = SAME_SUBNET['network_points'][1]
    icmp_client_port_id = _get_port_id(icmp_client_conf['name'])
    icmp_server_port_id = _get_port_id(icmp_server_conf['name'])

    configured_client_no_connectivity = enable_port_security(
        icmp_client_port_id, security_groups=[limited_access_group.id]
    )
    configured_server = enable_port_security(
        icmp_server_port_id,
        security_groups=[limited_access_group.id]
    )

    with configured_client_no_connectivity, configured_server:
        inner_ping(
            CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
            icmp_server_conf['ip'], expected_result=1
        )

        configured_client_connectivity = enable_port_security(
            icmp_client_port_id, security_groups=[icmp_security_group.id]
        )
        with configured_client_connectivity:
            inner_ping(
                CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
                icmp_server_conf['ip'], expected_result=0
            )


def _get_port_id(port_name):
    port = get_port_by_name(port_name)
    assert port
    return port.get('id')


@contextlib.contextmanager
def enable_port_security(port_uuid, security_groups=None):
    _update_port_security(
        port_uuid, port_security_value=True,
        security_groups=(
            security_groups if security_groups is not None
            else ['Default']
        )
    )
    try:
        yield
    finally:
        _update_port_security(
            port_uuid, port_security_value=False, security_groups=[]
        )


def _update_port_security(port_uuid, port_security_value, security_groups):
    update_port_data = {
        'port': {
            'port_security_enabled': port_security_value,
            'security_groups': security_groups
        }
    }
    update_and_assert('ports', port_uuid, update_port_data)
