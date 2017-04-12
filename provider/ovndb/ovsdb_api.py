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
#

from __future__ import absolute_import

from functools import wraps

import abc
import logging
import os
import time

import six

import ovs.db.idl
import ovs.stream

import ovirt_provider_config as config


SSL_CONFIG_SECTION = 'SSL'
CONNECTION_TIMEOUT = 3
SLEEP_BETWEEN_CONNECTION_RETRY_TIME = 0.01
DEFAULT_KEY_FILE = '/etc/pki/ovirt-engine/keys/ovirt-provider-ovn.pem'
DEFAULT_CERT_FILE = '/etc/pki/ovirt-engine/certs/ovirt-provider-ovn.cer'
DEFAULT_CACERT_FILE = '/etc/pki/ovirt-engine/ca.pem'
PROTOCOL_SSL = 'ssl'


def _monotonic_time():
    return os.times()[4]


def _block_on_ovsdb_connect(f):
    @wraps(f)
    def block(connection):
        i = 0
        start = _monotonic_time()
        while (_monotonic_time() - start) < CONNECTION_TIMEOUT:
            logging.debug('Connection retry: %s', i)
            f(connection)
            if connection.has_ever_connected():
                logging.debug('Connected (number of retries: %s)', i)
                return
            time.sleep(SLEEP_BETWEEN_CONNECTION_RETRY_TIME)
            i += 1
        logging.debug('Failed to connect!')
        raise OvsDBConnectionFailed('Failed to connect!')
    return block


@six.add_metaclass(abc.ABCMeta)
class RestToDbRowMapper(object):

    @classmethod
    def validate(cls, f):
        @wraps(f)
        def wrapper(self, rest_data):
            cls.validate_rest_input(rest_data)
            return f(self, rest_data)
        return wrapper

    @staticmethod
    def rest2row(rest_data, row):
        raise NotImplementedError()

    @staticmethod
    def row2rest(row, rest_data):
        raise NotImplementedError()

    @staticmethod
    def validate_rest_input(rest_data):
        raise NotImplementedError()


class OvsDBConnectionFailed(Exception):
    pass


class OvsDBTransactionFailed(Exception):
    pass


class OvsDb(object):

    def __init__(self):
        self._ovsdb_connection = None

    def _is_ssl_connection(self, remote):
        protocol = remote.split(':')[0]
        return protocol == PROTOCOL_SSL

    def _setup_pki(self):
        key_file = config.get(
            SSL_CONFIG_SECTION,
            'key-file',
            DEFAULT_KEY_FILE
        )
        cert_file = config.get(
            SSL_CONFIG_SECTION,
            'cert-file',
            DEFAULT_CERT_FILE
        )
        cacert_file = config.get(
            SSL_CONFIG_SECTION,
            'cacert-file',
            DEFAULT_CACERT_FILE
        )

        ovs.stream.Stream.ssl_set_private_key_file(key_file)
        ovs.stream.Stream.ssl_set_certificate_file(cert_file)
        ovs.stream.Stream.ssl_set_ca_cert_file(cacert_file)

    def connect(self, tables, remote, schema_file):
        """
        Connect to a database defined by the passed socked
        Arguments:
        tables -- tables which will be accessed (needed to build the schema)
        table format:[['table_name', ['column name', ...]], ...]
        remote -- the url of the database
        schema_file -- schema file path of the database
        """

        logging.debug('Connecting to remote ovn database: {}'.format(remote))
        # TODO: there seems to be an OVS bug which causes transactions to fail
        # when a connection is reused for more than one transaction.
        # For this reason, the entire connection must be recreated for each
        # transaction. To be safe we also recreate the schema_helper every
        # time.
        # Some time we should change this code to be created only once in init
        schema_helper = ovs.db.idl.SchemaHelper(schema_file)
        for table in tables:
            schema_helper.register_columns(table[0], table[1])
        self._ovsdb_connection = ovs.db.idl.Idl(remote, schema_helper)
        if self._is_ssl_connection(remote):
            self._setup_pki()
        OvsDb._connect(self._ovsdb_connection)

    @staticmethod
    @_block_on_ovsdb_connect
    def _connect(connection):
        connection.run()

    def close(self):
        self._ovsdb_connection.close()

    def row_lookup(self, table, predicate):
        """
        Retrieves a row from `table` filtered by `predicate` function.
        Only retrieves the first encountered row.
        table -- the table from which to retrieve the row
        predicate -- function comparing the row to find a match, taking a row
        as a parameter
        """
        for row in six.itervalues(self._ovsdb_connection.tables[table].rows):
            if predicate(row):
                return row
        return None

    def row_lookup_by_id(self, table, id):
        return self.row_lookup(table, lambda row: str(row.uuid) == id)

    def commit(self, transaction):
        status = transaction.commit_block()
        if (status == ovs.db.idl.Transaction.ERROR or
                status == ovs.db.idl.Transaction.TRY_AGAIN):
            error_message = ('Transaction failed. Status: {}. Error message:'
                             ' {}'.format(status, transaction.get_error()))
            logging.error('Commit error: {}'.format(error_message))
            raise OvsDBTransactionFailed(error_message)

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def set_row(self, table, rest_values_dict, rest2db_mapper, transaction):
        """
        Update a row if one exists (matched by the 'id' key in values_dict
        and the uuid of a row) or create a new one if one does not exist.
        It returns the updated or added row.
        Note if a new row is created, the returned row is the temporary
        transaction row, which must be converted to real row after transaction
        commit.
        """
        received_id = rest_values_dict.get('id')
        row = (self.row_lookup_by_id(table, received_id)
               if received_id else None)
        if not row:
            row = transaction.insert(self._ovsdb_connection.tables[table])
        rest2db_mapper.rest2row(rest_values_dict, row)
        return row

    def update_existing_row_value(self, row, column, value, transaction):
        setattr(row, column, value)

    def get_real_row_from_inserted(self, table, row, transaction):
        if not self._is_new_row(row.uuid, transaction):
            return row
        new_row_uuid = transaction.get_insert_uuid(row.uuid)
        new_row = self.row_lookup(table, lambda row: row.uuid == new_row_uuid)
        return new_row

    def _is_new_row(self, uuid, transaction):
        """
        A row created by transaction.insert is only temporary.
        It's uuid is also only a temporary one.
        After transaction commit a new row is created. The new row's uuid
        can be obtained by transaction.get_insert_uuid(temporary_id).
        This method checks if a new row exists for a given temorary uuid.
        """
        return transaction.get_insert_uuid(uuid) is not None

    def create_transaction(self):
        return ovs.db.idl.Transaction(self._ovsdb_connection)

    def update_child_parent(self, parent_table, child_row,
                            new_parent_row, parent_children_column):
        """
        Updates the child-parent relation.
        OVN keeps row relation info as a list of children in the parent row.
        parent_table - table in which parent rows are stored
        child_row - row with ports being added/updated/deleted
        new_parent_row - new parent row, None if a child is deleted
        parent_children_column - the column in parent table used to store
        children
        """
        current_parent_row = self._get_current_parent(parent_table, child_row,
                                                      parent_children_column)

        if new_parent_row:
            self._attach_child_row_to_parent(new_parent_row, child_row,
                                             parent_children_column)
        if current_parent_row:
            self._detach_child_row_from_parent(current_parent_row, child_row,
                                               parent_children_column)

    def _get_current_parent(self, parent_table, child_row,
                            parent_children_column):
        for parent_row in six.itervalues(
                self._ovsdb_connection.tables[parent_table].rows):
            if OvsDb._is_current_parent(parent_row, child_row,
                                        parent_children_column):
                return parent_row
        return None

    @staticmethod
    def _is_current_parent(parent_row, child_row, parent_children_column):
        for parents_child_row in getattr(parent_row, parent_children_column):
            if parents_child_row.uuid == child_row.uuid:
                return True
        return False

    def _attach_child_row_to_parent(self, parent_row, child_row,
                                    parent_children_column):
        # TODO: replace with the following after moving to OVS 2.6.1
        # parent_row.addvalue(parent_children_column, child_row)
        new_children = []
        new_children.append(child_row)
        new_children.extend(getattr(parent_row, parent_children_column))
        parent_row.verify(parent_children_column)
        setattr(parent_row, parent_children_column, new_children)

    def _detach_child_row_from_parent(self, parent_row, child_row,
                                      parent_children_column):
        # TODO: replace with the following after moving to OVS 2.6.1
        # parent_row.delvalue(parent_children_column, child_row)
        new_children = [p for p in getattr(parent_row, parent_children_column)
                        if p.uuid != child_row.uuid]
        parent_row.verify(parent_children_column)
        setattr(parent_row, parent_children_column, new_children)
