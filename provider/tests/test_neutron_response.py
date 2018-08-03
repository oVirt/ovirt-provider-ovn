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
import mock
import pytest

from handlers.base_handler import BadRequestError
from handlers.neutron_responses import responses
from handlers.neutron_responses import GET
from handlers.neutron_responses import DELETE
from handlers.neutron_responses import POST
from handlers.neutron_responses import PUT

from handlers.neutron_responses import NETWORK_ID
from handlers.neutron_responses import PORT_ID

from handlers.neutron_responses import ADD_ROUTER_INTERFACE
from handlers.neutron_responses import DELETE_ROUTER_INTERFACE
from handlers.neutron_responses import FLOATINGIPS
from handlers.neutron_responses import NETWORK_ENTITY
from handlers.neutron_responses import NETWORKS
from handlers.neutron_responses import PORT_ENTITY
from handlers.neutron_responses import PORTS
from handlers.neutron_responses import ROUTER_ENTITY
from handlers.neutron_responses import ROUTERS
from handlers.neutron_responses import SECURITY_GROUPS
from handlers.neutron_responses import SUBNET_ENTITY
from handlers.neutron_responses import SUBNETS

from handlers.selecting_handler import SelectingHandler

from neutron.ovn_north_mappers import NetworkMapper
from neutron.ovn_north_mappers import PortMapper
from neutron.ovn_north_mappers import Router
from neutron.ovn_north_mappers import RouterMapper
from neutron.ovn_north import OvnNorth

from ovntestlib import OvnRouterRow


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
            for path in [NETWORKS, PORTS, SUBNETS, ROUTERS]:
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
                SUBNET_ENTITY.format(subnet_id=7),
                ROUTER_ENTITY.format(router_id=7)
            ]:
                handler, params = SelectingHandler.get_response_handler(
                    responses(), method, path.split('/')
                )
                assert handler is not None
                assert params is not None
                assert params.values()[0] == '7'

        for path in [
            ADD_ROUTER_INTERFACE.format(router_id=7),
            DELETE_ROUTER_INTERFACE.format(router_id=7)
        ]:
            handler, params = SelectingHandler.get_response_handler(
                responses(), PUT, path.split('/')
            )
            assert handler is not None
            assert params is not None
            assert params['router_id'] == '7'

        for path in [
            FLOATINGIPS,
            SECURITY_GROUPS
        ]:
            handler, params = SelectingHandler.get_response_handler(
                responses(), GET, path.split('/')
            )
            assert handler is not None

        # This is a test call engine makes to check if provider is alive
        handler, params = SelectingHandler.get_response_handler(
            responses(), GET, ''.split('/')
        )
        assert handler is not None

    handler, params = SelectingHandler.get_response_handler(
        responses(), GET, ['']
    )
    assert handler is not None

    def _test_invalid_content(self, content):
        for path in [NETWORKS, PORTS, SUBNETS]:
            handler, params = SelectingHandler.get_response_handler(
                responses(), POST, path.split('/')
            )
            with pytest.raises(BadRequestError):
                handler(NOT_RELEVANT, content, NOT_RELEVANT)

        for path in [
            NETWORK_ENTITY.format(network_id=7),
            PORT_ENTITY.format(port_id=7),
            SUBNET_ENTITY.format(subnet_id=7)
        ]:
            handler, params = SelectingHandler.get_response_handler(
                responses(), PUT, path.split('/')
            )
            with pytest.raises(BadRequestError):
                handler(NOT_RELEVANT, content, NOT_RELEVANT)

    def test_invalid_content_structure(self):
        self._test_invalid_content('{"invalid": null}')

    def test_invalid_content_json(self):
        self._test_invalid_content('invalid JSON')

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

        response_json = response.body
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

        response_json = response.body
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

        response_json = response.body
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

        response_json = response.body
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

        response_json = response.body
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

        response_json = response.body
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
        response_json = response.body
        assert response_json['port']['id'] == str(PORT_ID07)

    @mock.patch('ovsdbapp.backend.ovs_idl.connection', autospec=False)
    def test_post_routers(self, mock_connection):
        nb_db = OvnNorth()
        nb_db._add_router = Mock()
        nb_db.atomics.idl = Mock()

        nb_db._add_router.return_value = Router(OvnRouterRow(
            'uuid',
            'router1',
            {
                RouterMapper.OVN_ROUTER_GATEWAY_PORT: 'port_id',
            }
        ), 'network_id', 'subnet_id', '1.1.1.1')
        rest_input = '''{
            "router": {
                "name": "router1",
                "external_gateway_info": {
                    "enable_snat": false,
                    "external_fixed_ips": [{
                        "ip_address": "172.24.4.6",
                        "subnet_id": "b930d7f6-ceb7-40a0-8b81-a425dd994ccf"
                    }],
                    "network_id": "ae34051f-aa6c-4c75-abf5-50dc9ac99ef3"
                }
            }
        }'''

        handler, params = SelectingHandler.get_response_handler(
            responses(), POST, ROUTERS.split('/')
        )
        response = handler(nb_db, rest_input, NOT_RELEVANT)

        response_json = response.body
        router = response_json['router']
        assert router[RouterMapper.REST_ROUTER_NAME] == 'router1'
        assert router[RouterMapper.REST_ROUTER_ID] == 'uuid'

        gateway = router[RouterMapper.REST_ROUTER_EXTERNAL_GATEWAY_INFO]
        ips = gateway[RouterMapper.REST_ROUTER_FIXED_IPS][0]
        assert gateway[RouterMapper.REST_ROUTER_NETWORK_ID] == 'network_id'
        assert ips[RouterMapper.REST_ROUTER_SUBNET_ID] == 'subnet_id'
        assert ips[RouterMapper.REST_ROUTER_IP_ADDRESS] == '1.1.1.1'

        nb_db._add_router.assert_called_once_with(
            'router1',
            True,
            'ae34051f-aa6c-4c75-abf5-50dc9ac99ef3',
            'b930d7f6-ceb7-40a0-8b81-a425dd994ccf',
            '172.24.4.6',
            None
        )
