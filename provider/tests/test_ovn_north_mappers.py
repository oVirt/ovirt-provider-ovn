# Copyright 2016 Red Hat, Inc.
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

from uuid import UUID

from ovndb.ovn_north_mappers import SubnetMapper

from ovntestlib import assert_subnet_equal
from ovntestlib import OvnSubnetRow


NETWORK_ID1 = '1'
SUBNET_ID102 = UUID(int=102)
SUBNET_CIDR = '1.1.1.0/24'


class TestOvnNorthMappers(object):
    def test_subnet_to_rest_minimal(self):
        row = OvnSubnetRow(SUBNET_ID102, cidr=SUBNET_CIDR, external_ids={
            SubnetMapper.OVN_NETWORK_ID: NETWORK_ID1
        })
        subnet = SubnetMapper.row2rest(row)
        assert_subnet_equal(subnet, row)

    def test_subnet_to_rest_with_name(self):
        row = OvnSubnetRow(SUBNET_ID102, cidr=SUBNET_CIDR)
        subnet = SubnetMapper.row2rest(row)
        assert_subnet_equal(subnet, row)
