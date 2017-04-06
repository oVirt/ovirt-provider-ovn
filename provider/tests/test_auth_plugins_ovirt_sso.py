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

import pytest
import requests_mock

from auth.plugins.ovirt import sso

NOT_RELEVANT = None

ENGINE_URL = 'http://test.com/ovirt-engine'
TOKEN_URL = 'http://test.com/ovirt-engine/sso/oauth/token'
TOKEN = 'the_secret_token'

TOKEN_RESPONSE_SUCCESS = json.dumps({'access_token': TOKEN})

TOKEN_RESPONSE_AUTH_FAILED = json.dumps({
    'error_code': 'access_denied',
    'error':    "Cannot authenticate user 'netadmin@internal':"
                "Cannot Login. User Account is Disabled or Locked"
                "Please contact your system administrator.."
})


@requests_mock.Mocker()
class TestOvirtSso(object):

    def test_create_token_success(self, mock_requests):
        mock_requests.register_uri('POST', TOKEN_URL,
                                   text=TOKEN_RESPONSE_SUCCESS)
        token = sso.create_token(username=NOT_RELEVANT,
                                 password=NOT_RELEVANT,
                                 engine_url=ENGINE_URL,
                                 ca_file=NOT_RELEVANT)
        assert token == TOKEN

    def test_create_token_fail(self, mock_requests):
        mock_requests.register_uri('POST', TOKEN_URL,
                                   text=TOKEN_RESPONSE_AUTH_FAILED)
        with pytest.raises(sso.Unauthorized):
            sso.create_token(username=NOT_RELEVANT,
                             password=NOT_RELEVANT,
                             engine_url=ENGINE_URL,
                             ca_file=NOT_RELEVANT)
