# Copyright 2018 Red Hat, Inc.
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

import pytest
import requests


ENDPOINT = 'http://localhost:9696/v2.0/'


@pytest.fixture(scope='module')
def logical_switch():
    payload = {
        'network': {'name': 'ls0'}
    }
    response = requests.post(
        'http://localhost:9696/v2.0/networks/', json=payload
    )
    if response.status_code not in range(200, 205):
        raise Exception('could not create network')
    try:
        yield response.json()['network']
    finally:
        requests.delete(
            'http://localhost:9696/v2.0/networks/' +
            response.json()['network']['id']
        )


def test_get_network(logical_switch):
    networks = _get_and_assert('networks')
    assert len(networks) == 1
    assert networks.pop()['name'] == logical_switch['name']


def test_filter(logical_switch):
    networks = _get_and_assert('networks', 'name', 'ls0')
    assert len(networks) == 1
    assert networks.pop()['name'] == logical_switch['name']
    assert len(_get_and_assert('networks', 'name', 'kangaroo')) == 0


def test_limiter(logical_switch):
    networks = _get_and_assert('networks', 'limit', '1000')
    assert len(networks) == 1
    assert networks.pop()['name'] == logical_switch['name']


def _get_and_assert(entity_type, filter_key=None, filter_value=None):
    url = ENDPOINT + entity_type + (
        '?{key}={value}'.format(key=filter_key, value=filter_value)
        if filter_key and filter_value else ''
    )
    r = requests.get(url)
    assert r.status_code == 200
    return r.json()[entity_type]
