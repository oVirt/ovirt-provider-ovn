# Copyright 2017 Red Hat, Inc.
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

from handlers.selecting_handler import rest


class TestSelectingHandler(object):
    def test_assign_responses(self):
        response_handlers = {}

        @rest('TEST1', 'test1', response_handlers)
        def decorated_method1():
            return 1

        @rest('TEST2', 'test2', response_handlers)
        def decorated_method2():
            return 2

        assert response_handlers['TEST1']['test1']() == 1
        assert response_handlers['TEST2']['test2']() == 2
