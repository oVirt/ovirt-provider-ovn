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
import httplib
import logging
import urlparse

from six.moves.BaseHTTPServer import BaseHTTPRequestHandler

from auth import Forbidden
from auth import Unauthorized
from auth import Timeout

GET = 'GET'  # list of entities
SHOW = 'SHOW'  # concrete entity
DELETE = 'DELETE'
POST = 'POST'
PUT = 'PUT'

ERROR_MESSAGE = """\
{{
  "error": {{
    "message": "{}",
    "code": {},
    "title": "{}"
  }}
}}
"""

ERROR_CONTENT_TYPE = 'application/json'


class Response(object):
    def __init__(self, body=None, code=None, headers=None):
        self.body = body
        self.code = code
        self.headers = headers


class PathNotFoundError(AttributeError):
    pass


class ElementNotFoundError(AttributeError):
    pass


class BadRequestError(AttributeError):
    pass


class MethodNotAllowedError(AttributeError):
    pass


class BaseHandler(BaseHTTPRequestHandler):

    # Suppress static error message of BaseHTTPRequestHandler, because a
    # the individual error message ERROR_MESSAGE is sent.
    error_message_format = ''
    error_content_type = ERROR_CONTENT_TYPE

    # TODO: this is made configurable in a later patch

    def __init__(self, request, client_address, server):
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
        self._handle_request(DELETE, code=httplib.NO_CONTENT)

    def _handle_request(self, method, code=httplib.OK, content=None):
        logging.debug('Request: {} : {}'.format(method, self.path))
        if content:
            logging.debug('Request body:\n{}'.format(content))
        try:

            key, id = self._parse_request_path(self.path)
            self._validate_request(method, id)
            response = self.handle_request(
                method, key, id, content)
            self._process_response(response.body, response.code or code)
        except PathNotFoundError as e:
            message = 'Incorrect path: {}'.format(self.path)
            self._handle_response_exception(e, message=message,
                                            response_code=httplib.NOT_FOUND)
        except ElementNotFoundError as e:
            message = 'The element requested has not been found.'
            self._handle_response_exception(e, message=message,
                                            response_code=httplib.NOT_FOUND)
        except MethodNotAllowedError as e:
            message = 'Method not allowed: {}'.format(method)
            self._handle_response_exception(
                e, message=message, response_code=httplib.METHOD_NOT_ALLOWED)
        except BadRequestError as e:
            self._handle_response_exception(e,
                                            response_code=httplib.BAD_REQUEST)
        except Unauthorized as e:
            self._handle_response_exception(e,
                                            response_code=httplib.UNAUTHORIZED)
        except Forbidden as e:
            self._handle_response_exception(e, response_code=httplib.FORBIDDEN)
        except Timeout as e:
            self._handle_response_exception(
                e, response_code=httplib.GATEWAY_TIMEOUT)
        except Exception as e:
            self._handle_response_exception(e)

    def _validate_request(self, method, id):
        if method in [DELETE, PUT] and not id:
            raise BadRequestError(
                '{method} request must specify an id'.format(method=method)
            )

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

    def _handle_response_exception(
            self, e, message=None,
            response_code=httplib.INTERNAL_SERVER_ERROR):
        error_message = message if message else e.message
        logging.exception(error_message)
        self.send_error(response_code)
        self.wfile.write(ERROR_MESSAGE.format(
            error_message,
            response_code,
            httplib.responses[response_code]))

    @staticmethod
    def _parse_request_path(full_path):
        """
        The request path is split into the tree parts:
        /{version}/{key}/{id} .
        The {id} may be empty and is allowed to contain multiple slashes.
        Several subsequent slashes are subsumed to a single one.
        """
        full_path = urlparse.urlparse(full_path).path
        elements = filter(None, full_path.split('/'))
        key = elements[1] if len(elements) > 1 else ''
        id = '/'.join(elements[2:]) if len(elements) > 2 else ''
        return key, id

    @abc.abstractmethod
    def handle_request(self, method, key, id, content):
        """
        :return: An instance of Response
        """
        pass
