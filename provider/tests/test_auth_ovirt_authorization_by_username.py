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


from auth.plugins.ovirt import AuthorizationByUserName

TOKEN = 'the_secret_token'


INFO_VALID = {
    'user_id': 'netadmin@internal',
    'active': True
}

INFO_INVALID = {
    'user_id': 'user@internal',
    'active': True
}


@mock.patch('auth.plugins.ovirt.authorization_by_username.get_token_info',
            return_value=INFO_VALID, autospec=True)
def test_validate_token_success(mock_get_token_info):
    authorizationByUserName = AuthorizationByUserName()
    assert authorizationByUserName.validate_token(TOKEN)
    mock_get_token_info.assert_called_once_with(ca_file=ANY, client_id=ANY,
                                                client_secret=ANY,
                                                engine_url=ANY, token=TOKEN,
                                                timeout=ANY)


@mock.patch('auth.plugins.ovirt.authorization_by_username.get_token_info',
            return_value=INFO_INVALID, autospec=True)
def test_validate_token_fail(mock_get_token_info):
    authorizationByUserName = AuthorizationByUserName()
    assert not authorizationByUserName.validate_token(TOKEN)
    mock_get_token_info.assert_called_once_with(ca_file=ANY, client_id=ANY,
                                                client_secret=ANY,
                                                engine_url=ANY, token=TOKEN,
                                                timeout=ANY)
