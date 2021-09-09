# Copyright 2017-2021 Red Hat, Inc.
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


class DbSetCommand(object):
    def __init__(self, idl, table, entity_id):
        self.idl = idl
        self.table = table
        self.entity_id = entity_id
        self.values = list()

    def execute(self):
        update_command = self.build_command()
        if update_command:
            update_command.execute()

    def build_command(self):
        if not self.values:
            return
        return self.idl.db_set(self.table, self.entity_id, *self.values)

    def add(self, column, value, add_condition=True):
        if add_condition:
            self.values.append((column, value))
        return self
