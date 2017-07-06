# Copyright 2017 Red Hat, Inc.
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
import mock

from ovndb.ovn_north import OvnNorth

from ovntestlib import OvnNetworkRow


@mock.patch('ovsdbapp.backend.ovs_idl.connection', autospec=False)
class TestOvnNorth(object):

    NETWORK_ID10 = UUID(int=10)
    NETWORK_ID11 = UUID(int=11)
    NETWORK_NAME10 = 'name10'
    NETWORK_NAME11 = 'name11'

    networks = [
        OvnNetworkRow(NETWORK_ID10, NETWORK_NAME10),
        OvnNetworkRow(NETWORK_ID11, NETWORK_NAME11),
    ]

    @mock.patch(
        'ovsdbapp.schema.ovn_northbound.commands.LsListCommand',
        autospec=False
    )
    def test_get_networks(self, mock_ls_list, mock_connection):
        mock_ls_list.return_value.execute.return_value = TestOvnNorth.networks

        ovn_north = OvnNorth()
        result = ovn_north.list_networks()

        assert len(result) == 2
        assert result[0]['id'] == str(TestOvnNorth.NETWORK_ID10)
        assert result[0]['name'] == TestOvnNorth.NETWORK_NAME10
        assert mock_ls_list.call_count == 1
        assert mock_ls_list.return_value.execute.call_count == 1
