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

from six.moves.BaseHTTPServer import BaseHTTPRequestHandler

import logging

import ovirt_provider_config
from neutron_responses import DELETE
from neutron_responses import GET
from neutron_responses import POST
from neutron_responses import PUT
from neutron_responses import SHOW
from neutron_responses import responses
from ovndb.ndb_api import OvnNbDb


OVN_REMOTE_AT_LOCALHOST = 'tcp:127.0.0.1:6641'


class IncorrectRequestError(AttributeError):
    pass


class NeutronHandler(BaseHTTPRequestHandler):

    # TODO: this is made configurable in a later patch

    def __init__(self, request, client_address, server):
        self.response_handler = ResponseHandler(self._remote())
        self._run_server(request, client_address, server)

    def _run_server(self, request, client_address, server):
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def do_GET(self):
        self._handle_request(SHOW if self._parse_request_path(self.path)[1]
                             else GET)

    def do_POST(self):
        self._handle_request(POST, content=self._get_content())

    def do_PUT(self):
        self._handle_request(PUT, content=self._get_content())

    def do_DELETE(self):
        assert self._parse_request_path(self.path)[1], ('Delete request must'
                                                        'specify an id')
        self._handle_request(DELETE, code=204)

    def _handle_request(self, method, code=200, content=None):
        logging.debug('Request: {} : {}'.format(method, self.path))
        if content:
            logging.debug('Request body:\n{}'.format(content))
        try:

            key, id = self._parse_request_path(self.path)
            response = self.response_handler.handle_request(method, key, id,
                                                            content)
            self._process_response(response, code)
        except IncorrectRequestError as e:
            message = 'Incorrect path: {}: {}'.format(self.path)
            self._handle_response_exception(e, message=message,
                                            response_code=404)
        except Exception as e:
            self._handle_response_exception(e)

    def _process_response(self, response, response_code):
        self._set_response_headers(response_code, response)
        logging.debug('Response code: {}'.format(response_code))
        if response:
            logging.debug('Response body: {}'.format(response))
            self.wfile.write(response)

    def _get_content(self):
        content_length = int(self.headers['Content-Length'])
        content = self.rfile.read(content_length)
        return content

    def _set_response_headers(self, response_code, response):
        self.send_response(response_code)
        if response:
            self.send_header('Content-Type', 'application/json')
        self.end_headers()

    def _handle_response_exception(self, e, message=None, response_code=500):
        if message:
            logging.error(message)
        else:
            logging.exception(e)
        self.send_error(response_code)
        self.end_headers()
        self.wfile.write('Error:\n{}'.format(message if message else e))

    @staticmethod
    def _parse_request_path(full_path):
        """
        The request path looks like: "/v2.0/*" example: "/v2.0/networks".
        We are only interested in the * part
        """
        path = full_path[6:] if len(full_path) >= 6 else None
        key, id = path.split('/', 1) if '/' in path else (path, None)
        return key, id

    @staticmethod
    def _remote():
        return ovirt_provider_config.get('OVN REMOTE', 'ovn-remote',
                                         OVN_REMOTE_AT_LOCALHOST)


class ResponseHandler(object):

    def __init__(self, remote):
        self.remote = remote

    def handle_request(self, method, key, id, content):
        response_handler = self._get_response_handler(method, key)
        with OvnNbDb(self.remote) as nb_db:
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
