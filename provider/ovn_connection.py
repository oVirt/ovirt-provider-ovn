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

import contextlib

import ovs.stream
import ovsdbapp.backend.ovs_idl.connection
from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound
from ovsdbapp.backend.ovs_idl.transaction import Transaction
from ovsdbapp.schema.ovn_northbound.impl_idl import OvnNbApiIdlImpl

import constants as ovnconst

from handlers.base_handler import BadRequestError
from handlers.base_handler import ElementNotFoundError

from ovirt_provider_config_common import is_ovn_remote_ssl
from ovirt_provider_config_common import ovn_remote
from ovirt_provider_config_common import ssl_key_file
from ovirt_provider_config_common import ssl_cacert_file
from ovirt_provider_config_common import ssl_cert_file

_api_impl = None


def connect():
    global _api_impl
    if _api_impl:
        return _api_impl
    _api_impl = _create_new_connection()
    return _api_impl


def _create_new_connection():
    configure_ssl_connection()
    ovsidl = ovsdbapp.backend.ovs_idl.connection.OvsdbIdl.from_server(
        ovn_remote(), ovnconst.OVN_NORTHBOUND
    )
    return OvnNbApiIdlImpl(
        ovsdbapp.backend.ovs_idl.connection.Connection(idl=ovsidl, timeout=100)
    )


def configure_ssl_connection():
    if is_ovn_remote_ssl():
        ovs.stream.Stream.ssl_set_private_key_file(ssl_key_file())
        ovs.stream.Stream.ssl_set_certificate_file(ssl_cert_file())
        ovs.stream.Stream.ssl_set_ca_cert_file(ssl_cacert_file())


def execute(command):
    try:
        return command.execute(check_error=True)
    except (ValueError, TypeError) as e:
        raise BadRequestError(e)
    except RowNotFound as e:
        raise ElementNotFoundError(e)


class OvnTransactionManager(OvnNbApiIdlImpl):
    def __init__(self, connection):
        super(OvnTransactionManager, self).__init__(connection)
        self._tx = None

    def create_transaction(self, check_error=False, log_errors=True, **kwargs):
        tx = Transaction(
            self,
            self.ovsdb_connection,
            self.ovsdb_connection.timeout,
            check_error,
            log_errors,
        )
        self._tx = tx
        return tx

    @contextlib.contextmanager
    def transaction(self, check_error=True, log_errors=False, **kwargs):
        if not self._tx:
            self._tx = self.create_transaction(check_error, log_errors)
        try:
            yield self._tx
        finally:
            self._tx.commit()
            self._tx = None
