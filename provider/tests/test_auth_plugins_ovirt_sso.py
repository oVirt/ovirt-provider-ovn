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
from requests.exceptions import ConnectTimeout

from auth.plugins.ovirt import sso

NOT_RELEVANT = None

ENGINE_URL = 'http://test.com/ovirt-engine'
TOKEN_URL = 'http://test.com/ovirt-engine/sso/oauth/token'
TOKEN_INFO_URL = 'http://test.com/ovirt-engine/sso/oauth/token-info'
TOKEN = 'the_secret_token'

TOKEN_RESPONSE_SUCCESS = json.dumps({'access_token': TOKEN})

TOKEN_RESPONSE_AUTH_FAILED = json.dumps({
    'error_code': 'access_denied',
    'error':    "Cannot authenticate user 'netadmin@internal':"
                "Cannot Login. User Account is Disabled or Locked"
                "Please contact your system administrator.."
})

PROFILES_LIST_RESPONSE = json.dumps({
    'result': [
        'java.util.ArrayList',
        [[
            'java.util.HashMap',
            {
                'authz_name': 'internal-authz',
                'authn_name': 'internal'
            }
        ]]
    ]
})

PROFILES = [{
    'authn_name': 'internal',
    'authz_name': 'internal-authz'
}]

INFO = {
    'user_id': 'netadmin@internal',
    'client_id': None,
    'token_type': 'bearer',
    'exp': '1490609013000',
    'active': True
}


@requests_mock.Mocker()
class TestOvirtSso(object):

    def test_create_token_success(self, mock_requests):
        mock_requests.register_uri('POST', TOKEN_URL,
                                   text=TOKEN_RESPONSE_SUCCESS)
        token = sso.create_token(username=NOT_RELEVANT,
                                 password=NOT_RELEVANT,
                                 engine_url=ENGINE_URL,
                                 ca_file=NOT_RELEVANT,
                                 timeout=NOT_RELEVANT)
        assert token == TOKEN

    def test_create_token_fail(self, mock_requests):
        mock_requests.register_uri('POST', TOKEN_URL,
                                   status_code=400,
                                   text=TOKEN_RESPONSE_AUTH_FAILED)
        with pytest.raises(sso.Unauthorized):
            sso.create_token(username=NOT_RELEVANT,
                             password=NOT_RELEVANT,
                             engine_url=ENGINE_URL,
                             ca_file=NOT_RELEVANT,
                             timeout=NOT_RELEVANT)

    def test_create_token_timeout(self, mock_requests):
        mock_requests.register_uri('POST', TOKEN_URL, exc=ConnectTimeout)
        with pytest.raises(sso.Timeout):
            sso.create_token(username=NOT_RELEVANT,
                             password=NOT_RELEVANT,
                             engine_url=ENGINE_URL,
                             ca_file=NOT_RELEVANT,
                             timeout=NOT_RELEVANT)

    def test_get_profiles(self, mock_requests):
        mock_requests.register_uri('POST', TOKEN_INFO_URL,
                                   text=PROFILES_LIST_RESPONSE)
        profiles = sso.get_profiles(token=TOKEN,
                                    engine_url=ENGINE_URL,
                                    ca_file=NOT_RELEVANT,
                                    timeout=NOT_RELEVANT,
                                    client_id=NOT_RELEVANT,
                                    client_secret=NOT_RELEVANT)
        assert profiles == PROFILES

    def test_get_token_info(self, mock_requests):
        mock_requests.register_uri('POST', TOKEN_INFO_URL,
                                   text=json.dumps(INFO))
        info = sso.get_token_info(token=TOKEN,
                                  engine_url=ENGINE_URL,
                                  ca_file=NOT_RELEVANT,
                                  timeout=NOT_RELEVANT,
                                  client_id=NOT_RELEVANT,
                                  client_secret=NOT_RELEVANT)
        assert info == INFO
