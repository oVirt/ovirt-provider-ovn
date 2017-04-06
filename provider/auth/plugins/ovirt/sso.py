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
#
from functools import wraps

import requests

from auth import Unauthorized

AUTH_PATH = '/sso/oauth'
TOKEN_PATH = '/token'
TOKEN_INFO_PATH = '/token-info'
TOKEN_NAME = 'access_token'
AUTH_HEADERS = {
    'Accept': 'application/json',
    'Content-type': 'application/x-www-form-urlencoded'}
PUBLIC_AUTHZ_SEARCH_SCOPE = 'ovirt-ext=token-info:public-authz-search'
TOKEN_SCOPE = 'ovirt-app-api ovirt-ext=token-info:validate'


def _inspect_response(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        response.raise_for_status()
        result = response.json()
        _check_for_error(result)
        return result
    return wrapper


def create_token(username, password, engine_url, ca_file):
    sso_response = _get_sso_token(username, password, engine_url, ca_file)
    return sso_response[TOKEN_NAME]


@_inspect_response
def _get_sso_token(username, password, engine_url, ca_file):
    post_data = {
        'grant_type': 'password',
        'scope': TOKEN_SCOPE,
        'username': username,
        'password': password
    }
    return requests.post(_token_url(engine_url),
                         headers=AUTH_HEADERS,
                         data=post_data,
                         verify=ca_file)


def _token_url(engine_url):
    return engine_url + AUTH_PATH + TOKEN_PATH


def _check_for_error(response):
    if 'error' in response:
        raise Unauthorized(
            'Error during SSO authentication {} : {}'.format(
                response['error_code'], response['error']))
