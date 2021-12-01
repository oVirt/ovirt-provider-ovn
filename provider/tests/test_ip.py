# Copyright 2018-2021 Red Hat, Inc.
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

from collections import namedtuple
import neutron.ip as ip_utils

Lsp = namedtuple('Lsp', ['addresses', 'dynamic_addresses'])
Lrp = namedtuple('Lrp', ['networks'])

ADDRESS_DATA = [
    (None, 'unknown', None),
    (None, '80:fa:5b:06:72:b7', None),
    ('10.0.0.4', '80:fa:5b:06:72:b7 10.0.0.4 20.0.0.4', None),
    (
        'fdaa:15f2:72cf:0:f816:3eff:fe20:3f41',
        '80:fa:5b:06:72:b7 fdaa:15f2:72cf:0:f816:3eff:fe20:3f41',
        None,
    ),
    (
        '10.0.0.4',
        '80:fa:5b:06:72:b7 10.0.0.4 fdaa:15f2:72cf:0:f816:3eff:fe20:3f41',
        None,
    ),
    ('10.0.0.4', 'dynamic', '80:fa:5b:06:72:b7 10.0.0.4'),
    ('10.0.0.4', '80:fa:5b:06:72:b7 dynamic', '80:fa:5b:06:72:b7 10.0.0.4'),
    (None, '80:fa:5b:06:72:b7 unknown', None),
]


def test_get_port_ip():
    for expected, address, dynamic in ADDRESS_DATA:
        assert expected == ip_utils.get_port_ip(Lsp([address], [dynamic]))


def test_get_port_ip_router():
    assert '10.0.0.1' == ip_utils.get_port_ip(
        lsp=Lsp(addresses=['router'], dynamic_addresses=None),
        lrp=Lrp(networks=['10.0.0.1/24']),
    )


def test_get_port_ip_empty():
    assert (
        ip_utils.get_port_ip(lsp=Lsp(addresses=[], dynamic_addresses=None))
        is None
    )


def test_ip_in_cidr():
    assert ip_utils.ip_in_cidr('192.168.0.1', '192.168.0.0/24')
    assert ip_utils.ip_in_cidr('192.168.0.1', '192.168.0.0/16')
    assert ip_utils.ip_in_cidr('192.168.0.1', '0.0.0.0/0')
    assert ip_utils.ip_in_cidr('192.168.0.1', '192.168.0.1/32')
    assert not ip_utils.ip_in_cidr('192.168.0.1', '192.168.1.0/24')


class Route(object):
    def __init__(self, ip_prefix, nexhop):
        self.ip_prefix = ip_prefix
        self.nexthop = nexhop


def test_diff_routes():
    rest_routes = [
        {'destination': '1.1.1.0/24', 'nexthop': '1.1.1.1'},
        {'destination': '1.1.2.0/24', 'nexthop': '1.1.2.1'},
        {'destination': '1.1.3.0/24', 'nexthop': '1.1.3.1'},
    ]

    db_routes = [
        Route('1.1.2.0/24', '1.1.2.100'),
        Route('1.1.3.0/24', '1.1.3.1'),
        Route('1.1.4.0/24', '1.1.4.1'),
    ]

    added, deleted = ip_utils.diff_routes(rest_routes, db_routes)
    assert len(added) == 2
    assert len(deleted) == 2
    assert rest_routes[0]['destination'] in added
    assert rest_routes[1]['destination'] in added
    assert db_routes[0].ip_prefix in deleted
    assert db_routes[2].ip_prefix in deleted


def test_diff_routes_all_empty():
    assert ({}, {}) == ip_utils.diff_routes(None, None)
    assert ({}, {}) == ip_utils.diff_routes([], [])


def test_diff_routes_only_new():
    route = {'destination': '1.1.1.0/24', 'nexthop': '1.1.1.1'}
    assert (
        {route['destination']: route['nexthop']},
        {},
    ) == ip_utils.diff_routes([route], [])


def test_diff_routes_only_db():
    route = Route('1.1.2.0/24', '1.1.2.100')
    assert ({}, {route.ip_prefix: route.nexthop}) == ip_utils.diff_routes(
        None, [route]
    )


def test_diff_routes_ipv6():
    rest_routes = [
        {'destination': 'fd:10::/64', 'nexthop': 'fd:10::1'},
    ]

    db_routes = [
        Route('fd:20::/64', 'fd:20::1'),
    ]

    added, deleted = ip_utils.diff_routes(rest_routes, db_routes)
    assert len(added) == 1
    assert len(deleted) == 1
    assert rest_routes[0]['destination'] in added
    assert db_routes[0].ip_prefix in deleted
