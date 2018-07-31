# Copyright 2018 Red Hat, Inc.
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


import uuid
from datetime import datetime

from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound

import constants as ovnconst

from handlers.base_handler import ElementNotFoundError

from neutron.neutron_api_mappers import SecurityGroupMapper

from ovndb.db_set_command import DbSetCommand


class OvnSecurityGroupApi(object):

    def __init__(self, idl):
        self._idl = idl

    def create_security_group(
            self, name, project_id, tenant_id, description=None):
        now = datetime.utcnow().isoformat()
        pg_name = self._generate_name(name)
        external_ids = {
            SecurityGroupMapper.OVN_SECURITY_GROUP_CREATE_TS: now,
            SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION: description,
            SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS: now,
            SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: '1',
            SecurityGroupMapper.OVN_SECURITY_GROUP_NAME: name,
            SecurityGroupMapper.OVN_SECURITY_GROUP_PROJECT: project_id,
            SecurityGroupMapper.OVN_SECURITY_GROUP_TENANT: tenant_id,
        }
        return self._idl.pg_add(
            pg_name, may_exist=False, external_ids=external_ids
        )

    def delete_security_group(self, port_group_id):
        return self._idl.pg_del(port_group_id)

    def update_security_group(self, sec_group_id, name, description=None):
        try:
            sec_group = self._idl.lookup(
                ovnconst.TABLE_PORT_GROUP, sec_group_id
            )
        except RowNotFound as e:
            raise ElementNotFoundError(e)
        now = datetime.utcnow().isoformat()
        pg_name = self._generate_name(name)
        external_ids = sec_group.external_ids

        external_ids[SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS] = now
        external_ids[SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER] = (
            self._get_bumped_revision_number(sec_group)
        )
        external_ids[SecurityGroupMapper.OVN_SECURITY_GROUP_NAME] = name
        if description:
            external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION
            ] = description

        DbSetCommand(
            self._idl, ovnconst.TABLE_PORT_GROUP, sec_group_id
        ).add(ovnconst.ROW_PG_NAME, pg_name).add(
            ovnconst.ROW_PG_EXTERNAL_IDS,
            external_ids
        ).execute()

    @staticmethod
    def _generate_name(name):
        return 'ovirt-{name}-{gen_id}'.format(
            name=name, gen_id=uuid.uuid4()
        )

    @staticmethod
    def _get_bumped_revision_number(security_group):
        current_revision = int(
            security_group.external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER
            ]
        )
        return str(current_revision + 1)
