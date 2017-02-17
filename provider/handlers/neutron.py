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
from handlers.neutron_responses import responses
import ovirt_provider_config
from ovndb.ndb_api import OvnNbDb


OVN_REMOTE_AT_LOCALHOST = 'tcp:127.0.0.1:6641'


class IncorrectRequestError(AttributeError):
    pass


class NeutronHandler(BaseHandler):

    # TODO: this is made configurable in a later patch

    def __init__(self, request, client_address, server):
        BaseHandler.__init__(self, request, client_address, server)

    def handle_request(self, method, key, id, content):
        response_handler = self._get_response_handler(method, key)
        with OvnNbDb(self. _remote()) as nb_db:
            return response_handler(nb_db, content, id)

    @staticmethod
    def _get_response_handler(method, key):
        neutron_responses_for_method = responses().get(method)
        if not neutron_responses_for_method:
            raise IncorrectRequestError()
        response_handler = neutron_responses_for_method.get(key)
        if not response_handler:
            raise IncorrectRequestError()
        return response_handler

    @staticmethod
    def _remote():
        return ovirt_provider_config.get('OVN REMOTE', 'ovn-remote',
                                         OVN_REMOTE_AT_LOCALHOST)
