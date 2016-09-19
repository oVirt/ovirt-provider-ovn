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
from ovndb.ovsdb_api import RestToDbRowMapper
from ovntestlib import SCHEMA_FILE
from ovntestlib import REMOTE
from ovntestlib import TABLES
from ovntestlib import OvnNetworkRow
from ovntestlib import OvnTable

TABLE_NAME = 'table_name'


class ConcreteRestToDbRowMapper(RestToDbRowMapper):
    @staticmethod
    def rest2row(rest_data, row):
        if 'name' in rest_data:
            row.name = rest_data['name']


@mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
class TestOvsDb(object):

    def setup_db(self, mock_idl):
        db_rows = {0: OvnNetworkRow(0, 'name0'),
                   1: OvnNetworkRow(1, 'name1'),
                   2: OvnNetworkRow(2, 'name2')
                   }
        mock_idl.Idl.return_value.tables = {TABLE_NAME: OvnTable(db_rows)}

    def test_fetch_row_by_value(self, mock_idl):
        self.setup_db(mock_idl)

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        row = ovsdb.row_lookup(TABLE_NAME, lambda row: row.uuid == 1)

        assert row.uuid == 1
        assert row.name == 'name1'

    def test_add_new_row(self, mock_idl):
        self.setup_db(mock_idl)
        mock_transaction = mock_idl.Transaction.return_value
        mock_transaction.insert.return_value = OvnNetworkRow(7)

        new_rest_data = {'name': 'new_name_value'}

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        transaction = ovsdb.create_transaction()

        added_row = ovsdb.set_row(TABLE_NAME, new_rest_data,
                                  ConcreteRestToDbRowMapper, transaction)

        mock_transaction.insert.assert_called_once_with(mock.ANY)
        assert added_row.uuid == 7

    def test_modify_existing_row(self, mock_idl):
        self.setup_db(mock_idl)

        updated_entity = {'id': '1', 'name': 'updated_name_value'}

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        transaction = ovsdb.create_transaction()
        modified_row = ovsdb.set_row(TABLE_NAME, updated_entity,
                                     ConcreteRestToDbRowMapper,
                                     transaction)

        assert modified_row.uuid == 1
        assert modified_row.name == 'updated_name_value'
        assert mock_idl.Transaction.return_value.insert.call_count == 0

    def test_update_existing_row_value(self, mock_idl):
        self.setup_db(mock_idl)

        row_to_update = OvnNetworkRow(1)

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        transaction = ovsdb.create_transaction()
        ovsdb.update_existing_row_value(row_to_update, 'name', 'updated_value',
                                        transaction)
        ovsdb.commit(transaction)

        assert row_to_update.name == 'updated_value'
        transaction = mock_idl.Transaction
        transaction.assert_called_once_with(mock.ANY)
        transaction.return_value.commit_block.assert_called_once_with()

    def test_get_real_row_when_new_row_was_created_by_transaction(self,
                                                                  mock_idl):
        self.setup_db(mock_idl)
        mock_idl.Transaction.return_value.get_insert_uuid.return_value = 1

        new_rest_data = {'name': 'new_name_value'}

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        transaction = ovsdb.create_transaction()

        added_row = ovsdb.set_row(TABLE_NAME, new_rest_data,
                                  ConcreteRestToDbRowMapper, transaction)
        transaction.commit()
        real_row = ovsdb.get_real_row_from_inserted(TABLE_NAME, added_row,
                                                    transaction)
        assert real_row.uuid == 1

    def test_get_real_row_when_no_row_was_created(self, mock_idl):
        self.setup_db(mock_idl)
        mock_idl.Transaction.return_value.get_insert_uuid.return_value = None

        existing_row = OvnNetworkRow(0)

        ovsdb = OvsDb()
        ovsdb.connect(TABLES, REMOTE, SCHEMA_FILE)
        transaction = ovsdb.create_transaction()

        real_row = ovsdb.get_real_row_from_inserted(TABLE_NAME, existing_row,
                                                    transaction)
        assert real_row == existing_row
