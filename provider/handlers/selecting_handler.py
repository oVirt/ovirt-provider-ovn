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
from handlers.base_handler import IncorrectRequestError


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
        if method not in response_handlers:
            response_handlers[method] = {}
        response_handlers[method][path] = funct
        return funct
    return assign_response


class SelectingHandler(BaseHandler):

    # TODO: this is made configurable in a later patch

    def handle_request(self, method, key, id, content):
        return self.call_response_handler(
            self._get_response_handler(method, key), content, id)

    @classmethod
    def _get_response_handler(cls, method, key):
        responses_for_method = cls.get_responses().get(method)
        if not responses_for_method:
            raise IncorrectRequestError()
        response_handler = responses_for_method.get(key)
        if not response_handler:
            raise IncorrectRequestError()
        return response_handler

    @abc.abstractmethod
    def call_response_handler(self, response_handler, content, id):
        pass

    @staticmethod
    def get_responses():
        raise NotImplementedError
