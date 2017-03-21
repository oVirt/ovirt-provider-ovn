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

from auth.plugins.ovirt import AuthorizationByRole

TOKEN = 'the_secret_token'

PROFILES = [{
    'authn_name': 'internal',
    'authz_name': 'internal-authz'
}]

INFO = {
    'user_id': 'netadmin@internal',
    'active': True,
    'ovirt': [
        'java.util.HashMap',
        {
            'principal_id': '1222a19d-e081-437c-be68-d18d36341222'
        }
    ]
}


DOMAIN_ENTRY_ID = \
    '31323232613139642D653038312D343337632D626536382D643138643336333431323232'

USER = {
    'domain_entry_id': DOMAIN_ENTRY_ID,
    'link': [{
        'href': '/ovirt-engine/api/users/USER_ID/roles',
        'rel': 'roles'
    }]
}

USERS = [USER]

ROLE_0 = {'id': 'def00021-0000-0000-0000-def000000015'}

ROLE_1 = {'id': 'def00005-0000-0000-0000-def000000005'}

ROLES_VALID = [ROLE_0, ROLE_1]

ROLES_INVALID = [ROLE_0]


@mock.patch('auth.plugins.ovirt.authorization_by_role.get_token_info',
            return_value=INFO, autospec=True)
@mock.patch('auth.plugins.ovirt.authorization_by_role.get_profiles',
            return_value=PROFILES, autospec=True)
@mock.patch('auth.plugins.ovirt.authorization_by_role.search_request',
            return_value=USERS, autospec=True)
@mock.patch('auth.plugins.ovirt.authorization_by_role.follow_link',
            return_value=ROLES_VALID, autospec=True)
def test_validate_token_success(mock_follow_link, mock_search,
                                mock_get_profiles, mock_get_token_info):
    authorizationByRole = AuthorizationByRole()
    assert authorizationByRole.validate_token(TOKEN)
    query = 'usrname=netadmin@internal-authz'
    mock_search.assert_called_once_with(rel_path='users',
                                        query=query,
                                        ca_file=ANY, engine_url=ANY,
                                        token=TOKEN)
    mock_follow_link.assert_called_once_with(obj=USER, rel='roles',
                                             ca_file=ANY, engine_host=ANY,
                                             token=TOKEN)


@mock.patch('auth.plugins.ovirt.authorization_by_role.get_token_info',
            return_value=INFO, autospec=True)
@mock.patch('auth.plugins.ovirt.authorization_by_role.get_profiles',
            return_value=PROFILES, autospec=True)
@mock.patch('auth.plugins.ovirt.authorization_by_role.search_request',
            return_value=USERS, autospec=True)
@mock.patch('auth.plugins.ovirt.authorization_by_role.follow_link',
            return_value=ROLES_INVALID, autospec=True)
def test_validate_token_fail(mock_follow_link, mock_search,
                             mock_get_profiles, mock_get_token_info):
    authorizationByRole = AuthorizationByRole()
    assert not authorizationByRole.validate_token(TOKEN)
