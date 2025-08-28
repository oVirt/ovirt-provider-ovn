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

import json
from unittest.mock import MagicMock, ANY
import unittest.mock as mock

from handlers.base_handler import BadRequestError
from handlers.base_handler import Response
from handlers.base_handler import Timeout
from handlers.keystone import TokenHandler

from handlers.selecting_handler import rest

REST_RESPONSE_POST = 'REST_RESPONSE_POST'
EMPTY = 'EMPTY'
CLIENT_ADDRESS = ('127.0.0.1', 41736)

response_handlers = {}


@rest('POST', 'tokens', response_handlers)
def tokens_handler(content, id):
    return Response({'value': REST_RESPONSE_POST + json.loads(content)['key']})


@rest('POST', 'empty', response_handlers)
def empty_handler(content, id):
    return Response({'value': EMPTY})


@rest(
    'POST', 'domains/{domain_id}/{config}/{group}/{option}', response_handlers
)
def domains_handler(content, params):
    return Response(
        {
            'value': '{domain_id}/{config}/{group}/{option}{key}'.format(
                domain_id=params['domain_id'],
                config=params['config'],
                group=params['group'],
                option=params['option'],
                key=str(json.loads(content)['key']),
            )
        }
    )


@rest('POST', 'bad_req', response_handlers)
def bad_req_handler(content, id):
    raise BadRequestError


@rest('POST', 'timeout', response_handlers)
def timeout_producer(content, id):
    raise Timeout()


@mock.patch('handlers.keystone.TokenHandler._run_server', lambda *args: None)
@mock.patch('handlers.keystone_responses._responses', response_handlers)
@mock.patch('handlers.keystone.TokenHandler.end_headers')
@mock.patch('handlers.keystone.TokenHandler.send_header')
@mock.patch('handlers.keystone.TokenHandler.send_response', autospec=True)
class TestKeystoneHandler(object):
    def _test_handle_post_request_ok(
        self, mock_send_response, path, expected_string
    ):
        handler = self._test_handle_post_request(path)
        mock_send_response.assert_called_once_with(handler, 201)
        handler.wfile.write.assert_called_once_with(
            json.dumps({'value': expected_string + 'value'}).encode()
        )

    def _test_handle_post_request(self, path):
        handler = self._create_tokenhandler(path)
        input_data = json.dumps({'key': 'value'})
        handler.rfile.read.return_value = input_data
        handler.headers = {'Content-Length': len(input_data)}
        handler.do_POST()
        return handler

    def _test_handle_get_request(self, path):
        handler = self._create_tokenhandler(path)
        handler.do_GET()
        return handler

    @staticmethod
    def _create_tokenhandler(path):
        handler = TokenHandler(None, None, None)
        handler.wfile = MagicMock()
        handler.rfile = MagicMock()
        handler.client_address = CLIENT_ADDRESS
        handler.path = path
        return handler

    def test_handle_post_request(
        self, mock_send_response, mock_send_header, mock_end_headers
    ):
        self._test_handle_post_request_ok(
            mock_send_response, '/v2.0/tokens', REST_RESPONSE_POST
        )

    def test_handle_post_request_double_slashes(
        self, mock_send_response, mock_send_header, mock_end_headers
    ):

        self._test_handle_post_request_ok(
            mock_send_response, '/v2.0//tokens', REST_RESPONSE_POST
        )

    def test_handle_post_request_long(
        self, mock_send_response, mock_send_header, mock_end_headers
    ):
        key = 'domains'
        values = 'domain_id/config/group/option'
        path = '/v3/{}/{}'.format(key, values)

        self._test_handle_post_request_ok(mock_send_response, path, values)

    @mock.patch('handlers.keystone.TokenHandler.send_error', autospec=True)
    def test_handle_post_request_timeout(
        self,
        mock_send_error,
        mock_send_response,
        mock_send_header,
        mock_end_headers,
    ):
        self._test_handle_post_request('/v2.0/timeout')
        self._assert_send_error_correctly_called(mock_send_error, 504)

    @mock.patch('handlers.keystone.TokenHandler.send_error', autospec=True)
    def test_handle_get_request_not_allowed(
        self,
        mock_send_error,
        mock_send_response,
        mock_send_header,
        mock_end_headers,
    ):
        self._test_handle_get_request('/v2.0/tokens')
        self._assert_send_error_correctly_called(mock_send_error, 405)

    @mock.patch('handlers.keystone.TokenHandler.send_error', autospec=True)
    def test_handle_post_request_not_found(
        self,
        mock_send_error,
        mock_send_response,
        mock_send_header,
        mock_end_headers,
    ):
        self._test_handle_post_request('/v2/garbage')
        self._assert_send_error_correctly_called(mock_send_error, 404)

    @mock.patch('handlers.keystone.TokenHandler.send_error', autospec=True)
    def test_handle_post_request_bad_req(
        self,
        mock_send_error,
        mock_send_response,
        mock_send_header,
        mock_end_headers,
    ):
        self._test_handle_post_request('/v2/bad_req')
        self._assert_send_error_correctly_called(mock_send_error, 400)

    def test_empty_content(
        self, mock_send_response, mock_send_header, mock_end_headers
    ):
        handler = self._create_tokenhandler('/v2.0/empty')
        handler.rfile.read.return_value = None
        handler.headers = {'Content-Length': 0}
        handler.do_POST()
        expected_body = json.dumps({'value': EMPTY}).encode()
        handler.wfile.write.assert_called_once_with(expected_body)

    @staticmethod
    def _assert_send_error_correctly_called(mock_object, resp_code):
        mock_object.assert_called_once_with(ANY, resp_code, explain=ANY)
