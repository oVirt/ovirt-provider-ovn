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


from __future__ import absolute_import

import uuid
from datetime import datetime
from functools import wraps

from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound

import constants as ovnconst

from handlers.base_handler import ElementNotFoundError

import neutron.constants as neutron_constants
from neutron.neutron_api_mappers import SecurityGroupMapper

from ovndb.db_set_command import DbSetCommand
import ovndb.acls as acl_lib


def build_add_acl_command(f):
    @wraps(f)
    def build_command_from_dict(wrapped_self, port_group):
        return [
            wrapped_self.create_add_acl_command(port_group.name, acl_data)
            for acl_data in f(wrapped_self, port_group)
        ]

    return build_command_from_dict


class SecurityGroupException(AttributeError):
    pass


class OvnSecurityGroupApi(object):
    def __init__(self, idl):
        self._idl = idl

    def create_security_group(
        self, name, project_id=None, tenant_id=None, description=None
    ):
        now = datetime.utcnow().isoformat()
        pg_name = self._generate_name_when_required(name)
        external_ids = {
            SecurityGroupMapper.OVN_SECURITY_GROUP_CREATE_TS: now,
            SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS: now,
            SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: '1',
            SecurityGroupMapper.OVN_SECURITY_GROUP_NAME: name,
        }
        if description:
            external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION
            ] = description
        if tenant_id:
            external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_TENANT
            ] = tenant_id
        if project_id:
            external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_PROJECT
            ] = project_id
        return self._idl.pg_add(
            pg_name, may_exist=False, acls=[], external_ids=external_ids
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
        if sec_group.name == self.get_default_sec_group_name():
            raise SecurityGroupException(
                'Updating default security group not allowed.'
            )
        now = datetime.utcnow().isoformat()
        external_ids = sec_group.external_ids

        external_ids[SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS] = now
        external_ids[
            SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER
        ] = self.get_bumped_revision_number(sec_group)
        external_ids[SecurityGroupMapper.OVN_SECURITY_GROUP_NAME] = name
        if description:
            external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_DESCRIPTION
            ] = description

        return (
            DbSetCommand(self._idl, ovnconst.TABLE_PORT_GROUP, sec_group_id)
            .add(ovnconst.ROW_PG_EXTERNAL_IDS, external_ids)
            .build_command()
        )

    @staticmethod
    def _generate_name_when_required(name):
        return (
            u'ovirt_{gen_id}'.format(
                gen_id=str(uuid.uuid4()).replace('-', '_')
            )
            if name not in SecurityGroupMapper.WHITE_LIST_GROUP_NAMES
            else name
        )

    @staticmethod
    def get_bumped_revision_number(security_group):
        current_revision = int(
            security_group.external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER
            ]
        )
        return str(current_revision + 1)

    def create_security_group_rule(
        self,
        security_group,
        direction,
        description=None,
        ether_type=None,
        ip_prefix=None,
        port_min=None,
        port_max=None,
        protocol=None,
        remote_group=None,
    ):
        acl = acl_lib.create_acl(
            security_group,
            direction=direction,
            ether_type=ether_type,
            ip_prefix=ip_prefix,
            port_min=port_min,
            port_max=port_max,
            protocol=protocol,
            description=description,
            remote_group=remote_group,
        )

        return self.create_add_acl_command(security_group.uuid, acl)

    def delete_security_group_rule(
        self, port_group, direction, priority, match
    ):
        return self._idl.pg_acl_del(port_group, direction, priority, match)

    def create_add_acl_command(self, pg_uuid, acl):
        return self._idl.pg_acl_add(
            pg_uuid,
            acl['direction'],
            acl['priority'],
            acl['match'],
            acl['action'],
            severity='alert',
            name=acl['name'],
            **acl.get('external_ids', {})
        )

    @build_add_acl_command
    def create_drop_all_traffic_acls(self, port_group):
        return acl_lib.create_drop_all_traffic_acls(port_group)

    @build_add_acl_command
    def create_default_sec_group_acls(self, port_group):
        acls = acl_lib.create_default_allow_egress_acls(port_group)
        for ip_version in neutron_constants.ETHER_TYPE_MAPPING.keys():
            acls.append(
                acl_lib.create_acl(
                    port_group,
                    neutron_constants.INGRESS_DIRECTION,
                    ether_type=ip_version,
                    remote_group=port_group,
                )
            )
        return acls

    @build_add_acl_command
    def create_allow_all_egress_acls(self, port_group):
        return acl_lib.create_default_allow_egress_acls(port_group)

    def add_security_group_ports(self, security_group, port_id):
        return self._idl.pg_add_ports(security_group, port_id)

    def delete_security_group_ports(self, security_group, port_id):
        return self._idl.pg_del_ports(security_group, port_id)

    @staticmethod
    def get_default_sec_group_name():
        return SecurityGroupMapper.DEFAULT_PG_NAME

    @staticmethod
    def get_drop_all_sec_group_name():
        return SecurityGroupMapper.DROP_ALL_IP_PG_NAME


def only_rules_with_allowed_actions(f):
    def filter_rules(*args):
        return list(
            filter(
                lambda rule: rule.action != neutron_constants.ACL_ACTION_DROP,
                f(*args),
            )
        )

    return filter_rules
