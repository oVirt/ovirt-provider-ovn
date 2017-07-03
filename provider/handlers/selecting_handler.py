# Copyright 2017 Red Hat, Inc.
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
from handlers.base_handler import NotFoundError
from handlers.base_handler import MethodNotAllowedError
from handlers.base_handler import Response


def rest(method, path, response_handlers):
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
        if path not in response_handlers:
            response_handlers[path] = {}
        response_handlers[path][method] = funct
        return funct
    return assign_response


class SelectingHandler(BaseHandler):

    # TODO: this is made configurable in a later patch

    def handle_request(self, method, key, id, content):
        response = self.call_response_handler(
            self._get_response_handler(method, key), content, id
        )
        if not isinstance(response, Response):
            return Response(body=response)
        return response

    @classmethod
    def _get_response_handler(cls, method, key):
        responses_for_key = cls.get_responses().get(key)
        if not responses_for_key:
            raise NotFoundError()
        response_handler = responses_for_key.get(method)
        if not response_handler:
            raise MethodNotAllowedError()
        return response_handler

    @abc.abstractmethod
    def call_response_handler(self, response_handler, content, id):
        pass

    @staticmethod
    def get_responses():
        raise NotImplementedError
