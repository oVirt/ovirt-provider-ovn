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
from __future__ import absolute_import

import mock
import pytest

from auth import init
from auth.plugin import Plugin


class ValidPlugin(Plugin):
    @staticmethod
    def create_token(user_at_domain, user_password):
        pass


class IncompletePlugin(Plugin):
    pass


class NoPlugin(object):
    @staticmethod
    def create_token(user_at_domain, user_password):
        pass


VALID_PLUGIN_NAME = '{}:{}'.format(__name__, ValidPlugin.__name__)
INCOMPLETE_PLUGIN_NAME = '{}:{}'.format(__name__, IncompletePlugin.__name__)
NO_PLUGIN_NAME = '{}:{}'.format(__name__, NoPlugin.__name__)


@mock.patch('auth.core.ovirt_provider_config.get',
            return_value=VALID_PLUGIN_NAME)
def test_auth_core_init_valid(mock_get):
    init()


@mock.patch('auth.core.ovirt_provider_config.get',
            return_value=INCOMPLETE_PLUGIN_NAME)
def test_auth_core_init_incomplete(mock_get):
    with pytest.raises(TypeError):
        init()


@mock.patch('auth.core.ovirt_provider_config.get',
            return_value=NO_PLUGIN_NAME)
def test_auth_core_init_no_plugin(mock_get):
    with pytest.raises(AssertionError):
        init()
