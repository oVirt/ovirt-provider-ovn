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

from mock import MagicMock
import mock
import pytest

from handlers.neutron import NeutronHandler

from handlers.selecting_handler import rest


REST_RESPONSE_GET = 'REST_RESPONSE_GET'
REST_RESPONSE_SHOW = 'REST_RESPONSE_SHOW'
REST_RESPONSE_POST = 'REST_RESPONSE_POST'


response_handlers = {}


@rest('GET', 'testports', response_handlers)
def get_handler(nb_db, content, id):
    return REST_RESPONSE_GET


@rest('SHOW', 'testports', response_handlers)
def show_handler(nb_db, content, id):
    return REST_RESPONSE_SHOW + id


@rest('DELETE', 'testports', response_handlers)
def delete_handler(nb_db, content, id):
    return None


@rest('POST', 'testports', response_handlers)
def post_handler(nb_db, content, id):
    return REST_RESPONSE_POST + content


@mock.patch('handlers.neutron.NeutronHandler._run_server', lambda *args: None)
@mock.patch('handlers.neutron_responses._responses', response_handlers)
class TestNeutronHandler(object):

    @mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
    @mock.patch('handlers.neutron.NeutronHandler.end_headers')
    @mock.patch('handlers.neutron.NeutronHandler.send_header')
    @mock.patch('handlers.neutron.NeutronHandler.send_response', autospec=True)
    @mock.patch('handlers.neutron.validate_token', return_value=True)
    def test_handle_get_request(self, mock_validate_token, mock_send_response,
                                mock_send_header, mock_end_headers,
                                mock_ndb_api):

        handler = NeutronHandler(None, None, None)
        handler.wfile = MagicMock()
        handler.headers = {}
        handler.path = '/v2.0/testports'

        handler.do_GET()

        assert mock_send_response.call_args[0][1] == 200
        assert handler.wfile.write.call_args[0][0] == REST_RESPONSE_GET
        assert mock_send_response.call_count == 1
        assert mock_validate_token.call_count == 1

    @mock.patch('handlers.neutron.validate_token', return_value=False)
    @mock.patch('handlers.neutron.NeutronHandler.log_error')
    @mock.patch('handlers.neutron.NeutronHandler.send_error')
    def test_handle_get_request_auth_fail(self, mock_send_error,
                                          mock_log_error, mock_validate_token):

        handler = NeutronHandler(None, None, None)
        handler.wfile = MagicMock()
        handler.headers = {}
        handler.path = '/v2.0/testports'

        handler.do_GET()

        assert mock_validate_token.call_count == 1
        assert mock_send_error.call_args[0][0] == 403

    @mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
    @mock.patch('handlers.neutron.NeutronHandler.end_headers')
    @mock.patch('handlers.neutron.NeutronHandler.send_header')
    @mock.patch('handlers.neutron.NeutronHandler.send_response', autospec=True)
    @mock.patch('handlers.neutron.validate_token', return_value=True)
    def test_handle_get_request_with_id(self, mock_validate_token,
                                        mock_send_response, mock_send_header,
                                        mock_end_headers,
                                        mock_ndb_api):

        handler = NeutronHandler(None, None, None)
        handler.wfile = MagicMock()
        id = '123456'
        handler.headers = {}
        handler.path = '/v2.0/testports/' + id

        handler.do_GET()

        assert mock_send_response.call_args[0][1] == 200
        assert handler.wfile.write.call_args[0][0] == REST_RESPONSE_SHOW + id
        assert mock_send_response.call_count == 1
        assert mock_validate_token.call_count == 1

    @mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
    @mock.patch('handlers.neutron.NeutronHandler.end_headers')
    @mock.patch('handlers.neutron.NeutronHandler.send_header')
    @mock.patch('handlers.neutron.NeutronHandler.send_response', autospec=True)
    @mock.patch('handlers.neutron.validate_token', return_value=True)
    def test_handle_delete_request(self, mock_validate_token,
                                   mock_send_response, mock_send_header,
                                   mock_end_headers, mock_ndb_api):

        handler = NeutronHandler(None, None, None)
        handler.wfile = MagicMock()
        id = '123456'
        handler.headers = {}
        handler.path = '/v2.0/testports/' + id

        handler.do_DELETE()

        assert mock_send_response.call_args[0][1] == 204
        assert handler.wfile.write.call_count == 0
        assert mock_send_response.call_count == 1
        assert mock_validate_token.call_count == 1

    @mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
    @mock.patch('handlers.neutron.NeutronHandler.end_headers')
    @mock.patch('handlers.neutron.NeutronHandler.send_header')
    @mock.patch('handlers.neutron.NeutronHandler.send_response', autospec=True)
    def test_handle_delete_with_no_id(self, mock_send_response,
                                      mock_send_header, mock_end_headers,
                                      mock_ndb_api):

        handler = NeutronHandler(None, None, None)
        handler.wfile = MagicMock()
        handler.path = '/v2.0/testports'
        with pytest.raises(AssertionError,
                           message='Delete request must specify an id'):
            handler.do_DELETE()

    @mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
    @mock.patch('handlers.neutron.NeutronHandler.end_headers')
    @mock.patch('handlers.neutron.NeutronHandler.send_header')
    @mock.patch('handlers.neutron.NeutronHandler.send_response', autospec=True)
    @mock.patch('handlers.neutron.validate_token', return_value=True)
    def test_handle_post_request(self, mock_validate_token, mock_send_response,
                                 mock_send_header, mock_end_headers,
                                 mock_ndb_api):

        handler = NeutronHandler(None, None, None)
        handler.wfile = MagicMock()
        handler.rfile = MagicMock()
        handler.rfile.read.return_value = 'content'
        handler.headers = {'Content-Length': 7}

        handler.path = '/v2.0/testports'

        handler.do_POST()

        assert mock_send_response.call_args[0][1] == 200
        expected_response = REST_RESPONSE_POST + 'content'
        assert handler.wfile.write.call_args[0][0] == expected_response
        assert mock_send_response.call_count == 1
        assert mock_validate_token.call_count == 1
