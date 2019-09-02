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
from lib.api_lib import create_entity
from lib.api_lib import delete_entity
from lib.api_lib import get_port_by_name
from lib.api_lib import update_and_assert
from lib.dockerlib import inner_ping
from lib.dockerlib import get_container_id_from_img_name

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
    icmp_group = _create_security_group('icmp_group', 'allow ICMP traffic')
    try:
        yield icmp_group
    finally:
        delete_entity('security-groups', icmp_group['id'])


@pytest.fixture(scope='module')
def icmp_security_group(icmp_security_group_no_rules):
    allow_icmp_ipv4 = _create_security_group_rule(
        icmp_security_group_no_rules['id'], 'ingress',
        ether_type='IPv4', protocol='icmp'
    )
    try:
        yield icmp_security_group_no_rules
    finally:
        delete_entity('security-group-rules', allow_icmp_ipv4['id'])


@pytest.fixture(scope='module')
def limited_access_group_no_rules():
    limited_access_group = _create_security_group(
        'remote_group', 'remote access requires \'icmp_group\' membership'
    )
    try:
        yield limited_access_group
    finally:
        delete_entity('security-groups', limited_access_group['id'])


@pytest.fixture(scope='module')
def limited_access_group(limited_access_group_no_rules, icmp_security_group):
    allow_remote_icmp_group_rule = _create_security_group_rule(
        limited_access_group_no_rules['id'], 'ingress',
        ether_type='IPv4', remote_group_id=icmp_security_group['id']
    )
    try:
        yield limited_access_group_no_rules
    finally:
        delete_entity(
            'security-group-rules', allow_remote_icmp_group_rule['id']
        )


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

    with enable_port_security(icmp_client_port_id):
        with enable_port_security(icmp_server_port_id, security_groups=[]):
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
        icmp_client_port_id, security_groups=[icmp_security_group['id']]
    )
    configured_server = enable_port_security(
        icmp_server_port_id,
        security_groups=[icmp_security_group['id']]
    )

    with configured_client, configured_server:
        inner_ping(
            CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
            icmp_server_conf['ip'], expected_result=0
        )


@pytest.mark.xfail(reason='https://bugzilla.redhat.com/1744235', strict=True)
def test_created_group_remote_group_id(
        setup_dataplane, icmp_security_group, limited_access_group
):
    icmp_client_conf = SAME_SUBNET['network_points'][0]
    icmp_server_conf = SAME_SUBNET['network_points'][1]
    icmp_client_port_id = _get_port_id(icmp_client_conf['name'])
    icmp_server_port_id = _get_port_id(icmp_server_conf['name'])

    configured_client_no_connectivity = enable_port_security(
        icmp_client_port_id, security_groups=[limited_access_group['id']]
    )
    configured_server = enable_port_security(
        icmp_server_port_id,
        security_groups=[limited_access_group['id']]
    )

    with configured_client_no_connectivity, configured_server:
        inner_ping(
            CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
            icmp_server_conf['ip'], expected_result=1
        )

        configured_client_connectivity = enable_port_security(
            icmp_client_port_id, security_groups=[icmp_security_group['id']]
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


def _create_security_group(name, description):
    create_group_data = {
        'security_group': {
            'name': name,
            'description': description
        }
    }
    return create_entity('security-groups', create_group_data).get(
        'security_group'
    )


def _create_security_group_rule(
        security_group_id, direction, ether_type,
        protocol=None, remote_ip_prefix=None, remote_group_id=None
):
    create_rule_data = {
        'security_group_id': security_group_id,
        'direction': direction,
        'ethertype': ether_type
    }

    if remote_ip_prefix:
        create_rule_data['remote_ip_prefix'] = remote_ip_prefix
    if protocol:
        create_rule_data['protocol'] = protocol
    if remote_group_id:
        create_rule_data['remote_group_id'] = remote_group_id

    return create_entity(
        'security-group-rules', {'security_group_rule': create_rule_data}
    ).get('security_group_rule')
