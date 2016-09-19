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

GET = 'GET'  # list of entities
SHOW = 'SHOW'  # concrete entity
DELETE = 'DELETE'
POST = 'POST'
PUT = 'PUT'

NETWORKS = 'networks'
PORTS = 'ports'
SUBNETS = 'subnets'

_responses = {}


def responses():
    return _responses


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
