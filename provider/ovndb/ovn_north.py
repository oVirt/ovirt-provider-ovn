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

from ovsdbapp.backend.ovs_idl.idlutils import RowNotFound

import ovn_connection
import constants as ovnconst

from handlers.base_handler import BadRequestError
from handlers.base_handler import ElementNotFoundError

import neutron.validation as validate
import neutron.constants as neutron_constants
from neutron.ip import get_ip_version
from neutron.ip import get_mask_from_subnet
from neutron.neutron_api_mappers import PortMapper
from neutron.neutron_api_mappers import SecurityGroupMapper
from neutron.neutron_api_mappers import SecurityGroupRuleMapper
from neutron.neutron_api_mappers import SubnetMapper

import ovndb.acls as acl_lib
from ovndb.db_set_command import DbSetCommand
from ovndb.ovn_security_groups import OvnSecurityGroupApi
from ovndb.ovn_security_groups import SecurityGroupException
from ovndb.ovn_security_groups import only_rules_with_allowed_actions


def accepts_single_arg(f):
    def inner(self, **kwargs):
        assert len(
            list(filter(lambda v: v is not None, kwargs.values()))
        ) == 1, 'Exactly one parameter must be specified'
        return f(self, **kwargs)
    return inner


def optionally_use_transactions(f):
    def inner(self, *args, **kwargs):
        command = f(self, *args, **kwargs)
        transaction = kwargs.get('transaction')
        if transaction and command:
            return transaction.add(command)
        if command:
            return ovn_connection.execute(command)
    return inner


class OvnNorth(object):
    def __init__(self, idl):
        self.idl = idl
        self._ovn_sec_group_api = OvnSecurityGroupApi(self.idl)

    def create_ovn_update_command(self, table_name, entity_uuid):
        return DbSetCommand(self.idl, table_name, entity_uuid)

    def add_ls(self, name, external_ids):
        return ovn_connection.execute(
            self.idl.ls_add(
                switch=name,
                may_exist=False,
                external_ids=external_ids
            )
        )

    @optionally_use_transactions
    def add_lsp(self, port_id, name, network_id, transaction=None):
        return self.idl.lsp_add(
            network_id,
            port_id,
            may_exist=False,
            external_ids={PortMapper.OVN_NIC_NAME: name},
        )

    def add_lr(self, name, enabled):
        return ovn_connection.execute(self.idl.lr_add(
            router=name, may_exist=False, enabled=enabled
        ))

    def add_lrp(self, lr_id, lrp_name, mac, lrp_ip, ipv6_ra_configs=None):
        ovn_connection.execute(self.idl.lrp_add(
            router=lr_id, port=lrp_name,
            mac=mac,
            networks=[lrp_ip],
            ipv6_ra_configs=ipv6_ra_configs or {}
        ))

    def add_route(self, lrp_id, prefix, nexthop):
        ovn_connection.execute(self.idl.lr_route_add(lrp_id, prefix, nexthop))

    def add_dhcp_options(self, cidr, external_ids):
        return ovn_connection.execute(
            self.idl.dhcp_options_add(cidr, **external_ids)
        )

    @accepts_single_arg
    def get_ls(self, ls_id=None, dhcp=None):
        if ls_id:
            return ovn_connection.execute(self.idl.ls_get(ls_id))
        if dhcp:
            dhcp_ls_id = str(
                dhcp.external_ids.get(SubnetMapper.OVN_NETWORK_ID)
            )
            for ls in self.list_ls():
                if dhcp_ls_id == str(ls.uuid):
                    return ls

    @accepts_single_arg
    def get_dhcp(self, ls_id=None, dhcp_id=None, lsp_id=None):
        if ls_id:
            return next((
                subnet for subnet in self.list_dhcp()
                if subnet.external_ids[SubnetMapper.OVN_NETWORK_ID] == (
                    str(ls_id)
                )),
                None
            )
        if dhcp_id:
            dhcp = ovn_connection.execute(self.idl.dhcp_options_get(dhcp_id))
            # TODO: this: str(subnet.uuid) != str(subnet_id)
            # is a workaround for an ovsdbapp problem returning
            # random value for table with no indexing column specified when
            # no record for the given UUID was found.
            # Remove when issue is resolved.
            if not dhcp or str(dhcp.uuid) != str(dhcp_id):
                raise ElementNotFoundError(
                    'Subnet {subnet} does not exist'.format(subnet=dhcp_id)
                )
            validate.subnet_is_ovirt_managed(dhcp)
            return dhcp

        if lsp_id:
            for dhcp in self.list_dhcp():
                network_id = dhcp.external_ids[SubnetMapper.OVN_NETWORK_ID]
                try:
                    network = self.get_ls(ls_id=network_id)
                except ElementNotFoundError:
                    continue
                if any(lsp.uuid == lsp_id for lsp in network.ports):
                    return dhcp
            return None

    @accepts_single_arg
    def get_lsp(self, lsp_id=None, ovirt_lsp_id=None, lrp=None, lsp_name=None):
        if lsp_id or lsp_name:
            return ovn_connection.execute(self.idl.lsp_get(lsp_id or lsp_name))
        if ovirt_lsp_id:
            lsp = ovn_connection.execute(self.idl.lsp_get(ovirt_lsp_id))
            if not self._is_port_ovirt_controlled(lsp):
                raise ValueError('Not an ovirt controller port')
            return lsp
        if lrp:
            lsp_id = lrp.name[len(ovnconst.ROUTER_PORT_NAME_PREFIX):]
            return ovn_connection.execute(self.idl.lsp_get(lsp_id))

    @accepts_single_arg
    def get_lrp(self, lrp_name=None, lsp_id=None):
        if lrp_name:
            return self.idl.lookup(ovnconst.TABLE_LRP, lrp_name)
        if lsp_id:
            lsp = self.get_lsp(lsp_id=lsp_id)
            lrp_name = lsp.options.get(ovnconst.LSP_OPTION_ROUTER_PORT)
            return self.get_lrp(
                lrp_name=lrp_name
            ) if lrp_name else None

    @accepts_single_arg
    def get_lr(self, lr_id=None):
        if lr_id:
            try:
                # TODO: replace by command after moving to newer ovsdbapp ver
                return self.idl.lookup(ovnconst.TABLE_LR, lr_id)
            except RowNotFound:
                raise ElementNotFoundError(
                    'Router {router} does not exist'.format(router=lr_id)
                )

    def list_ls(self):
        return ovn_connection.execute(self.idl.ls_list())

    def list_lrp(self, router_id=None):
        # TODO: ovsdbapp does not allow to retrieve all lrp's in one query,
        # so we have to resort to using the generic query
        # To be changed once lrp_list is modified
        all_lrps = ovn_connection.execute(self.idl.db_list(ovnconst.TABLE_LRP))
        if router_id and all_lrps:
            logical_router_ports = self.get_lr(lr_id=router_id).ports
            lrp_ids = [lrp.uuid for lrp in logical_router_ports]
            return list(
                filter(
                    lambda lrp: self.get_lrp_id(lrp) in lrp_ids, all_lrps
                )
            )
        else:
            return all_lrps

    @staticmethod
    def get_lrp_id(lrp):
        return lrp['_uuid']

    def list_dhcp(self):
        dhcps = ovn_connection.execute(self.idl.dhcp_options_list())
        return [
            dhcp for dhcp in dhcps
            if SubnetMapper.OVN_NETWORK_ID in dhcp.external_ids
        ]

    def list_lsp(self):
        return ovn_connection.execute(self.idl.lsp_list())

    def list_lr(self):
        return ovn_connection.execute(self.idl.lr_list())

    def remove_ls(self, ls_id):
        ovn_connection.execute(self.idl.ls_del(ls_id))

    def remove_static_route(self, lr, ip_prefix):
        for route in lr.static_routes:
            if route.ip_prefix == ip_prefix:
                ovn_connection.execute(self.idl.db_remove(
                    ovnconst.TABLE_LR,
                    str(lr.uuid),
                    ovnconst.ROW_LR_STATIC_ROUTES,
                    route
                ))

    def remove_dhcp_options(self, id):
        ovn_connection.execute(self.idl.dhcp_options_del(id))

    @optionally_use_transactions
    def remove_lsp(self, lsp_id, transaction=None):
        return self.idl.lsp_del(lsp_id)

    def remove_router(self, router_id):
        ovn_connection.execute(self.idl.lr_del(router_id))

    def remove_lrp(self, lrp_id):
        ovn_connection.execute(self.idl.lrp_del(str(lrp_id)))

    def db_set(self, table, id, values):
        ovn_connection.execute(self.idl.db_set(table, id, values))

    def _is_port_ovirt_controlled(self, port_row):
        return PortMapper.OVN_NIC_NAME in port_row.external_ids

    def clear_row_column(self, table, row_id, column):
        ovn_connection.execute(self.idl.db_clear(table, row_id, column))

    def remove_key_from_column(self, table, row_id, column_name, key):
        ovn_connection.execute(
            self.idl.db_remove(table, row_id, column_name, key)
        )

    def set_dhcp_options_options_column(self, subnet_uuid, options):
        ovn_connection.execute(
            self.idl.dhcp_options_set_options(subnet_uuid, **options)
        )

    def list_security_groups(self):
        return list(
            filter(
                lambda pg: pg.name != SecurityGroupMapper.DROP_ALL_IP_PG_NAME,
                ovn_connection.execute(
                    self.idl.db_list_rows(ovnconst.TABLE_PORT_GROUP)
                )
            )
        )

    def get_security_group(self, security_group_id):
        try:
            return self.idl.lookup(
                ovnconst.TABLE_PORT_GROUP, security_group_id
            )
        except RowNotFound:
            raise ElementNotFoundError(
                'Security Group {sec_group_id} does not exist'.format(
                    sec_group_id=security_group_id
                )
            )

    def add_security_group(
        self, name, project_id, tenant_id, description, transaction
    ):
        security_group = transaction.add(
            self._ovn_sec_group_api.create_security_group(
                name, project_id, tenant_id, description
            )
        )
        egress_rules = self.activate_egress_rules(security_group, transaction)
        self.create_address_sets(security_group.name, transaction)
        return security_group, egress_rules

    def remove_security_group(self, security_group_id):
        security_group = self.get_security_group(security_group_id)
        validate.cannot_delete_default_security_group(
            security_group,
            self._ovn_sec_group_api.get_default_sec_group_name()
        )
        validate.cannot_delete_sec_group_in_use(security_group)
        ovn_connection.execute(
            self._ovn_sec_group_api.delete_security_group(security_group_id)
        )
        self.remove_address_sets(security_group.name)

    def update_security_group(
            self, sec_group_id, name, description, transaction
    ):
        try:
            transaction.add(
                self._ovn_sec_group_api.update_security_group(
                    sec_group_id, name, description
                )
            )
        except SecurityGroupException as ex:
            raise BadRequestError(ex)

    @only_rules_with_allowed_actions
    def list_security_group_rules(self, sec_group=None):
        all_rules = ovn_connection.execute(
            self.idl.db_list_rows(ovnconst.TABLE_ACL)
        )

        return (
            all_rules if sec_group is None
            else list(
                filter(
                    lambda sec_group_rule: sec_group_rule.external_ids.get(
                        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID
                    ) in (str(sec_group.name), str(sec_group.uuid)), all_rules
                )
            )
        )

    def get_security_group_rule(self, security_group_rule_id):
        try:
            return self.idl.lookup(ovnconst.TABLE_ACL, security_group_rule_id)
        except RowNotFound:
            raise ElementNotFoundError(
                'Security Group Rule {rule_id} does not exist'.format(
                    rule_id=security_group_rule_id
                )
            )

    def create_security_group_rule(
            self, security_group, direction, description=None,
            ether_type=None, remote_ip_prefix=None, port_min=None,
            port_max=None, protocol=None, remote_group_id=None
    ):
        new_rev_number = self._ovn_sec_group_api.get_bumped_revision_number(
            security_group
        )
        remote_group = (
            self.get_security_group(remote_group_id)
            if remote_group_id else None
        )
        sec_group_rule_command = (
            self._ovn_sec_group_api.create_security_group_rule(
                security_group, direction, description=description,
                ether_type=ether_type, ip_prefix=remote_ip_prefix,
                port_min=port_min, port_max=port_max, protocol=protocol,
                remote_group=remote_group
            )
        )
        try:
            add_sec_group_rule_result = ovn_connection.execute(
                sec_group_rule_command
            )
        except RuntimeError as e:
            raise BadRequestError(e)

        sec_group_update_command = self.create_ovn_update_command(
            ovnconst.TABLE_PORT_GROUP, security_group.uuid
        )

        sec_group_update_command.add(
            ovnconst.ROW_PG_EXTERNAL_IDS,
            {SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: new_rev_number}
        ).execute()

        return add_sec_group_rule_result

    def remove_security_group_rule(self, security_group_rule_id):
        sec_group_rule = self.get_security_group_rule(security_group_rule_id)
        security_group_id = self.get_security_group_id(
            sec_group_rule
        )
        ovn_connection.execute(
            self._ovn_sec_group_api.delete_security_group_rule(
                security_group_id, sec_group_rule.direction,
                sec_group_rule.priority, sec_group_rule.match
            )
        )
        sec_group = self.get_security_group(security_group_id)
        new_rev_number = self._ovn_sec_group_api.get_bumped_revision_number(
            sec_group
        )
        self.create_ovn_update_command(
            ovnconst.TABLE_PORT_GROUP, security_group_id
        ).add(
            ovnconst.ROW_PG_EXTERNAL_IDS,
            {SecurityGroupMapper.OVN_SECURITY_GROUP_REV_NUMBER: new_rev_number}
        ).execute()

    @staticmethod
    def get_security_group_id(sec_group_rule):
        return sec_group_rule.external_ids[
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID
        ]

    def activate_default_security_group(
            self, port_id, transaction, update_port_association
    ):
        self.activate_drop_all_security_group(port_id, transaction)
        default_sec_group = self.assure_group_exists(
            SecurityGroupMapper.DEFAULT_PG_NAME, transaction,
            self._ovn_sec_group_api.create_default_sec_group_acls
        )
        if update_port_association:
            transaction.add(
                self._ovn_sec_group_api.add_security_group_ports(
                    default_sec_group.name, port_id
                )
            )

    def assure_group_exists(
            self, sec_group_name, transaction, provision_acl_function=None,
            create_address_sets=True
    ):
        try:
            sec_group = self.get_security_group(sec_group_name)
        except ElementNotFoundError:
            sec_group = self._activate_group(sec_group_name, transaction)
            if create_address_sets:
                self.create_address_sets(sec_group.name, transaction)
            if provision_acl_function:
                for acl in provision_acl_function(sec_group):
                    transaction.add(acl)
        return sec_group

    def activate_drop_all_security_group(self, port_id, transaction):
        drop_all_port_group = self.assure_group_exists(
            SecurityGroupMapper.DROP_ALL_IP_PG_NAME, transaction,
            self._ovn_sec_group_api.create_drop_all_traffic_acls,
            False
        )
        transaction.add(
            self._ovn_sec_group_api.add_security_group_ports(
                drop_all_port_group.name, port_id
            )
        )

    def _activate_group(self, sec_group_name, transaction):
        return transaction.add(
            self._ovn_sec_group_api.create_security_group(sec_group_name)
        )

    def activate_egress_rules(self, port_group, transaction):
        return [
            transaction.add(acl)
            for acl in self._ovn_sec_group_api.create_allow_all_egress_acls(
                port_group
            )
        ]

    def list_port_security_groups(self, port_uuid):
        return list(
            filter(
                lambda pg: port_uuid in pg.ports,
                self.list_security_groups()
            )
        )

    def add_security_groups_to_port(
        self, port_id, security_groups, transaction
    ):
        for sec_group in security_groups:
            transaction.add(
                self._ovn_sec_group_api.add_security_group_ports(
                    sec_group, port_id
                )
            )

    def remove_security_groups_from_port(
        self, port_id, security_groups, transaction
    ):
        for sec_group in security_groups:
            transaction.add(
                self._ovn_sec_group_api.delete_security_group_ports(
                    sec_group, port_id
                )
            )

    def deactivate_dropall_security_group(self, port_id, transaction):
        try:
            drop_all_sec_group = self.get_security_group(
                self._ovn_sec_group_api.get_drop_all_sec_group_name()
            )
            transaction.add(
                self._ovn_sec_group_api.delete_security_group_ports(
                    drop_all_sec_group.uuid, port_id
                )
            )
        except ElementNotFoundError:
            pass

    def create_address_sets(self, sec_group_name, transaction):
        return [
            transaction.add(
                self._ovn_sec_group_api.create_address_set(
                    ip_version, sec_group_name
                )
            )
            for ip_version in neutron_constants.OVN_IP_VERSIONS
        ]

    def remove_address_sets(self, sec_group_name):
        return [
            ovn_connection.execute(
                self._ovn_sec_group_api.remove_address_set(
                    acl_lib.get_assoc_addr_set_name(sec_group_name, ip_version)
                )
            )
            for ip_version in neutron_constants.OVN_IP_VERSIONS
        ]

    def add_addr_set_ip(self, security_groups, ip, transaction):
        if not ip or not security_groups:
            return
        ip_version = get_ip_version(ip)
        commands = self._ovn_sec_group_api.add_address_set_ip(
            security_groups=[
                self.get_security_group(sec_group_id)
                for sec_group_id in security_groups
            ], ip=ip, ip_version=ip_version
        )
        for command in commands:
            transaction.add(command)

    def delete_addr_set_ip(self, security_groups, ip, transaction):
        if not ip or not security_groups:
            return
        ip_version = get_ip_version(ip)
        commands = self._ovn_sec_group_api.remove_address_set_ip(
            security_groups=[
                self.get_security_group(sec_group_id)
                for sec_group_id in security_groups
            ], ip=ip, ip_version=ip_version
        )
        for command in commands:
            transaction.add(command)

    def get_lrp_by_subnet(self, subnet):
        router_id = subnet.external_ids.get(SubnetMapper.OVN_GATEWAY_ROUTER_ID)
        subnet_gateway = subnet.external_ids.get(SubnetMapper.OVN_GATEWAY)
        subnet_prefix_length = get_mask_from_subnet(subnet)
        cidr = '{gateway}/{prefix_length}'.format(
            gateway=subnet_gateway, prefix_length=subnet_prefix_length
        )
        return next(
            (
                lrp for lrp in self.list_lrp(router_id=router_id)
                if cidr in lrp[ovnconst.ROW_LRP_NETWORKS]
            ),
            None
        )
