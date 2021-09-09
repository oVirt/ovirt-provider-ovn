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
#
from __future__ import absolute_import

import json

from handlers.base_handler import POST
from handlers.selecting_handler import SelectingHandler
from handlers.keystone_responses import responses


class TokenHandler(SelectingHandler):

    OBFUSCATED_PASSWORD = '<PASSWORD_HIDDEN>'

    def call_response_handler(self, response_handler, content, parameters):
        return response_handler(content, parameters)

    @staticmethod
    def get_responses():
        return responses()

    def _format_content_for_log(self, method, path, content):
        if method == POST and 'tokens' in path:
            try:
                content_json = json.loads(content)
                credentials = content_json['auth']['passwordCredentials']
                credentials['password'] = TokenHandler.OBFUSCATED_PASSWORD
                return json.dumps(content_json)
            except (Exception,):
                pass
        return content
