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

from ovndb.ovsdb_api import OvsDb

from ovntestlib import SCHEMA_FILE
from ovntestlib import REMOTE
from ovntestlib import TABLES
from ovntestlib import OvnTable


PARENT_TABLE = 'parent_table'

# Column which keeps the relation of to the children in parent row.
# Contains children objects
CHILDREN_ROW_NAME = 'children'


class ParentRow(object):
    def __init__(self, uuid, children=None):
        self.uuid = uuid
        self.children = children or []

    def verify(self, parent_children_column):
        pass


class ChildRow(object):
    def __init__(self, uuid):
        self.uuid = uuid


@mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
class TestOvsDbParentChildRelations(object):

    CHILD_1 = ChildRow(1)
    CHILD_2 = ChildRow(2)
    CHILD_3 = ChildRow(3)

    def setup_db(self, mock_idl):

        parent_rows = {
            10: ParentRow(10),
            11: ParentRow(11, [self.CHILD_1, self.CHILD_2])
        }

        mock_idl.Idl.return_value.tables = {PARENT_TABLE:
                                            OvnTable(parent_rows)}
        return parent_rows

    def test_move_child_between_parents(self, mock_idl):
        parent_rows = self.setup_db(mock_idl)

        target_parent_row = parent_rows[10]

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        ovsdb.update_child_parent(PARENT_TABLE, self.CHILD_1,
                                  target_parent_row, CHILDREN_ROW_NAME)

        assert len(parent_rows[10].children) == 1
        assert len(parent_rows[11].children) == 1

        assert parent_rows[10].children[0].uuid == 1
        assert parent_rows[11].children[0].uuid == 2

    def test_remove_child_from_parent(self, mock_idl):
        parent_rows = self.setup_db(mock_idl)
        target_parent_row = None
        removed_child = self.CHILD_1

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        ovsdb.update_child_parent(PARENT_TABLE, removed_child,
                                  target_parent_row, CHILDREN_ROW_NAME)

        assert len(parent_rows[11].children) == 1
        assert parent_rows[11].children[0].uuid == 2

    def test_add_new_child_to_empty_parent(self, mock_idl):
        parent_rows = self.setup_db(mock_idl)
        target_parent_row = parent_rows[10]
        new_child = self.CHILD_3

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        ovsdb.update_child_parent(PARENT_TABLE, new_child,
                                  target_parent_row, CHILDREN_ROW_NAME)

        assert len(parent_rows[10].children) == 1
        assert parent_rows[10].children[0].uuid == 3

    def test_add_new_child_to_populated_parent(self, mock_idl):
        parent_rows = self.setup_db(mock_idl)
        source_parent_row = parent_rows[10]
        target_parent_row = parent_rows[11]
        new_child = self.CHILD_3

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        ovsdb.update_child_parent(PARENT_TABLE, new_child,
                                  target_parent_row, CHILDREN_ROW_NAME)

        assert len(parent_rows[int(source_parent_row.uuid)].children) == 0
        assert len(parent_rows[int(target_parent_row.uuid)].children) == 3
