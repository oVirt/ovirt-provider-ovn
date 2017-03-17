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

import json
from mock import MagicMock
import mock

from handlers.keystone import TokenHandler

from handlers.selecting_handler import rest

REST_RESPONSE_POST = 'REST_RESPONSE_POST'

response_handlers = {}


@rest('POST', 'tokens', response_handlers)
def post_handler(content, id):
    return {'value': REST_RESPONSE_POST + content['key']}


@mock.patch('handlers.keystone.TokenHandler._run_server', lambda *args: None)
@mock.patch('handlers.keystone_responses._responses', response_handlers)
class TestKeystoneHandler(object):

    @mock.patch('handlers.keystone.TokenHandler.end_headers')
    @mock.patch('handlers.keystone.TokenHandler.send_header')
    @mock.patch('handlers.keystone.TokenHandler.send_response', autospec=True)
    def test_handle_post_request(self, mock_send_response, mock_send_header,
                                 mock_end_headers):

        handler = TokenHandler(None, None, None)
        handler.wfile = MagicMock()
        handler.rfile = MagicMock()
        input_data = json.dumps({'key': 'value'})
        handler.rfile.read.return_value = input_data
        handler.headers = {'Content-Length': len(input_data)}

        handler.path = '/v2.0/tokens'

        handler.do_POST()

        mock_send_response.assert_called_once_with(handler, 200)
        handler.wfile.write.assert_called_once_with(json.dumps(
            {'value': REST_RESPONSE_POST + 'value'}))
