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

from collections import namedtuple
import ovndb.ip as ip_utils

Lsp = namedtuple('Lsp', ['addresses', 'dynamic_addresses'])
Lrp = namedtuple('Lrp', ['networks'])

ADDRESS_DATA = [
    (None, 'unknown', None),
    (None, '80:fa:5b:06:72:b7', None),
    ('10.0.0.4', '80:fa:5b:06:72:b7 10.0.0.4 20.0.0.4', None),
    ('fdaa:15f2:72cf:0:f816:3eff:fe20:3f41',
     '80:fa:5b:06:72:b7 fdaa:15f2:72cf:0:f816:3eff:fe20:3f41', None),
    ('10.0.0.4',
     '80:fa:5b:06:72:b7 10.0.0.4 fdaa:15f2:72cf:0:f816:3eff:fe20:3f41',
     None),
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
        lrp=Lrp(networks=['10.0.0.1/24'])
    )


def test_get_port_ip_empty():
    assert ip_utils.get_port_ip(
        lsp=Lsp(addresses=[], dynamic_addresses=None)
    ) is None
