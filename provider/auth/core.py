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

import importlib
import logging

from ovirt_provider_config_common import auth_plugin
from .plugin import Plugin


TOKEN_HTTP_HEADER_FIELD_NAME = 'X-Auth-Token'

plugin = None


def init():
    global plugin
    plugin = _load_plugin(auth_plugin())


def _load_plugin(plugin_name):
    try:
        module_name, class_name = plugin_name.rsplit(':', 1)
        plugin_class = getattr(
            importlib.import_module(module_name), class_name
        )
        try:
            assert issubclass(plugin_class, Plugin)
            return plugin_class()
        except TypeError as e:
            logging.error(
                "Auth plugin '%s' is of wrong type: %s",
                plugin_class.__name__,
                e,
            )
            raise e
    except Exception as e:
        logging.error("Unable to load auth plugin '%s'", plugin_name)
        raise e


def plugin_loaded():
    global plugin
    if not plugin:
        raise AttributeError('No auth plugin loaded')
