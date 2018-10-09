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
            wrapped_self.create_add_acl_command(port_group.uuid, acl_data)
            for acl_data in f(wrapped_self, port_group)
        ]
    return build_command_from_dict


class SecurityGroupException(AttributeError):
    pass


class OvnSecurityGroupApi(object):

    def __init__(self, idl):
        self._idl = idl

    def create_security_group(
            self, name, project_id=None, tenant_id=None, description=None):
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
        if sec_group.name == self.get_default_sec_group_name():
            raise SecurityGroupException(
                'Updating default security group not allowed.'
            )
        now = datetime.utcnow().isoformat()
        pg_name = self._generate_name_when_required(name)
        external_ids = sec_group.external_ids

        external_ids[SecurityGroupMapper.OVN_SECURITY_GROUP_UPDATE_TS] = now
        external_ids[SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER] = (
            self.get_bumped_revision_number(sec_group)
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
    def _generate_name_when_required(name):
        return u'ovirt_{name}_{gen_id}'.format(
            name=name, gen_id=str(uuid.uuid4()).replace('-', '_')
        ) if name != acl_lib.DEFAULT_PG_NAME else name

    @staticmethod
    def get_bumped_revision_number(security_group):
        current_revision = int(
            security_group.external_ids[
                SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER
            ]
        )
        return str(current_revision + 1)

    def create_security_group_rule(
            self, security_group, direction, description=None,
            ether_type=None, ip_prefix=None, port_min=None, port_max=None,
            protocol=None, remote_group=None
    ):
        acl = acl_lib.create_acl(
            security_group, direction=direction, ether_type=ether_type,
            ip_prefix=ip_prefix, port_min=port_min, port_max=port_max,
            protocol=protocol,  description=description,
            remote_group=remote_group
        )

        return self.create_add_acl_command(security_group.uuid, acl)

    def delete_security_group_rule(
            self, port_group, direction, priority, match
    ):
        return self._idl.pg_acl_del(port_group, direction, priority, match)

    def create_add_acl_command(self, pg_uuid, acl):
        return self._idl.pg_acl_add(
            pg_uuid, acl['direction'], acl['priority'],
            acl['match'], acl['action'], severity='alert', name='',
            **acl.get('external_ids', {})
        )

    @build_add_acl_command
    def create_default_port_group_acls(self, port_group):
        return acl_lib.create_default_port_group_acls(port_group)

    @build_add_acl_command
    def create_allow_all_egress_acls(self, port_group):
        return acl_lib.create_default_allow_egress_acls(port_group)

    def add_security_group_ports(self, security_group, port_id):
        return self._idl.pg_add_ports(security_group, port_id)

    def delete_security_group_ports(self, security_group, port_id):
        return self._idl.pg_del_ports(security_group, port_id)

    @staticmethod
    def get_default_sec_group_name():
        return acl_lib.DEFAULT_PG_NAME

    def create_address_set(self, ip_version, sec_group_name):
        return self._idl.db_create(
            ovnconst.TABLE_ADDRESS_SET,
            name=acl_lib.get_assoc_addr_set_name(
                sec_group_name, ip_version
            ),
            external_ids={'sec_group_name': sec_group_name}
        )

    def remove_address_set(self, address_set_name):
        return self._idl.db_destroy(
            ovnconst.TABLE_ADDRESS_SET, address_set_name
        )

    def add_address_set_ip(self, security_groups, ip, ip_version):
        for sec_group in security_groups:
            addr_set_name = acl_lib.get_assoc_addr_set_name(
                sec_group.name, ip_version
            )
            current_ips = self.get_address_set_addresses(addr_set_name)
            DbSetCommand(
                self._idl, ovnconst.TABLE_ADDRESS_SET, addr_set_name
            ).add('addresses', current_ips + [ip]).execute()

    def get_address_set_addresses(self, addr_set_name):
        row = self._idl.lookup(ovnconst.TABLE_ADDRESS_SET, addr_set_name)
        return row.addresses if row else []

    def remove_address_set_ip(self, security_groups, ip, ip_version):
        for sec_group in security_groups:
            addr_set_name = acl_lib.get_assoc_addr_set_name(
                sec_group.name, ip_version
            )
            current_ips = self.get_address_set_addresses(addr_set_name)
            current_ips.remove(ip)
            DbSetCommand(
                self._idl, ovnconst.TABLE_ADDRESS_SET, addr_set_name
            ).add('addresses', current_ips).execute()


def only_rules_with_allowed_actions(f):
    def filter_rules(*args):
        return filter(
            lambda rule: rule.action != neutron_constants.ACL_ACTION_DROP,
            f(*args)
        )
    return filter_rules
