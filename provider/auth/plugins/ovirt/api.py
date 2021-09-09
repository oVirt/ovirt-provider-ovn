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
#
from __future__ import absolute_import

import requests

from auth import Forbidden
from auth import Timeout

API_PATH = '/api'
HEADERS = {'Accept': 'application/json', 'Content-Type': 'application/json'}


def search_request(rel_path, query, engine_url, token, ca_file, timeout):
    return _http_get(
        url='{}/{}'.format(_get_api_url(engine_url), rel_path),
        token=token,
        ca_file=ca_file,
        timeout=timeout,
        params={'search': query},
    )


def follow_link(obj, rel, engine_host, token, ca_file, timeout):
    link = next((link for link in obj['link'] if link['rel'] == rel), None)
    assert link is not None
    url = engine_host + link['href']
    return _http_get(url, token, ca_file, timeout)


def _http_get(url, token, ca_file, timeout, params=None):
    try:
        response = requests.get(
            url,
            headers=_get_headers(token),
            verify=ca_file,
            timeout=timeout,
            params=params,
        )
    except requests.exceptions.Timeout as e:
        raise Timeout(e)

    if response.ok:
        data = response.json()

        if len(data) == 1:
            return data.values()[0]
        else:
            return data
    else:
        _handle_fail(response)


def _get_headers(token):
    headers = {}
    headers.update(HEADERS)
    headers.update({'Authorization': 'Bearer {}'.format(token)})
    return headers


def _handle_fail(response):
    try:
        content = response.json()
        raise Forbidden('{}: {}'.format(content['reason'], content['detail']))
    except (Exception,):
        response.raise_for_status()


def _get_api_url(engine_url):
    return engine_url + API_PATH
