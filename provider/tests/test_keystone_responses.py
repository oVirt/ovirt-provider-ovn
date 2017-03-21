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

import mock

from handlers.keystone_responses import responses
from handlers.keystone_responses import TOKENS
from handlers.base_handler import POST

TOKEN = 'the_secret_token'
TOKEN_REQUEST = {
    'auth': {
        'tenantName': 'customer-x',
        'passwordCredentials': {
            'username': 'joeuser',
            'password': 'secret'
        }
    }
}


@mock.patch('handlers.keystone_responses.auth.create_token',
            return_value=TOKEN)
def test_post_tokens(mock_create_token):
    post_response_handlers = responses()[POST]
    post_tokens_response_handler = post_response_handlers[TOKENS]
    response = post_tokens_response_handler(content=TOKEN_REQUEST, id=None)
    mock_create_token.assert_called_once_with(
        user_at_domain='joeuser',
        user_password='secret')
    assert response['access']['token']['id'] == TOKEN
