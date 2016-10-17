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

import mock
import pytest

from ovndb.ovsdb_api import OvsDBConnectionFailed
from ovndb.ovsdb_api import OvsDb


TABLES = [['table0', ['column0', 'column1']]]
REMOTE = 'address://url'
SCHEMA_FILE = '/path/to/schema'


@mock.patch('ovndb.ovsdb_api.time.sleep', lambda x: None)
@mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
class TestConnection:

    def test_block_on_connect_success(self, mock_idl):
        mock_idl.Idl.return_value.has_ever_connected.return_value = True

        ovs_db = OvsDb()
        ovs_db.connect(TABLES, REMOTE, SCHEMA_FILE)

        mock_idl.Idl.assert_called_once_with(
            REMOTE, mock_idl.SchemaHelper.return_value)
        assert mock_idl.Idl.return_value.run.call_count == 1
        assert mock_idl.Idl.return_value.has_ever_connected.call_count == 1

    def test_block_on_connect_success_on_3_retry(self, mock_idl):
        ret_values = [False, False, True]
        mock_idl.Idl.return_value.has_ever_connected.side_effect = ret_values

        ovs_db = OvsDb()
        ovs_db.connect(TABLES, REMOTE, SCHEMA_FILE)

        mock_idl.Idl.assert_called_once_with(
            REMOTE, mock_idl.SchemaHelper.return_value)
        assert mock_idl.Idl.return_value.run.call_count == 3
        assert mock_idl.Idl.return_value.has_ever_connected.call_count == 3

    def test_block_on_connect_fails(self, mock_idl):
        mock_idl.Idl.return_value.has_ever_connected.return_value = False
        with pytest.raises(OvsDBConnectionFailed,
                           message='Failed to connect!'):
            ovs_db = OvsDb()
            ovs_db.connect(TABLES, REMOTE, SCHEMA_FILE)
