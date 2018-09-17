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

from neutron.neutron_api_mappers import RestDataError

from ovndb.acls import acl_direction
from ovndb.acls import acl_ethertype
from ovndb.acls import acl_remote_ip_prefix
from ovndb.acls import handle_icmp_protocol
from ovndb.acls import handle_ports


def test_acl_direction():
    assert acl_direction('ingress', 'pg1') == 'inport == @pg1'
    assert acl_direction('egress', 'pg1') == 'outport == @pg1'
    with pytest.raises(KeyError):
        acl_direction('left2right', 'pg1')


def test_acl_ether_type():
    assert acl_ethertype('IPv4') == ('ip4', 'icmp4')
    assert acl_ethertype('IPv6') == ('ip6', 'icmp6')
    assert acl_ethertype('dumb-type') == (None, None)


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
    with pytest.raises(RestDataError):
        acl_remote_ip_prefix('bobloblaw', 'ingress', 'ip6')


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
