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

import httplib
import json

from handlers.base_handler import GET
from handlers.base_handler import SHOW
from handlers.base_handler import DELETE
from handlers.base_handler import POST
from handlers.base_handler import PUT
from handlers.base_handler import Response

from handlers.selecting_handler import rest
from ovirt_provider_config_common import neutron_url


NETWORKS = 'networks'
PORTS = 'ports'
SUBNETS = 'subnets'


_responses = {}


@rest(SHOW, NETWORKS, _responses)
def show_network(nb_db, content, id=None):
    return json.dumps({
        'network': nb_db.get_network(id)
    })


@rest(SHOW, PORTS, _responses)
def show_port(nb_db, content, id=None):
    return json.dumps({
        'port': nb_db.get_port(id)
    })


@rest(SHOW, SUBNETS, _responses)
def show_subnet(nb_db, content, id):
    return json.dumps({
        'subnet': nb_db.get_subnet(id) if id else None
    })


@rest(GET, '', _responses)
def get_default(nb_db, content, id):
    return json.dumps({
        'versions': [{
            'status': 'CURRENT',
            'id': 'v2.0',
            'links': [{
                'href': neutron_url(),
                'rel': 'self'
            }]
        }]
    })


@rest(GET, NETWORKS, _responses)
def get_networks(nb_db, conten, id):
    networks = nb_db.list_networks()
    return json.dumps({
        'networks': networks
    })


@rest(GET, PORTS, _responses)
def get_ports(nb_db, content, id):
    ports = nb_db.list_ports()
    return json.dumps({
        'ports': ports
    })


@rest(GET, SUBNETS, _responses)
def get_subnets(nb_db, content, id):
    return json.dumps({
        'subnets': nb_db.list_subnets()
    })


@rest(DELETE, NETWORKS, _responses)
def delete_network(nb_db, content=None, id=None):
    if id is not None:
        nb_db.delete_network(id)


@rest(DELETE, PORTS, _responses)
def delete_port(nb_db, content=None, id=None):
    if id is not None:
        nb_db.delete_port(id)


@rest(DELETE, SUBNETS, _responses)
def delete_subnet(nb_db, content, id):
    if id is not None:
        nb_db.delete_subnet(id)


@rest(POST, NETWORKS, _responses)
def post_networks(nb_db, content, id):
    content_json = json.loads(content)
    received_network = content_json['network']
    network = nb_db.add_network(received_network)
    return Response(
        body=json.dumps({'network': network}),
        code=httplib.CREATED
    )


@rest(POST, PORTS, _responses)
def post_ports(nb_db, content, id):
    content_json = json.loads(content)
    received_port = content_json['port']
    port = nb_db.add_port(received_port)
    return Response(
        body=json.dumps({'port': port}),
        code=httplib.CREATED
    )


@rest(POST, SUBNETS, _responses)
def post_subnets(nb_db, content, id):
    received_subnet = json.loads(content)['subnet']
    subnet = nb_db.add_subnet(received_subnet)
    return Response(
        body=json.dumps({'subnet': subnet}),
        code=httplib.CREATED
    )


@rest(PUT, NETWORKS, _responses)
def put_network(nb_db, content, id):
    content_json = json.loads(content)
    received_network = content_json['network']
    network = nb_db.update_network(received_network, id)
    return Response(
        body=json.dumps({'network': network}),
        code=httplib.OK
    )


@rest(PUT, PORTS, _responses)
def put_ports(nb_db, content, id):

    content_json = json.loads(content)
    received_port = content_json['port']
    port = nb_db.update_port(received_port, id)
    return Response(
        body=json.dumps({'port': port}),
        code=httplib.OK
    )

    # if not id:
    #    raise Exception('No port id in POST request')

    # REQUIRED_FOR Engine < 4.1
    # older Engine does not pass mac_address here
    # mac = json.loads(content)['port'].get('mac_address')
    # if mac:
    #    nb_db.update_port_mac(id, mac)
    # result = nb_db.get_port(id)
    # return json.dumps({'port': result})


@rest(PUT, SUBNETS, _responses)
def put_subnets(nb_db, content, id):
    received_subnet = json.loads(content)['subnet']
    subnet = nb_db.update_subnet(received_subnet, id)
    return Response(
        body=json.dumps({'subnet': subnet}),
        code=httplib.OK
    )


@rest(GET, 'tech', _responses)
def get_debug(nb_db, content, id):
    networks = nb_db.list_networks()
    ports = nb_db.list_ports()
    response = json.dumps({
        'networks': [network for network in networks],
        'ports': [port for port in ports]
    })
    return response


def responses():
    return _responses
