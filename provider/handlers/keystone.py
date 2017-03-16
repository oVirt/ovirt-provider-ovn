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
#
from __future__ import absolute_import

from handlers.base_handler import BaseHandler
from handlers.base_handler import IncorrectRequestError
from handlers.keystone_responses import responses


# TODO: authentication to be implemented
# This is just a placeholder
class TokenHandler(BaseHandler):

    def handle_request(self, method, key, id, content):
        response_handler = self._get_response_handler(method, key)
        return response_handler(content, id)

    @staticmethod
    def _get_response_handler(method, key):
        keystone_responses_for_method = responses().get(method)
        if not keystone_responses_for_method:
            raise IncorrectRequestError()
        response_handler = keystone_responses_for_method.get(key)
        if not response_handler:
            raise IncorrectRequestError()
        return response_handler
