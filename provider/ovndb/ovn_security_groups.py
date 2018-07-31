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

from neutron.neutron_api_mappers import SecurityGroupMapper


class OvnSecurityGroupApi(object):

    def __init__(self, idl):
        self._idl = idl

    def create_security_group(
            self, name, project_id, tenant_id, description=None):
        now = datetime.utcnow().isoformat()
        pg_name = 'ovirt-{name}-{gen_id}'.format(
            name=name, gen_id=uuid.uuid4()
        )
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
