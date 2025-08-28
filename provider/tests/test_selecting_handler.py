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
from __future__ import absolute_import

import pytest
import urllib.parse

from handlers.selecting_handler import RESPONSE_VALUE_KEY
from handlers.selecting_handler import RESPONSE_VALUE_PARAMETER
from handlers.selecting_handler import rest
from handlers.selecting_handler import SelectingHandler


class TestSelectingHandler(object):
    def test_assign_responses(self):
        response_handlers = {}

        @rest('TEST1', 'test1', response_handlers)
        def decorated_method1():
            return 1

        @rest('TEST2', 'test2/test3', response_handlers)
        def decorated_method2():
            return 2

        @rest('TEST3', 'test4/*/test5/*', response_handlers)
        def decorated_method3():
            return 3

        @rest('TEST3', 'test4/test6/test5/*', response_handlers)
        def decorated_method4():
            return 4

        @rest('TEST3', 'test4/{id1}/test5/{id2}', response_handlers)
        def decorated_method5():
            return 5

        assert response_handlers['test1'][RESPONSE_VALUE_KEY]['TEST1']() == 1
        assert (
            response_handlers['test2']['test3'][RESPONSE_VALUE_KEY]['TEST2']()
            == 2
        )
        assert (
            response_handlers['test4']['*']['test5']['*'][RESPONSE_VALUE_KEY][
                'TEST3'
            ]()
            == 3
        )
        assert (
            response_handlers['test4']['test6']['test5']['*'][
                RESPONSE_VALUE_KEY
            ]['TEST3']()
            == 4
        )
        assert (
            response_handlers['test4'][RESPONSE_VALUE_PARAMETER]['id1'][
                'test5'
            ][RESPONSE_VALUE_PARAMETER]['id2'][RESPONSE_VALUE_KEY]['TEST3']()
            == 5
        )

        url = 'http://localhost:8080/v2.0/test4/11/test5/12'
        elements = list(
            filter(None, urllib.parse.urlparse(url).path.split('/'))
        )[1:]
        handler, params = SelectingHandler.get_response_handler(
            response_handlers, 'TEST3', elements
        )
        assert handler() == 5
        assert params['id1'] == '11'
        assert params['id2'] == '12'

    def test_duplicate_parameter_name(self):
        with pytest.raises(AssertionError):
            self._test_parameters('test1/{id1}/test2/{id1}', {})

    def test_not_unique_parameter_name(self):
        responses = {}
        self._test_parameters('test1/{id1}/test2/{id2}', responses)
        with pytest.raises(AssertionError):
            self._test_parameters('test1/{id3}/test2/{id2}', responses)

    def test_duplicate_path(self):
        responses = {}
        self._test_parameters('test1/{id1}/test2/{id2}', responses)
        with pytest.raises(AssertionError):
            self._test_parameters('test1/{id1}/test2/{id2}', responses)

    def _test_parameters(self, path, responses):
        assign_response = rest('GET', path, responses)
        assign_response(lambda: None)
