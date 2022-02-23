# Copyright 2016-2021 Red Hat, Inc.
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

from handlers.base_handler import GET
from handlers.base_handler import DELETE
from handlers.base_handler import POST
from handlers.base_handler import PUT
from handlers.base_handler import Response

from handlers.responses_utils import get_entity
from handlers.selecting_handler import rest
from ovirt_provider_config_common import neutron_url_with_version


NETWORK_ID = 'network_id'
PORT_ID = 'port_id'
SUBNET_ID = 'subnet_id'
ROUTER_ID = 'router_id'
SECURITY_GROUP_ID = 'security_group_id'
SECURITY_GROUP_RULE_ID = 'security_group_rule_id'
ALIAS = 'alias'

NETWORKS = 'networks'
NETWORK_ENTITY = 'networks/{network_id}'
PORTS = 'ports'
PORT_ENTITY = 'ports/{port_id}'
SUBNETS = 'subnets'
SUBNET_ENTITY = 'subnets/{subnet_id}'
ROUTERS = 'routers'
ROUTER_ENTITY = 'routers/{router_id}'
SECURITY_GROUPS = 'security-groups'
SECURITY_GROUP_ENTITY = 'security-groups/{security_group_id}'
ADD_ROUTER_INTERFACE = 'routers/{router_id}/add_router_interface'
DELETE_ROUTER_INTERFACE = 'routers/{router_id}/remove_router_interface'
SECURITY_GROUP_RULES = 'security-group-rules'
SECURITY_GROUP_RULE_ENTITY = 'security-group-rules/{security_group_rule_id}'
EXTENSIONS = 'extensions'
EXTENSION_ENTITY = 'extensions/{alias}'

FLOATINGIPS = 'floatingips'


_responses = {}


@rest(GET, NETWORK_ENTITY, _responses)
def show_network(nb_db, content, parameters):
    return Response({'network': nb_db.get_network(parameters[NETWORK_ID])})


@rest(GET, PORT_ENTITY, _responses)
def show_port(nb_db, content, parameters):
    return Response({'port': nb_db.get_port(parameters[PORT_ID])})


@rest(GET, SUBNET_ENTITY, _responses)
def show_subnet(nb_db, content, parameters):
    return Response({'subnet': nb_db.get_subnet(parameters[SUBNET_ID])})


@rest(GET, '', _responses)
def get_default(nb_db, content, parameters):
    return Response(
        {
            'versions': [
                {
                    'status': 'CURRENT',
                    'id': 'v2.0',
                    'links': [
                        {'href': neutron_url_with_version(), 'rel': 'self'}
                    ],
                }
            ]
        }
    )


@rest(GET, EXTENSIONS, _responses)
def get_extensions(nb_db, content, parameters):
    return Response({'extensions': nb_db.list_extensions()})


@rest(GET, EXTENSION_ENTITY, _responses)
def show_extension(nb_db, content, parameters):
    nb_db.get_extension(parameters[ALIAS])
    return Response()


@rest(GET, NETWORKS, _responses)
def get_networks(nb_db, content, parameters):
    networks = nb_db.list_networks()
    return Response({'networks': networks})


@rest(GET, PORTS, _responses)
def get_ports(nb_db, content, parameters):
    ports = nb_db.list_ports()
    return Response({'ports': ports})


@rest(GET, SUBNETS, _responses)
def get_subnets(nb_db, content, parameters):
    return Response({'subnets': nb_db.list_subnets()})


@rest(DELETE, NETWORK_ENTITY, _responses)
def delete_network(nb_db, content, parameters):
    nb_db.delete_network(parameters[NETWORK_ID])
    return Response()


@rest(DELETE, PORT_ENTITY, _responses)
def delete_port(nb_db, content, parameters):
    nb_db.delete_port(parameters[PORT_ID])
    return Response()


@rest(DELETE, SUBNET_ENTITY, _responses)
def delete_subnet(nb_db, content, parameters):
    nb_db.delete_subnet(parameters[SUBNET_ID])
    return Response()


@rest(POST, NETWORKS, _responses)
def post_networks(nb_db, content, parameters):
    received_network = get_entity(content, 'network')
    network = nb_db.add_network(received_network)
    return Response({'network': network})


@rest(POST, PORTS, _responses)
def post_ports(nb_db, content, parameters):
    received_port = get_entity(content, 'port')
    port = nb_db.add_port(received_port)
    return Response({'port': port})


@rest(POST, SUBNETS, _responses)
def post_subnets(nb_db, content, parameters):
    received_subnet = get_entity(content, 'subnet')
    subnet = nb_db.add_subnet(received_subnet)
    return Response({'subnet': subnet})


@rest(PUT, NETWORK_ENTITY, _responses)
def put_network(nb_db, content, parameters):
    received_network = get_entity(content, 'network')
    network = nb_db.update_network(received_network, parameters[NETWORK_ID])
    return Response({'network': network})


@rest(PUT, PORT_ENTITY, _responses)
def put_ports(nb_db, content, parameters):
    received_port = get_entity(content, 'port')
    port = nb_db.update_port(received_port, parameters[PORT_ID])
    return Response({'port': port})


@rest(PUT, SUBNET_ENTITY, _responses)
def put_subnets(nb_db, content, parameters):
    received_subnet = get_entity(content, 'subnet')
    subnet = nb_db.update_subnet(received_subnet, parameters[SUBNET_ID])
    return Response({'subnet': subnet})


@rest(GET, 'tech', _responses)
def get_debug(nb_db, content, parameters):
    networks = nb_db.list_networks()
    ports = nb_db.list_ports()
    subnets = nb_db.list_subnets()
    routers = nb_db.list_routers()
    return Response(
        {
            'networks': networks,
            'ports': ports,
            'subnets': subnets,
            'routers': routers,
        }
    )


@rest(GET, ROUTERS, _responses)
def get_routers(nb_db, content, parameters):
    return Response({'routers': nb_db.list_routers()})


@rest(POST, ROUTERS, _responses)
def post_routers(nb_db, content, parameters):
    content_json = json.loads(content)
    received_router = content_json['router']
    router = nb_db.add_router(received_router)
    return Response({'router': router})


@rest(GET, ROUTER_ENTITY, _responses)
def get_router(nb_db, content, parameters):
    return Response({'router': nb_db.get_router(parameters[ROUTER_ID])})


@rest(PUT, ROUTER_ENTITY, _responses)
def put_router(nb_db, content, parameters):
    content_json = json.loads(content)
    received_router = content_json['router']
    router = nb_db.update_router(received_router, parameters[ROUTER_ID])
    return Response({'router': router})


@rest(DELETE, ROUTER_ENTITY, _responses)
def delete_router(nb_db, content, parameters):
    nb_db.delete_router(parameters[ROUTER_ID])
    return Response()


@rest(PUT, ADD_ROUTER_INTERFACE, _responses)
def put_add_router_inerface(nb_db, content, parameters):
    result = nb_db.add_router_interface(
        get_entity(content), parameters[ROUTER_ID]
    )
    return Response(result)


@rest(PUT, DELETE_ROUTER_INTERFACE, _responses)
def put_remove_router_interface(nb_db, content, parameters):
    result = nb_db.delete_router_interface(
        get_entity(content), parameters[ROUTER_ID]
    )
    return Response(result)


@rest(GET, FLOATINGIPS, _responses)
def get_floating_ips(nb_db, content, parameters):
    return Response({'floatingips': []})


@rest(GET, SECURITY_GROUPS, _responses)
def get_security_groups(nb_db, content, parameters):
    return Response({'security_groups': nb_db.list_security_groups()})


@rest(GET, SECURITY_GROUP_ENTITY, _responses)
def show_security_group(nb_db, content, parameters):
    return Response(
        {
            'security_group': nb_db.get_security_group(
                parameters[SECURITY_GROUP_ID]
            )
        }
    )


@rest(POST, SECURITY_GROUPS, _responses)
def post_security_groups(nb_db, content, parameters):
    sec_group = get_entity(content, 'security_group')
    sec_group_data = nb_db.add_security_group(sec_group)
    return Response({'security_group': sec_group_data})


@rest(DELETE, SECURITY_GROUP_ENTITY, _responses)
def delete_security_group(nb_db, content, parameters):
    nb_db.delete_security_group(parameters[SECURITY_GROUP_ID])
    return Response()


@rest(PUT, SECURITY_GROUP_ENTITY, _responses)
def put_security_group(nb_db, content, parameters):
    received_security_group = get_entity(content, 'security_group')
    sec_group = nb_db.update_security_group(
        received_security_group, parameters[SECURITY_GROUP_ID]
    )
    return Response({'security_group': sec_group})


@rest(GET, SECURITY_GROUP_RULES, _responses)
def get_security_group_rules(nb_db, content, parameters):
    return Response(
        {'security_group_rules': nb_db.list_security_group_rules()}
    )


@rest(GET, SECURITY_GROUP_RULE_ENTITY, _responses)
def show_security_group_rule(nb_db, content, parameters):
    return Response(
        {
            'security_group_rule': nb_db.get_security_group_rule(
                parameters[SECURITY_GROUP_RULE_ID]
            )
        }
    )


@rest(POST, SECURITY_GROUP_RULES, _responses)
def post_security_group_rule(nb_db, content, parameters):
    received_sec_group_rule = get_entity(content, 'security_group_rule')
    return Response(
        {
            'security_group_rule': nb_db.add_security_group_rule(
                received_sec_group_rule
            )
        }
    )


@rest(DELETE, SECURITY_GROUP_RULE_ENTITY, _responses)
def delete_security_group_rule(nb_db, content, parameters):
    nb_db.delete_security_group_rule(parameters[SECURITY_GROUP_RULE_ID])
    return Response()


def responses():
    return _responses
