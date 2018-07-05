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
import json as libjson
import logging
import urlparse

from six.moves.BaseHTTPServer import BaseHTTPRequestHandler

from auth import BadGateway
from auth import Forbidden
from auth import Unauthorized
from auth import Timeout
from handlers.query_filter import filter_query_results

GET = 'GET'
DELETE = 'DELETE'
POST = 'POST'
PUT = 'PUT'
JSON_SUFFIX = '.json'

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
    def __init__(self, json=None, code=None, headers=None):
        self.body = json
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


class ConflictError(AttributeError):
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
        self._handle_request(GET, code=httplib.OK)

    def do_POST(self):
        self._handle_request(POST, content=self._get_content(),
                             code=httplib.CREATED)

    def do_PUT(self):
        self._handle_request(PUT, content=self._get_content(),
                             code=httplib.OK)

    def do_DELETE(self):
        self._handle_request(DELETE, code=httplib.NO_CONTENT)

    def _format_content_for_log(self, method, path, content):
        return content

    def _log_request(self, method, path, content, log_level=logging.DEBUG):
        logging.log(
            log_level,
            'From: {address}:{port} Request: {method} {path}'.format(
              address=self.client_address[0], port=self.client_address[1],
              method=method, path=path
            ))
        if content:
            logging.log(
                log_level,
                'Request body:\n{}'.format(
                    self._format_content_for_log(method, path, content)
                ))

    def _handle_request(self, method, code=httplib.OK, content=None):
        self._log_request(method, self.path, content)
        try:
            path_parts, query = self._parse_request_path(self.path)
            self._validate_request(method, id)
            response = self.handle_request(
                method, path_parts, content
            )
            result = filter_query_results(
                response.body, query, path_parts
            ) if method == GET else response.body

            body = libjson.dumps(result) if result else None
            self._process_response(body, response.code or code)
        except PathNotFoundError as e:
            message = 'Incorrect path: {}'.format(self.path)
            self._handle_response_exception(
                e, method, self.path, content, message=message,
                response_code=httplib.NOT_FOUND
            )
        except ElementNotFoundError as e:
            message = 'The element requested has not been found.'
            self._handle_response_exception(
                e, method, self.path, content, message=message,
                response_code=httplib.NOT_FOUND
            )
        except MethodNotAllowedError as e:
            message = 'Method not allowed: {}'.format(method)
            self._handle_response_exception(
                e, method, self.path, content, message=message,
                response_code=httplib.METHOD_NOT_ALLOWED
            )
        except BadRequestError as e:
            self._handle_response_exception(
                e, method, self.path, content,
                response_code=httplib.BAD_REQUEST
            )
        except Unauthorized as e:
            self._handle_response_exception(
                e, method, self.path, content,
                response_code=httplib.UNAUTHORIZED
            )
        except Forbidden as e:
            self._handle_response_exception(
                e, method, self.path, content, response_code=httplib.FORBIDDEN
            )
        except Timeout as e:
            self._handle_response_exception(
                e, method, self.path, content,
                response_code=httplib.GATEWAY_TIMEOUT
            )
        except BadGateway as e:
            self._handle_response_exception(
                e, method, self.path, content,
                response_code=httplib.BAD_GATEWAY
            )
        except ConflictError as e:
            self._handle_response_exception(
                e, method, self.path, content, response_code=httplib.CONFLICT
            )
        except NotImplementedError as e:
            self._handle_response_exception(
                e, method, self.path, content,
                response_code=httplib.NOT_IMPLEMENTED
            )
        except Exception as e:
            self._handle_response_exception(e, method, self.path, content)

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
        self, e, method, path, content=None, message=None,
        response_code=httplib.INTERNAL_SERVER_ERROR,
    ):
        self._log_request(method, path, content, log_level=logging.ERROR)
        error_message = e.message or message
        logging.exception(error_message)
        self.send_error(response_code)
        self.wfile.write(ERROR_MESSAGE.format(
            error_message,
            response_code,
            httplib.responses[response_code]))

    @staticmethod
    def _parse_request_path(full_path):
        parsed_path = urlparse.urlparse(full_path)
        query = urlparse.parse_qs(parsed_path.query)
        query_path = BaseHandler._remove_json_extension(parsed_path.path)
        elements = filter(None, query_path.split('/'))[1:]
        if not elements:
            elements.append('')
        return elements, query

    @staticmethod
    def _remove_json_extension(path):
        if path and path.lower().endswith(JSON_SUFFIX):
            path = path[: - len(JSON_SUFFIX)]
        return path

    @abc.abstractmethod
    def handle_request(self, method, path_parts, content):
        """
        :return: An instance of Response
        """
        pass
