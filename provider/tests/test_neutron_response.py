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

from neutron_responses import responses, rest
from neutron_responses import GET
from neutron_responses import SHOW
from neutron_responses import DELETE
from neutron_responses import POST
from neutron_responses import PUT

from neutron_responses import NETWORKS
from neutron_responses import PORTS

from ovndb.ovn_rest2db_mappers import PortMapper
from ovndb.ndb_api import NetworkPort


NOT_RELEVANT = None

ID01 = UUID(int=1)
ID07 = UUID(int=7)


class NetworkRow(object):
    def __init__(self, uuid, name):
        self.uuid = uuid
        self.name = name


class PortRow(object):
    def __init__(self, uuid, name, mac, device_id):
        self.uuid = uuid
        self.name = name
        self.addresses = [mac]
        self.options = {PortMapper.DEVICE_ID: device_id}


class TestNeutronResponse(object):
    def test_assign_responses(self):

        @rest('TEST1', 'test1')
        def decorated_method1():
            return 1

        @rest('TEST2', 'test2')
        def decorated_method2():
            return 2

        assert responses()['TEST1']['test1']() == 1
        assert responses()['TEST2']['test2']() == 2

    def test_check_neutron_responses_required_by_engine_are_present(self):
        for method in [GET, SHOW, DELETE, POST]:
            for path in [NETWORKS, PORTS]:
                assert responses()[method][path] is not None
        assert responses()[PUT][PORTS] is not None
        # This is a test call engine makes to check if provider is alive
        assert responses()[GET][''] is not None

    def test_show_network(self):
        nb_db = Mock()
        nb_db.get_network.return_value = NetworkRow(ID01, 'network_name')

        response = responses()[SHOW][NETWORKS](nb_db, NOT_RELEVANT, ID01)

        response_json = json.loads(response)
        assert response_json['network']['id'] == str(ID01)
        assert response_json['network']['name'] == 'network_name'

    def test_show_port(self):
        nb_db = Mock()
        netport = NetworkPort(PortRow(ID07, 'port_name', 'mac', 'device_id'),
                              NetworkRow(ID01, 'network_name'))
        nb_db.get_port.return_value = netport

        response = responses()[SHOW][PORTS](nb_db, NOT_RELEVANT, ID07)

        response_json = json.loads(response)
        assert response_json['port']['id'] == str(ID07)
        assert response_json['port']['name'] == 'port_name'

    def test_get_networks(self):
        nb_db = Mock()
        nb_db.networks = [NetworkRow(ID01, 'network_name')]

        response = responses()[GET][NETWORKS](nb_db, NOT_RELEVANT,
                                              NOT_RELEVANT)

        response_json = json.loads(response)
        assert response_json['networks'][0]['id'] == str(ID01)
        assert response_json['networks'][0]['name'] == 'network_name'

    def test_get_ports(self):
        nb_db = Mock()
        netport = NetworkPort(PortRow(ID07, 'port_name', 'mac', 'device_id'),
                              NetworkRow(ID01, 'network_name'))
        nb_db.ports = [netport]

        response = responses()[GET][PORTS](nb_db, NOT_RELEVANT, NOT_RELEVANT)

        response_json = json.loads(response)
        assert response_json['ports'][0]['id'] == str(ID07)
        assert response_json['ports'][0]['name'] == 'port_name'

    def test_delete_network(self):
        nb_db = Mock()

        responses()[DELETE][NETWORKS](nb_db, NOT_RELEVANT, ID07)

        nb_db.delete_network.assert_called_once_with(ID07)

    def test_delete_port(self):
        nb_db = Mock()

        responses()[DELETE][PORTS](nb_db, NOT_RELEVANT, ID07)

        nb_db.delete_port.assert_called_once_with(ID07)

    def test_post_network(self):
        nb_db = Mock()
        nb_db.update_network.return_value = NetworkRow(ID01, 'network_name')
        rest_input = '{"network":{"name":"network_name"}}'

        response = responses()[POST][NETWORKS](nb_db, rest_input, NOT_RELEVANT)

        response_json = json.loads(response)
        assert response_json['network']['id'] == str(ID01)
        assert response_json['network']['name'] == 'network_name'

        rest_json = json.loads(rest_input)
        nb_db.update_network.assert_called_once_with(rest_json['network'])

    def test_post_port(self):
        nb_db = Mock()
        netport = NetworkPort(PortRow(ID07, 'port_name', 'mac', 'device_id'),
                              NetworkRow(ID01, 'network_name'))
        nb_db.update_port.return_value = netport
        rest_input = ('{"port":{"name":"port_name", "mac_address":"mac",'
                      '"device_id":"device_id"}}')

        response = responses()[POST][PORTS](nb_db, rest_input, NOT_RELEVANT)

        response_json = json.loads(response)
        assert response_json['port']['id'] == str(ID07)
        assert response_json['port']['name'] == 'port_name'
        assert response_json['port']['mac_address'] == 'mac'
        assert response_json['port']['device_id'] == 'device_id'
        assert response_json['port']['device_owner'] == 'oVirt'
        assert response_json['port']['network_id'] == str(ID01)

        rest_json = json.loads(rest_input)
        nb_db.update_port.assert_called_once_with(rest_json['port'])
