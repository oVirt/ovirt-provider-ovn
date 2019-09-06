# Copyright 2019 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license


import requests


ENDPOINT = 'http://localhost:9696/v2.0/'
NETWORK_ENDPOINT = ENDPOINT + 'networks/'
PORT_ENDPOINT = ENDPOINT + 'ports/'


def get_port_by_name(port_name):
    return _get_entity_by_name('ports', port_name)


def get_network_by_name(network_name):
    return _get_entity_by_name('networks', network_name)


def get_router_by_name(router_name):
    return _get_entity_by_name('routers', router_name)


def _get_entity_by_name(entity_type, entity_name):
    return next(
        (
            entity for entity in _get_entities_by_type(entity_type)
            if entity.get('name') == entity_name
        ),
        None
    )


def get_networks():
    return _get_entities_by_type('networks')


def get_ports():
    return _get_entities_by_type('ports')


def _get_entities_by_type(entity_type):
    reply = requests.get(ENDPOINT + entity_type)
    return reply.json().get(entity_type, [])


def update_and_assert(entity_type, entity_id, update_payload):
    url = ENDPOINT + entity_type + '/{}'.format(entity_id)
    singular_entity_type = entity_type[0:len(entity_type)-1]
    response = requests.put(url, json=update_payload)
    assert response.status_code == 200
    json_response = response.json()
    updated_entity = json_response.get(singular_entity_type)
    assert len(json_response) == 1
    for k, v in update_payload[singular_entity_type].items():
        assert updated_entity[k] == v


def create_entity(entity_type, create_payload):
    url = ENDPOINT + entity_type
    response = requests.post(url, json=create_payload)
    assert response.status_code == 201
    return response.json()


def delete_entity(entity_type, entity_id):
    url = ENDPOINT + entity_type + '/{}'.format(entity_id)
    response = requests.delete(url)
    assert response.status_code in (200, 204)


class SecurityGroup(object):
    def __init__(self, name, description):
        self._name = name
        self._description = description
        self._security_group_id = None

    @property
    def description(self):
        return self._description

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._security_group_id

    def __enter__(self):
        security_group = self._create_security_group()
        self._security_group_id = security_group['id']
        return self

    def _create_security_group(self):
        create_group_data = {
            'security_group': {
                'name': self._name,
                'description': self._description
            }
        }
        return create_entity('security-groups', create_group_data).get(
            'security_group'
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        return delete_entity('security-groups', self.id)
