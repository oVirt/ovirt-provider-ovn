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

from mock import Mock
from uuid import UUID
import json

from handlers.neutron_responses import responses
from handlers.neutron_responses import GET
from handlers.neutron_responses import DELETE
from handlers.neutron_responses import POST
from handlers.neutron_responses import PUT

from handlers.neutron_responses import NETWORK_ID
from handlers.neutron_responses import PORT_ID

from handlers.neutron_responses import NETWORK_ENTITY
from handlers.neutron_responses import NETWORKS
from handlers.neutron_responses import PORT_ENTITY
from handlers.neutron_responses import PORTS
from handlers.neutron_responses import SUBNET_ENTITY
from handlers.neutron_responses import SUBNETS

from handlers.selecting_handler import SelectingHandler

from ovndb.ovn_north_mappers import NetworkMapper
from ovndb.ovn_north_mappers import PortMapper


NOT_RELEVANT = None

NETWORK_ID01 = UUID(int=1)
NETWORK_NAME1 = 'network_name_1'
PORT_ID07 = UUID(int=7)


class NetworkRow(object):
    def __init__(self, uuid, name):
        self.uuid = uuid
        self.name = name


class PortRow(object):
    def __init__(self, uuid, name, mac, device_id):
        self.uuid = uuid
        self.name = name
        self.addresses = [mac]
        self.external_ids = {PortMapper.REST_PORT_DEVICE_ID: device_id}


class TestNeutronResponse(object):
    def test_check_neutron_responses_required_by_engine_are_present(self):
        for method in [GET, POST]:
            for path in [NETWORKS, PORTS, SUBNETS]:
                handler, params = SelectingHandler.get_response_handler(
                    responses(), method, path.split('/')
                )
                assert handler is not None
                assert params is not None
                assert not params

        for method in [GET, PUT, DELETE]:
            for path in [
                NETWORK_ENTITY.format(network_id=7),
                PORT_ENTITY.format(port_id=7),
                SUBNET_ENTITY.format(subnet_id=7)
            ]:
                handler, params = SelectingHandler.get_response_handler(
                    responses(), method, path.split('/')
                )
                assert handler is not None
                assert params is not None
                assert params.values()[0] == '7'

        # This is a test call engine makes to check if provider is alive
        handler, params = SelectingHandler.get_response_handler(
            responses(), GET, ''.split('/')
        )
        assert handler is not None

    def test_show_network(self):
        nb_db = Mock()
        nb_db.get_network.return_value = {
            NetworkMapper.REST_NETWORK_ID: str(NETWORK_ID01),
            NetworkMapper.REST_NETWORK_NAME: NETWORK_NAME1,
        }
        handler, params = SelectingHandler.get_response_handler(
            responses(), GET, NETWORK_ENTITY.split('/')
        )

        response = handler(nb_db, NOT_RELEVANT, {NETWORK_ID: NETWORK_ID01})

        response_json = json.loads(response)
        assert response_json['network']['id'] == str(NETWORK_ID01)
        assert response_json['network']['name'] == NETWORK_NAME1

    def test_show_port(self):
        nb_db = Mock()
        nb_db.get_port.return_value = {
            PortMapper.REST_PORT_ID: str(PORT_ID07),
            PortMapper.REST_PORT_NAME: 'port_name',
            PortMapper.REST_PORT_SECURITY_GROUPS: [],
        }
        handler, params = SelectingHandler.get_response_handler(
            responses(), GET, PORT_ENTITY.split('/')
        )
        response = handler(nb_db, NOT_RELEVANT, {PORT_ID: PORT_ID07})

        response_json = json.loads(response)
        assert response_json['port']['id'] == str(PORT_ID07)
        assert response_json['port']['name'] == 'port_name'
        assert response_json['port']['security_groups'] == []

    def test_get_networks(self):
        nb_db = Mock()
        nb_db.list_networks.return_value = [{
            NetworkMapper.REST_NETWORK_ID: str(NETWORK_ID01),
            NetworkMapper.REST_NETWORK_NAME: NETWORK_NAME1,
        }]
        handler, params = SelectingHandler.get_response_handler(
            responses(), GET, NETWORKS.split('/')
        )
        response = handler(nb_db, NOT_RELEVANT, NOT_RELEVANT)

        response_json = json.loads(response)
        assert response_json['networks'][0]['id'] == str(NETWORK_ID01)
        assert response_json['networks'][0]['name'] == NETWORK_NAME1

    def test_get_ports(self):
        nb_db = Mock()
        nb_db.list_ports.return_value = [{
            PortMapper.REST_PORT_ID: str(PORT_ID07),
            PortMapper.REST_PORT_NAME: 'port_name',
            PortMapper.REST_PORT_SECURITY_GROUPS: [],
        }]
        handler, params = SelectingHandler.get_response_handler(
            responses(), GET, PORTS.split('/')
        )

        response = handler(nb_db, NOT_RELEVANT, NOT_RELEVANT)

        response_json = json.loads(response)
        assert response_json['ports'][0]['id'] == str(PORT_ID07)
        assert response_json['ports'][0]['name'] == 'port_name'
        assert response_json['ports'][0]['security_groups'] == []

    def test_delete_network(self):
        nb_db = Mock()

        handler, params = SelectingHandler.get_response_handler(
            responses(),
            DELETE,
            NETWORK_ENTITY.format(network_id=NETWORK_ID01).split('/')
        )
        handler(nb_db, NOT_RELEVANT, params)

        nb_db.delete_network.assert_called_once_with(str(NETWORK_ID01))

    def test_delete_port(self):

        nb_db = Mock()

        handler, params = SelectingHandler.get_response_handler(
            responses(),
            DELETE,
            PORT_ENTITY.format(port_id=PORT_ID07).split('/')
        )
        handler(nb_db, NOT_RELEVANT, params)

        nb_db.delete_port.assert_called_once_with(str(PORT_ID07))

    def test_post_network(self):
        nb_db = Mock()
        nb_db.add_network.return_value = {
            NetworkMapper.REST_NETWORK_ID: str(NETWORK_ID01),
            NetworkMapper.REST_NETWORK_NAME: NETWORK_NAME1,
            NetworkMapper.REST_TENANT_ID: ''
        }
        rest_input = '{"network":{"name":"network_name"}}'

        handler, params = SelectingHandler.get_response_handler(
            responses(), POST, NETWORKS.split('/')
        )
        response = handler(nb_db, rest_input, NOT_RELEVANT)

        response_json = json.loads(response.body)
        assert response_json['network']['id'] == str(NETWORK_ID01)
        assert response_json['network']['name'] == NETWORK_NAME1

        rest_json = json.loads(rest_input)
        nb_db.add_network.assert_called_once_with(rest_json['network'])

    def test_post_port(self):
        nb_db = Mock()
        nb_db.add_port.return_value = {
            PortMapper.REST_PORT_ID: str(PORT_ID07),
            PortMapper.REST_PORT_NAME: 'port_name',
            PortMapper.REST_PORT_DEVICE_ID: 'device_id',
            PortMapper.REST_PORT_DEVICE_OWNER: 'oVirt',
            PortMapper.REST_PORT_NETWORK_ID: str(NETWORK_ID01),
            PortMapper.REST_PORT_MAC_ADDRESS: 'mac'
        }
        rest_input = ('{"port":{"name":"port_name", "mac_address":"mac",'
                      '"device_id":"device_id"}}')

        handler, params = SelectingHandler.get_response_handler(
            responses(), POST, PORTS.split('/')
        )
        response = handler(nb_db, rest_input, NOT_RELEVANT)

        response_json = json.loads(response.body)
        assert response_json['port']['id'] == str(PORT_ID07)
        assert response_json['port']['name'] == 'port_name'
        assert response_json['port']['mac_address'] == 'mac'
        assert response_json['port']['device_id'] == 'device_id'
        assert response_json['port']['device_owner'] == 'oVirt'
        assert response_json['port']['network_id'] == str(NETWORK_ID01)

        rest_json = json.loads(rest_input)
        nb_db.add_port.assert_called_once_with(rest_json['port'])

    def test_put_port(self):
        nb_db = Mock()
        nb_db.update_port.return_value = {
            PortMapper.REST_PORT_ID: str(PORT_ID07),
        }
        handler, params = SelectingHandler.get_response_handler(
            responses(), PUT, PORT_ENTITY.split('/')
        )
        response = handler(nb_db, '{"port" :{}}', {PORT_ID: str(PORT_ID07)})
        response_json = json.loads(response.body)
        assert response_json['port']['id'] == str(PORT_ID07)
