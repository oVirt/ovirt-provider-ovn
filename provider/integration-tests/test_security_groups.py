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
from lib.ansiblelib import get_playbook
from lib.dockerlib import inner_ping
from lib.dockerlib import get_container_id_from_img_name

CONTROLLER_CONTAINER_ID = get_container_id_from_img_name(
        'tripleomaster/centos-binary-ovn-controller:current-tripleo'
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


def test_port_security(setup_dataplane):
    icmp_client_conf = SAME_SUBNET['network_points'][0]
    icmp_server_conf = SAME_SUBNET['network_points'][1]

    inner_ping(
        CONTROLLER_CONTAINER_ID, icmp_client_conf['ns'],
        icmp_server_conf['ip'], expected_result=0
    )
