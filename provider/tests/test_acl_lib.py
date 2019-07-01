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

from __future__ import absolute_import

import pytest
import uuid

from ovndb.acls import acl_direction
from ovndb.acls import get_acl_protocol_info
from ovndb.acls import acl_remote_ip_prefix
from ovndb.acls import create_acl_match
from ovndb.acls import create_acl_match_string
from ovndb.acls import handle_icmp_protocol
from ovndb.acls import handle_ports
from ovndb.acls import get_remote_group_id_match


def test_acl_direction():
    assert acl_direction('ingress', 'pg1') == 'outport == @pg1'
    assert acl_direction('egress', 'pg1') == 'inport == @pg1'
    with pytest.raises(KeyError):
        acl_direction('left2right', 'pg1')


def test_acl_ether_type():
    assert get_acl_protocol_info('IPv4') == ('ip4', 'icmp4')
    assert get_acl_protocol_info('IPv6') == ('ip6', 'icmp6')
    assert get_acl_protocol_info('dumb-type') == (None, None)


def test_ip_prefix():
    assert acl_remote_ip_prefix('192.168.2.0/24', 'ingress', 'ip4') == (
        'ip4.src == 192.168.2.0/24'
    )
    assert acl_remote_ip_prefix('192.168.2.0/24', 'egress', 'ip4') == (
        'ip4.dst == 192.168.2.0/24'
    )
    assert acl_remote_ip_prefix('192.168.2.0/24', 'ingress', 'ip6') == (
        'ip6.src == 192.168.2.0/24'
    )
    assert acl_remote_ip_prefix('192.168.2.0/24', 'egress', 'ip6') == (
        'ip6.dst == 192.168.2.0/24'
    )


def test_acl_icmp_handler():
    assert handle_icmp_protocol(
        'icmp', 0, None
    ) == ['icmp', 'icmp.type == 0']

    assert handle_icmp_protocol('icmp', 3, 4) == [
        'icmp', 'icmp.type == 3', 'icmp.code == 4'
    ]


def test_acl_port_matches():
    assert handle_ports('tcp', 80, 80) == ['tcp', 'tcp.dst == 80']
    assert handle_ports('tcp', 80, None) == ['tcp', 'tcp.dst >= 80']
    assert handle_ports('tcp', None, None) == ['tcp']
    assert handle_ports('tcp', 80, 90) == [
        'tcp', 'tcp.dst >= 80', 'tcp.dst <= 90'
    ]


def test_create_acl_match():
    pg_id = uuid.UUID(int=100)
    assert create_acl_match(
        'ingress', 'IPv4', None, None, None, 'tcp', pg_id
    ) == ['outport == @00000000-0000-0000-0000-000000000064', 'ip4', 'tcp']
    assert create_acl_match(
        'ingress', 'IPv4', None, 5000, 5299, 'tcp', pg_id
    ) == [
        'outport == @00000000-0000-0000-0000-000000000064',
        'ip4', 'tcp', 'tcp.dst >= 5000', 'tcp.dst <= 5299'
    ]
    assert create_acl_match(
        'ingress', 'IPv4', '192.168.80.0/24', 5000, 5299, 'tcp', pg_id
    ) == [
        'outport == @00000000-0000-0000-0000-000000000064',
        'ip4', 'ip4.src == 192.168.80.0/24', 'tcp', 'tcp.dst >= 5000',
        'tcp.dst <= 5299'
    ]
    assert sorted(
        create_acl_match(
            'ingress', 'IPv4', '192.168.80.0/24', 5000, 5299, 'tcp', pg_id,
            remote_group_name='Default'
        )
    ) == sorted(
        [
            'outport == @00000000-0000-0000-0000-000000000064',
            'ip4', 'ip4.src == 192.168.80.0/24', 'tcp', 'tcp.dst >= 5000',
            'tcp.dst <= 5299', 'ip4.src == $Default_ip4'
        ]
    )


def test_create_acl_match_output():
    pg_id = uuid.UUID(int=100)
    assert create_acl_match_string(
        create_acl_match(
            'ingress', 'IPv4', None, None, None, 'tcp', pg_id
        )
    ) == 'outport == @00000000-0000-0000-0000-000000000064 && ip4 && tcp'
    assert create_acl_match_string(
        create_acl_match(
            'ingress', 'IPv4', None, 5000, 5299, 'tcp', pg_id
        )
    ) == (
        'outport == @00000000-0000-0000-0000-000000000064 && ip4 && '
        'tcp && tcp.dst >= 5000 && tcp.dst <= 5299'
    )
    assert create_acl_match_string(
        create_acl_match(
            'ingress', 'IPv4', '192.168.80.0/24', 5000, 5299, 'tcp', pg_id
        )
    ) == (
        'outport == @00000000-0000-0000-0000-000000000064 && ip4 && '
        'ip4.src == 192.168.80.0/24 && tcp && tcp.dst >= 5000 && '
        'tcp.dst <= 5299'
    )
    assert create_acl_match_string(
        create_acl_match(
            'ingress', 'IPv4', '192.168.80.0/24', 5000, 5299, 'tcp', pg_id,
            remote_group_name='Default'
        )
    ) == (
        'outport == @00000000-0000-0000-0000-000000000064 && ip4 && '
        'ip4.src == 192.168.80.0/24 && ip4.src == $Default_ip4 && tcp && '
        'tcp.dst >= 5000 && tcp.dst <= 5299'
    )


def test_remote_group_id_output():
    remote_group_name = 'Default'
    assert get_remote_group_id_match(
        remote_group_name, 'ip4', 'ingress'
    ) == 'ip4.src == $Default_ip4'
    assert get_remote_group_id_match(
        remote_group_name, 'ip6', 'ingress'
    ) == 'ip6.src == $Default_ip6'
    assert get_remote_group_id_match(
        remote_group_name, 'ip4', 'egress'
    ) == 'ip4.dst == $Default_ip4'
    assert get_remote_group_id_match(
        remote_group_name, 'ip6', 'egress'
    ) == 'ip6.dst == $Default_ip6'
    assert get_remote_group_id_match(None, 'ip4', 'ingress') == ''
