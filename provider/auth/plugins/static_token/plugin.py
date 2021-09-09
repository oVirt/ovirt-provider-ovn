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
#
from __future__ import absolute_import

from auth.plugin import Plugin

MAGIC_TOKEN = '00000000000000000000000000000001'


class StaticTokenPlugin(Plugin):
    def create_token(self, user_at_domain, user_password):
        return MAGIC_TOKEN


class MagicTokenPlugin(StaticTokenPlugin):
    def validate_token(self, token):
        return token == MAGIC_TOKEN


class NoAuthPlugin(StaticTokenPlugin):
    def validate_token(self, token):
        return True
