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


TABLES = [['table0', ['column0', 'column1']]]
REMOTE = 'address://url'
SCHEMA_FILE = '/path/to/schema'


class OvnTable(object):
    def __init__(self, rows):
        self.rows = rows


class OvnNetworkRow(object):
    def __init__(self, uuid, name=None, other_config=None, ports=None):
        self.uuid = uuid
        self.name = name
        self.other_config = other_config or {}
        self.ports = ports or []
