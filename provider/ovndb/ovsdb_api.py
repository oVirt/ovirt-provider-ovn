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

import logging
import time

import six

import ovs.db.idl

SLEEP_BETWEEN_CONNECTION_RETRY_TIME = 0.1


def _block_on_ovsdb_connect(f):
    @wraps(f)
    def block(connection):
        CONNECT_RETRIES = 30

        for n in range(CONNECT_RETRIES):
            f(connection)
            if connection.has_ever_connected():
                logging.debug('Connected (number of retries: {})'.format(n))
                return
            time.sleep(SLEEP_BETWEEN_CONNECTION_RETRY_TIME)
        logging.debug('Failed to connect!')
        raise OvsDBConnectionFailed('Failed to connect!')
    return block


class OvsDBConnectionFailed(Exception):
    pass


class OvsDb(object):

    def __init__(self):
        self._ovsdb_connection = None

    def connect(self, tables, remote, schema_file):
        """ Connect to a database defined by the passed socked
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
        OvsDb._connect(self._ovsdb_connection)

    @staticmethod
    @_block_on_ovsdb_connect
    def _connect(connection):
        connection.run()

    def close(self):
        self._ovsdb_connection.close()
