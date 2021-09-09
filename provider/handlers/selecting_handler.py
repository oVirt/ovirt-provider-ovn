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

import abc

from handlers.base_handler import BaseHandler
from handlers.base_handler import PathNotFoundError
from handlers.base_handler import MethodNotAllowedError


PATH_SEPARATOR = '/'
RESPONSE_VALUE_KEY = '#VALUE'
RESPONSE_VALUE_PARAMETER = '#PARAMETER'
WILDCARD_KEY = '*'


def rest(method, path, response_handlers):
    """
    Decorator for adding rest request handling methods.
    method -- rest method of the arriving request: GET/POST/DELETE/PUT
    path -- the path of the arriving request

    For example the function handling the following request:
    GET: http://<host>/../networks/<network_id>/other/<other_id>
    (where <network_id> and <other_id> are variables)
    would have to be decorated with:
    rest('GET', 'networks/{network_id}/other/{other_id}')

    Based on the method (GET) and path('networks/{network_id}/other/
    {other_id}') new elements would be added to the response_handlers map.

    For each constant part of the path, like 'networks' and 'other' in the
    above decorator, a new map under the key equal to the name of the part is
    added. For 'networks' this would be:
        'networks': {}

    For a parameter, like {network_id} or {other_id}, the following structure
    is added:
        '#PARAMETER': {
            'network_id': {}
        }
    The '#PARAMETER' indicates that we deal with a variable. This two level
    approach is used to make lookup easier. Otherwise during lookup we would
    have to iterate over all the key to check if any of them is a parameter
    (the value received from the http request is a variable and can not be
    used as a key). The '#PARAMETER' allows us to retrieve the value by just
    using it as a key.
    Note that the map pointed to by '#PARAMETER' can only have one child node
    (only one parameter) to avoid ambiguity.

    After mapping the entire path, the last element in the tree is the http
    method (GET, POST, PUT, DELETE). The end of the path is marked by the
    '#VALUE' token. For example, for the above path this would be:
        '#VALUE': {
            'GET': handler_function1
            }
        }

    As an example, the data structure resulting from the @rest decorators
    below:
    @rest('GET', 'networks/{network_id}/other/{other_id}')
    def handler_function1

    @rest('POST', 'networks/{network_id}/other/{other_id}')
    def handler_function2

    @rest('GET', 'port')
    handler_function3

    will be as follows:
    response_handlers = {
        'port:' {
            '#VALUE': {
                'GET': handler_function3,
                }
            }
        },
        'networks': {
            '#PARAMETER': {
                'network_id':
                    'other':{
                        '#PARAMETER': {
                            'other_id': {
                                '#VALUE': {
                                    'GET': handler_function1,
                                    'POST': handler_function2
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    def assign_response(funct):
        parameters = []
        current_map = response_handlers
        i = 1
        path_parts = path.split(PATH_SEPARATOR)
        parts_length = len(path_parts)
        for part in path_parts:
            parameter = _get_parameter_name(part)
            if parameter:
                _validate_path_parameters(parameter, parameters, current_map)
                if not current_map.get(RESPONSE_VALUE_PARAMETER):
                    current_map[RESPONSE_VALUE_PARAMETER] = {}
                if not current_map[RESPONSE_VALUE_PARAMETER].get(parameter):
                    current_map[RESPONSE_VALUE_PARAMETER][parameter] = {}
                current_map = current_map[RESPONSE_VALUE_PARAMETER][parameter]
            else:
                if part not in current_map:
                    current_map[part] = {}
                current_map = current_map[part]
            if i == parts_length:
                if RESPONSE_VALUE_KEY not in current_map:
                    current_map[RESPONSE_VALUE_KEY] = {}
                current_map = current_map[RESPONSE_VALUE_KEY]
                assert method not in current_map, 'Duplicated REST path'
                current_map[method] = funct

                return funct
            i += 1
        assert False, 'Error parsing REST responses.'

    return assign_response


def _validate_path_parameters(parameter, parameters, current_map):
    duplicate_param_message = (
        'Duplicate parameter name: {name}. Parameter names within'
        ' a path must be unique.'.format(name=parameter)
    )
    assert parameter not in parameters, duplicate_param_message

    parameters.append(parameter)
    existing_params = current_map.get(RESPONSE_VALUE_PARAMETER)
    has_duplicated_params = existing_params and not existing_params.get(
        parameter
    )
    duplicate_param_in_path_message = (
        'Unable to add more than one unique parameter for path'
    )
    assert not has_duplicated_params, duplicate_param_in_path_message


def _get_parameter_name(part):
    if len(part) > 2 and part[0] == '{' and part[-1] == '}':
        return part[1:-1]


class SelectingHandler(BaseHandler):
    def handle_request(self, method, path_parts, content):
        handler, parameters = self.get_response_handler(
            self.get_responses(), method, path_parts
        )
        return self.call_response_handler(handler, content, parameters)

    @classmethod
    def get_response_handler(cls, responses, method, path_parts):
        parameters = {}
        current_map = responses
        for part in path_parts:
            if part in current_map:
                current_map = current_map[part]
            elif RESPONSE_VALUE_PARAMETER in current_map:
                current_map = current_map[RESPONSE_VALUE_PARAMETER]
                key = list(current_map.keys())[0]
                assert key, 'Expected parameter name is missing'
                current_map = current_map[key]
                parameters[key] = part
            elif WILDCARD_KEY in current_map:
                current_map = current_map[WILDCARD_KEY]
            else:
                raise PathNotFoundError()

        if RESPONSE_VALUE_KEY not in current_map:
            raise PathNotFoundError()

        method_map = current_map[RESPONSE_VALUE_KEY]
        if method not in method_map:
            raise MethodNotAllowedError()
        return method_map[method], parameters

    @abc.abstractmethod
    def call_response_handler(self, response_handler, content, parameters):
        pass

    @staticmethod
    def get_responses():
        raise NotImplementedError
