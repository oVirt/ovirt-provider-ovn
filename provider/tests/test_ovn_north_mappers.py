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

from mock import Mock
from uuid import UUID

from ovndb.ovn_north_mappers import SubnetMapper


NETWORK_ID1 = UUID(int=1)
SUBNET_ID102 = UUID(int=102)
SUBNET_NAME1 = 'subnet_name1'
CIDR = '1.1.1.0/24'


class TestOvnNorthMappers(object):
    def test_subnet_to_rest_minimal(self):
        row = self._minimal_subnet_row()

        subnet = SubnetMapper.row2rest(row)

        self._check_subnet_to_rest(
            subnet, SUBNET_ID102, CIDR, NETWORK_ID1, None)

    def test_subnet_to_rest_with_name(self):
        row = self._minimal_subnet_row()
        row.external_ids[SubnetMapper.OVN_NAME] = SUBNET_NAME1

        subnet = SubnetMapper.row2rest(row)

        self._check_subnet_to_rest(
            subnet, SUBNET_ID102, CIDR, NETWORK_ID1, SUBNET_NAME1)

    def _minimal_subnet_row(self):
        row = Mock()
        row.uuid = SUBNET_ID102
        row.external_ids = {
            SubnetMapper.OVN_NETWORK_ID: str(NETWORK_ID1,)
        }
        row.options = {}
        row.cidr = CIDR
        return row

    def _check_subnet_to_rest(
        self, rest, id, cidr, network_id, name
    ):
        assert rest[SubnetMapper.REST_SUBNET_ID] == str(id)
        assert rest[SubnetMapper.REST_SUBNET_NETWORK_ID] == str(network_id)
        assert rest[SubnetMapper.REST_SUBNET_CIDR] == CIDR

        if name:
            assert rest[SubnetMapper.REST_SUBNET_NAME] == name
        else:
            assert SubnetMapper.REST_SUBNET_NAME not in rest
