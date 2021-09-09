#!/usr/bin/python2
# Copyright 2020-2021 Red Hat, Inc.
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
from __future__ import print_function

import os
import sys

import ovsdbapp.backend.ovs_idl.connection
from ovsdbapp.schema.ovn_southbound.impl_idl import OvnSbApiIdlImpl

OVN_SB_DB_DEFAULT = 'unix:/var/run/openvswitch/ovnsb_db.sock'
OVN_SB_DB_KEY = 'OVN_SB_DB'
OVN_SOUTHBOUND = 'OVN_Southbound'


class HostnameNotFoundError(ValueError):
    pass


def _usage():
    print('Usage: %s <hostname>' % (sys.argv[0],))


def _connect_sb(connection_string):
    ovsidl = ovsdbapp.backend.ovs_idl.connection.OvsdbIdl.from_server(
        connection_string, OVN_SOUTHBOUND
    )
    return OvnSbApiIdlImpl(
        ovsdbapp.backend.ovs_idl.connection.Connection(idl=ovsidl, timeout=100)
    )


def _remove_chassis_by_hostname(ovn_sb, hostname):
    chassis_list = _execute(ovn_sb.chassis_list())
    candidates = _chassis_by_hostname(chassis_list, hostname)

    if len(candidates) < 1:
        raise HostnameNotFoundError(hostname)

    for chassis in candidates:
        _execute(ovn_sb.chassis_del(chassis=chassis.name))


def _chassis_by_hostname(chassis_list, hostname):
    return [
        chassis for chassis in chassis_list if chassis.hostname == hostname
    ]


def _execute(command):
    return command.execute(check_error=True)


def _connection_string():
    if OVN_SB_DB_KEY in os.environ:
        return os.environ[OVN_SB_DB_KEY]
    return OVN_SB_DB_DEFAULT


if __name__ == "__main__":
    if len(sys.argv) != 2:
        _usage()
        sys.exit(1)

    hostname = sys.argv[1]

    ovn_sb = _connect_sb(_connection_string())
    _remove_chassis_by_hostname(ovn_sb, hostname)
