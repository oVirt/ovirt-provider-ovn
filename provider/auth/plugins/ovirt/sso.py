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
from auth import Timeout

AUTH_PATH = '/sso/oauth'
TOKEN_PATH = '/token'
TOKEN_INFO_PATH = '/token-info'
TOKEN_NAME = 'access_token'
AUTH_HEADERS = {
    'Accept': 'application/json',
    'Content-type': 'application/x-www-form-urlencoded'}
PUBLIC_AUTHZ_SEARCH_SCOPE = 'ovirt-ext=token-info:public-authz-search'
TOKEN_SCOPE = 'ovirt-app-api ovirt-ext=token-info:validate'


def _translate_timeout_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.Timeout as e:
            raise Timeout(e)
    return wrapper


def _inspect_response(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        response.raise_for_status()
        result = response.json()
        _check_for_error(result)
        return result
    return wrapper


def create_token(username, password, engine_url, ca_file, timeout):
    sso_response = _get_sso_token(
        username, password, engine_url, ca_file, timeout)
    return sso_response[TOKEN_NAME]


@_inspect_response
@_translate_timeout_exception
def _get_sso_token(username, password, engine_url, ca_file, timeout):
    post_data = {
        'grant_type': 'password',
        'scope': TOKEN_SCOPE,
        'username': username,
        'password': password
    }
    return requests.post(_token_url(engine_url),
                         headers=AUTH_HEADERS,
                         data=post_data,
                         verify=ca_file,
                         timeout=timeout)


def get_profiles(
        token, engine_url, ca_file, timeout, client_id, client_secret):
    profiles = _profile_list(token, engine_url,
                             ca_file=ca_file,
                             timeout=timeout,
                             client_id=client_id,
                             client_secret=client_secret)['result'][1][0]
    # first element of container is corresponding data type in java
    profiles.pop(0)
    return profiles


@_inspect_response
@_translate_timeout_exception
def _profile_list(
        token, engine_url, ca_file, timeout, client_id, client_secret):
    return requests.post(_token_info_url(engine_url),
                         headers=AUTH_HEADERS,
                         data={
                             'token': token,
                             'query_type': 'profile-list',
                             'scope': PUBLIC_AUTHZ_SEARCH_SCOPE
                             },
                         auth=(client_id, client_secret),
                         verify=ca_file,
                         timeout=timeout)


@_inspect_response
@_translate_timeout_exception
def get_token_info(
        token, engine_url, ca_file, timeout, client_id, client_secret):
    return requests.post(_token_info_url(engine_url),
                         headers=AUTH_HEADERS,
                         data={'token': token},
                         auth=(client_id, client_secret),
                         verify=ca_file,
                         timeout=timeout)


def _get_token_url(engine_url):
    return engine_url + AUTH_PATH + TOKEN_PATH


def _token_info_url(engine_url):
    return engine_url + AUTH_PATH + TOKEN_INFO_PATH


def is_active(token_info):
    return token_info['active']


def get_user_id(token_info):
    user_id = token_info['user_id'].split('@')
    return user_id[0], user_id[-1]


def extract_authz_name(profiles, authn_name):
    for profile in profiles:
        if profile['authn_name'] == authn_name:
            return profile['authz_name']
    raise KeyError('{}'.format(authn_name))


def get_principal_id(token_info):
    return token_info['ovirt'][1]['principal_id']


def extract_groups(token_info):
    return [group_container[1]
            for group_container in token_info['ovirt'][1]['group_ids'][1]]


def _token_url(engine_url):
    return engine_url + AUTH_PATH + TOKEN_PATH


def _check_for_error(response):
    if 'error' in response:
        raise Unauthorized('Error during SSO authentication {} : {}'.format(
            response['error_code'], response['error']))
