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

from handlers.base_handler import ElementNotFoundError

import neutron.validation as validate
from neutron.neutron_api_mappers import PortMapper
from neutron.neutron_api_mappers import SubnetMapper

from ovndb.ovn_security_groups import OvnSecurityGroupApi


def accepts_single_arg(f):
    def inner(self, **kwargs):
        assert len(
            filter(lambda (_, v,): v is not None, kwargs.items())  # NOQA: E999
        ) == 1, 'Exactly one paramter must be specified'
        return f(self, **kwargs)
    return inner


class OvnNorth(object):
    def __init__(self, idl):
        self.idl = idl
        self._ovn_sec_group_api = OvnSecurityGroupApi(self.idl)

    def add_ls(self, name, external_ids):
        return ovn_connection.execute(
            self.idl.ls_add(
                switch=name,
                may_exist=False,
                external_ids=external_ids
            )
        )

    def add_lsp(self, name, network_id):
        return ovn_connection.execute(
            self.idl.lsp_add(
                network_id,
                name,
                may_exist=False
            )
        )

    def add_lr(self, name, enabled):
        return ovn_connection.execute(self.idl.lr_add(
            router=name, may_exist=False, enabled=enabled
        ))

    def add_lrp(self, lr_id, lrp_name, mac, lrp_ip):
        ovn_connection.execute(self.idl.lrp_add(
            router=lr_id, port=lrp_name,
            mac=mac,
            networks=[lrp_ip],
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
                if any(port.name == lsp_id for port in network.ports):
                    return dhcp
            return None

    @accepts_single_arg
    def get_lsp(self, lsp_id=None, ovirt_lsp_id=None, lrp=None):
        if lsp_id:
            return ovn_connection.execute(self.idl.lsp_get(lsp_id))
        if ovirt_lsp_id:
            lsp = ovn_connection.execute(self.idl.lsp_get(ovirt_lsp_id))
            if not self._is_port_ovirt_controlled(lsp):
                raise ValueError('Not an ovirt controller port')
            return lsp
        if lrp:
            return lrp.name[len(ovnconst.ROUTER_PORT_NAME_PREFIX):]

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

    def list_lrp(self):
        # TODO: ovsdbapp does not allow to retrieve all lrp's in one query,
        # so we have to resort to using the generic query
        # To be changed once lrp_list is modified
        return ovn_connection.execute(self.idl.db_list(ovnconst.TABLE_LRP))

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

    def remove_lsp(self, lsp_id):
        ovn_connection.execute(self.idl.lsp_del(lsp_id))

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
        return ovn_connection.execute(
            self.idl.db_list_rows(ovnconst.TABLE_PORT_GROUP)
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

    def add_security_group(self, name, project_id, tenant_id, description):
        return ovn_connection.execute(
            self._ovn_sec_group_api.create_security_group(
                name, project_id, tenant_id, description
            )
        )

    def remove_security_group(self, security_group_id):
        ovn_connection.execute(
            self._ovn_sec_group_api.delete_security_group(security_group_id)
        )

    def update_security_group(self, sec_group_id, name, description):
        self._ovn_sec_group_api.update_security_group(
            sec_group_id, name, description
        )
