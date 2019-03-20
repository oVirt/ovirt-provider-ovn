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


import requests
import pytest

from lib.ansiblelib import get_playbook
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

PROVIDER_URL = 'http://localhost:9696/v2.0/'


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


def test_single_subnet(setup_dataplane):
    icmp_src_conf = SAME_SUBNET['network_points'][0]
    icmp_dst_conf = SAME_SUBNET['network_points'][1]

    destination_ip = _get_port_ip_by_name(icmp_dst_conf.get('name'))
    assert destination_ip

    inner_ping(
        container_name=CONTROLLER_CONTAINER_ID,
        source_namespace=icmp_src_conf['ns'],
        target_ip=destination_ip, expected_result=0, ip_version=6
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
