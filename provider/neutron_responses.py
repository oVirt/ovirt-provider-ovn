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

import json

from ovndb.ovn_rest2db_mappers import NetworkMapper
from ovndb.ovn_rest2db_mappers import PortMapper

GET = 'GET'  # list of entities
SHOW = 'SHOW'  # concrete entity
DELETE = 'DELETE'
POST = 'POST'
PUT = 'PUT'

NETWORKS = 'networks'
PORTS = 'ports'
SUBNETS = 'subnets'


_responses = {}


def rest(method, path):
    """
    Decorator for adding rest request handling methods.
    method -- rest method of the arriving request: GET/POST/DELETE/PUT
    path -- the path of the arriving request
    For example the function handling the following request:
    GET: http://<host>/../networks
    would have to be decorated with:
    rest('GET', 'networks')
    """
    def assign_response(funct):
        if method not in _responses:
            _responses[method] = {}
        _responses[method][path] = funct
        return funct
    return assign_response


@rest(SHOW, NETWORKS)
def show_network(nb_db, content, id=None):
    return json.dumps({
        'network': NetworkMapper.row2rest(nb_db.get_network(id))
    })


@rest(SHOW, PORTS)
def show_port(nb_db, content, id=None):
    return json.dumps({
        'port': PortMapper.row2rest(nb_db.get_port(id))
    })


@rest(SHOW, SUBNETS)
def show_subnet(nb_db, content, id):
    return json.dumps({
        'subnet': ''
    })


@rest(GET, '')
def get_default(nb_db, content, id):
    return json.dumps({})


@rest(GET, NETWORKS)
def get_networks(nb_db, conten, id):
    networks = nb_db.networks
    return json.dumps({
        'networks': [NetworkMapper.row2rest(network) for network in networks]
    })


@rest(GET, PORTS)
def get_ports(nb_db, content, id):
    ports = nb_db.ports
    return json.dumps({
        'ports': [PortMapper.row2rest(port) for port in ports]
    })


@rest(GET, SUBNETS)
def get_subnets(nb_db, content, id):
    return json.dumps({
        'subnets': ''
    })


@rest(DELETE, NETWORKS)
def delete_network(nb_db, content=None, id=None):
    if id is not None:
        nb_db.delete_network(id)


@rest(DELETE, PORTS)
def delete_port(nb_db, content=None, id=None):
    if id is not None:
        nb_db.delete_port(id)


@rest(DELETE, SUBNETS)
def delete_subnet(nb_db, content, id):
    pass


@rest(POST, NETWORKS)
def post_networks(nb_db, content, id):
    content_json = json.loads(content)
    received_network = content_json['network']
    network = nb_db.update_network(received_network)
    return json.dumps({'network': NetworkMapper.row2rest(network)})


@rest(POST, PORTS)
def post_ports(nb_db, content, id):
    content_json = json.loads(content)
    received_port = content_json['port']
    port = nb_db.update_port(received_port)
    return json.dumps({'port': PortMapper.row2rest(port)})


@rest(POST, SUBNETS)
def post_subnets(nb_db, content, id):
    return json.dumps({'subnet': ''})


@rest(PUT, PORTS)
def put_ports(nb_db, content, id):
    if not id:
        raise Exception('No port id in POST request')
    # For now, the PUT ports request does not update any relevant values
    # TODO: check if the PUT request changes are relevant later on
    result = nb_db.get_port(id)
    return json.dumps({'port': PortMapper.row2rest(result)})


@rest(GET, 'tech')
def get_debug(nb_db, content, id):
    networks = nb_db.get_networks()
    ports = nb_db.get_ports()
    response = json.dumps({
        'networks': [NetworkMapper.row2rest(network) for network in networks],
        'ports': [PortMapper.row2rest() for port in ports]
    })
    return response


def responses():
    return _responses
