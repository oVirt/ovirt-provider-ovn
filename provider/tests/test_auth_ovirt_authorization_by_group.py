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
from mock import ANY


from auth.plugins.ovirt import AuthorizationByGroup

TOKEN = 'the_secret_token'


ENGINE_ADMIN_GROUP_ATTRIBUTE_NAME = 'AAA_AUTHZ_GROUP_NAME'
ENGINE_ADMIN_GROUP_ATTRIBUTE_VALUE = 'NetAdmin'

INFO_VALID = {
    'active': True,
    'ovirt': ['java.util.HashMap',
              {
                  'group_ids': ['java.util.ArrayList', [
                      ['org.ovirt.engine.api.extensions.ExtMap', {
                          ENGINE_ADMIN_GROUP_ATTRIBUTE_NAME:
                              ENGINE_ADMIN_GROUP_ATTRIBUTE_VALUE}],
                      ['org.ovirt.engine.api.extensions.ExtMap', {
                          ENGINE_ADMIN_GROUP_ATTRIBUTE_NAME: 'otherGroup',
                      }]]],
              }]
}

INFO_INVALID = {
    'active': True,
    'ovirt': ['java.util.HashMap',
              {
                  'group_ids': ['java.util.ArrayList', [
                      ['org.ovirt.engine.api.extensions.ExtMap', {
                          ENGINE_ADMIN_GROUP_ATTRIBUTE_NAME: 'otherGroup',
                      }]]],
              }]
}


def provider_config_get(section, key, default):
    if key == 'admin-group-atrribute-name':
        return ENGINE_ADMIN_GROUP_ATTRIBUTE_NAME
    elif key == 'admin-group-attribute-value':
        return ENGINE_ADMIN_GROUP_ATTRIBUTE_VALUE
    else:
        return default


@mock.patch(
    'auth.plugins.ovirt.authorization_by_group.get_token_info',
    return_value=INFO_VALID, autospec=True)
@mock.patch(
    'auth.plugins.ovirt.authorization_by_group.ovirt_provider_config.get',
    side_effect=provider_config_get, autospec=True)
def test_validate_token_success(mock_provider_config_get, mock_get_token_info):
    authorizationByGroup = AuthorizationByGroup()
    assert authorizationByGroup.validate_token(TOKEN)
    mock_get_token_info.assert_called_once_with(ca_file=ANY, client_id=ANY,
                                                client_secret=ANY,
                                                engine_url=ANY, token=TOKEN,
                                                timeout=ANY)


@mock.patch(
    'auth.plugins.ovirt.authorization_by_group.get_token_info',
    return_value=INFO_INVALID, autospec=True)
@mock.patch(
    'auth.plugins.ovirt.authorization_by_group.ovirt_provider_config.get',
    side_effect=provider_config_get, autospec=True)
def test_validate_token_fail(mock_provider_config_get, mock_get_token_info):
    authorizationByGroup = AuthorizationByGroup()
    assert not authorizationByGroup.validate_token(TOKEN)
    mock_get_token_info.assert_called_once_with(ca_file=ANY, client_id=ANY,
                                                client_secret=ANY,
                                                engine_url=ANY, token=TOKEN,
                                                timeout=ANY)
