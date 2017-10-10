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
import mock
import pytest

from handlers.base_handler import BadRequestError
from handlers.keystone_responses import responses
from handlers.keystone_responses import TOKENS
from handlers.base_handler import POST
from handlers.selecting_handler import SelectingHandler

NOT_RELEVANT = None
TOKEN = 'the_secret_token'
TOKEN_REQUEST = json.dumps({
    'auth': {
        'tenantName': 'customer-x',
        'passwordCredentials': {
            'username': 'joeuser',
            'password': 'secret'
        }
    }
})


@mock.patch('handlers.keystone_responses.auth.create_token',
            return_value=TOKEN)
def test_post_tokens(mock_create_token):
    handler, parameters = SelectingHandler.get_response_handler(
        responses(), POST, [TOKENS]
    )
    response = handler(content=TOKEN_REQUEST, parameters=parameters)
    mock_create_token.assert_called_once_with(
        user_at_domain='joeuser',
        user_password='secret')
    assert json.loads(response.body)['access']['token']['id'] == TOKEN


def _test_invalid_content(content):
    handler, parameters = SelectingHandler.get_response_handler(
        responses(), POST, [TOKENS]
    )
    with pytest.raises(BadRequestError):
        handler(content, NOT_RELEVANT)


def test_invalid_content_structure():
    _test_invalid_content('{"invalid": null}')


def test_invalid_content_json():
    _test_invalid_content('invalid JSON')
