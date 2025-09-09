# Copyright 2018-2021 Red Hat, Inc.
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

from lib.ansiblelib import get_playbook


PLAYBOOK_CONFIG = {'cloud': 'ovirt', 'secgroup_name': 'test_group'}


def test_security_groups_api():
    get_playbook('create_sec_group_api.yml', PLAYBOOK_CONFIG).run()
    get_playbook('cleanup_sec_group_api.yml', PLAYBOOK_CONFIG).run(
        enable_idempotency_checker=False
    )
