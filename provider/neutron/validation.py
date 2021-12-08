# Copyright 2017-2021 Red Hat, Inc.
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

import constants as ovnconst
import neutron.ip as ip_utils
from handlers.base_handler import ConflictError
from handlers.base_handler import BadRequestError
from handlers.base_handler import ElementNotFoundError

from neutron.neutron_api_mappers import PortMapper
from neutron.neutron_api_mappers import SubnetMapper
from neutron.neutron_api_mappers import RestDataError
from neutron.neutron_api_mappers import RouterMapper


def attach_network_to_router_by_subnet(subnet, network_id, router_id):
    if not ip_utils.get_subnet_gateway(subnet):
        raise ElementNotFoundError(
            'Unable to attach network {network_id} to router '
            '{router_id} by subnet {subnet_id}.'
            'Attaching by subnet requires the subnet to have '
            'a default gateway specified.'.format(
                network_id=network_id,
                subnet_id=subnet.uuid,
                router_id=router_id,
            )
        )


def fixed_ip_matches_port_subnet(fixed_ips, subnet):
    if not fixed_ips:
        return
    if not subnet:
        raise RestDataError(
            'Invalid paramter {fixed_ips}. {fixed_ips} can not be used if '
            'the network does not have a subnet attached.'.format(
                fixed_ips=PortMapper.REST_PORT_FIXED_IPS,
            )
        )
    fixed_ip_subnet_id = fixed_ips[0].get(PortMapper.REST_PORT_SUBNET_ID)
    if fixed_ip_subnet_id and fixed_ip_subnet_id != str(subnet.uuid):
        raise RestDataError(
            '{subnet_id} specified in {fixed_ips} is different from the '
            '{subnet_id} of the port\'s network'.format(
                subnet_id=PortMapper.REST_PORT_SUBNET_ID,
                fixed_ips=PortMapper.REST_PORT_FIXED_IPS,
            )
        )


def fixed_ips_require_stateful_dhcp(subnet, fixed_ips):
    if not fixed_ips:
        return
    subnet_ip_address = fixed_ips[0].get(PortMapper.REST_PORT_IP_ADDRESS)
    if (
        subnet.external_ids.get(SubnetMapper.OVN_IPV6_ADDRESS_MODE)
        == SubnetMapper.IPV6_ADDRESS_MODE_STATELESS
        and subnet_ip_address
    ):
        raise BadRequestError(
            'IPv6 address {ip} cannot be directly '
            'assigned to a port on subnet {subnet_id} as the '
            'subnet is configured for automatic addresses'.format(
                ip=subnet_ip_address, subnet_id=subnet.uuid
            )
        )


def ip_available_in_network(network, ip):
    if not ip_utils.is_ip_available_in_network(network, ip):
        raise RestDataError(
            f'The ip {ip} specified is already in use on '
            f'network {str(network.uuid)}'
        )


def port_ip_for_router(port_ip, port, router_id):
    if not port_ip:
        raise ElementNotFoundError(
            'Unable to attach port {port_id} to router '
            '{router_id}. '
            'Attaching by port requires the port to have '
            'an ip from subnet assigned.'.format(
                port_id=port.uuid, router_id=router_id
            )
        )


def create_routing_lsp_by_subnet(
    network_id,
    subnet_id,
    existing_subnet_for_network,
    existing_router_for_subnet,
    router_id=None,
    is_external_gateway=False,
):
    if not network_id:
        raise ElementNotFoundError(
            'Unable to add router interface. '
            'Subnet {subnet_id} does not belong to any network'.format(
                subnet_id=subnet_id
            )
        )

    if (
        not existing_subnet_for_network
        or str(existing_subnet_for_network.uuid) != subnet_id
    ):
        raise BadRequestError(
            'Subnet {subnet_id} does not belong to network {network_id}'.format(  # noqa: E501
                subnet_id=subnet_id, network_id=network_id
            )
        )

    _validate_subnet_is_connected_to_this_router(
        existing_router_for_subnet, router_id, subnet_id
    )

    if is_external_gateway:
        _validate_subnet_has_default_gateway(existing_subnet_for_network)
    else:
        _validate_subnet_is_connected_to_another_router(
            existing_router_for_subnet, subnet_id, router_id
        )


def _validate_subnet_is_connected_to_this_router(
    existing_router_for_subnet, router_id, subnet_id
):
    if existing_router_for_subnet and existing_router_for_subnet == router_id:
        raise BadRequestError(
            'Can not add subnet {subnet} to router {router}. Subnet is'
            ' already connected to this router'.format(
                subnet=subnet_id, router=router_id
            )
        )


def _validate_subnet_is_connected_to_another_router(
    existing_router_for_subnet, subnet_id, router_id
):
    if existing_router_for_subnet and existing_router_for_subnet != router_id:
        raise BadRequestError(
            f'Can not add subnet {subnet_id} to router {router_id}. Subnet is'
            f' already connected to router {existing_router_for_subnet}'
        )


def _validate_subnet_has_default_gateway(subnet):
    if ip_utils.get_subnet_gateway(subnet) is None:
        raise BadRequestError(
            'Subnet {} cannot be used as external gateway, '
            'since it does not have a default gateway defined'.format(
                subnet.uuid
            )
        )


def port_is_connected_to_router(lsp):
    lrp_name = lsp.options.get(ovnconst.LSP_OPTION_ROUTER_PORT)
    if not lrp_name:
        raise BadRequestError(
            'Port {port} is not connected to a router'.format(
                port=str(lsp.uuid)
            )
        )


def router_has_no_ports(lr):
    if lr.ports:
        raise ConflictError(
            'Router {router_id} still has ports'.format(router_id=lr.uuid)
        )


def port_added_to_lr_must_have_subnet(network_cidr, lsp_id, lr_id):
    if not network_cidr:
        raise ElementNotFoundError(
            'Unable to attach port {port_id} to router '
            '{router_id}. '
            'Attaching by port requires the port\'s network '
            'to have a subnet attached.'.format(
                port_id=lsp_id, router_id=lr_id
            )
        )


def unique_gateway_per_router(router, subnet, router_gateways):
    subnet_gateway = ip_utils.get_subnet_gateway(subnet)
    if subnet_gateway in router_gateways:
        raise BadRequestError(
            'Cannot attach subnet {subnet_id} to router {router_id},'
            'since its gateway [{subnet_gateway}] is used in another subnet'
            'already connected to it: {router_gateways}'.format(
                subnet_id=subnet.uuid,
                router_id=router.uuid,
                subnet_gateway=subnet_gateway,
                router_gateways=router_gateways,
            )
        )


def network_has_no_ports(ls_id, ls_ports, localnet_lsp):
    if list(filter(lambda x: x != localnet_lsp, ls_ports)):
        raise RestDataError(
            'Unable to delete network {}. Ports exist for the network'.format(
                ls_id
            )
        )


def port_is_not_connected_to_router(lsp):
    device_owner = lsp.external_ids.get(PortMapper.OVN_DEVICE_OWNER)
    if device_owner in (
        PortMapper.DEVICE_OWNER_ROUTER,
        PortMapper.DEVICE_OWNER_ROUTER_GATEWAY,
    ):
        raise ConflictError(
            'Port {port} cannot be deleted directly via the port API: '
            'has device owner network:router_interface'.format(port=lsp.uuid)
        )


def subnet_is_ovirt_managed(subnet):
    if SubnetMapper.OVN_NETWORK_ID not in subnet.external_ids:
        raise ElementNotFoundError(
            'Subnet {subnet} is not an ovirt manager subnet'.format(
                subnet=subnet.uuid
            )
        )


def no_default_gateway_in_routes(default_gateway_exists, routes):
    destination = RouterMapper.REST_ROUTER_DESTINATION
    if default_gateway_exists and routes:
        if list(
            filter(
                lambda r: r[destination] == ovnconst.DEFAULT_ROUTE4
                or r[destination] == ovnconst.DEFAULT_ROUTE6,
                routes,
            )
        ):
            raise BadRequestError(
                'A default static route can not be added when an external '
                ' gateway is defined on a router.'
            )


def subnet_not_connected_to_router(router_id, subnet_id):
    if router_id:
        raise BadRequestError(
            'Unable to delete subnet {subnet} because it is connected to '
            'router {router}. Please disconnect the subnet from the router'
            ' first.'.format(subnet=subnet_id, router=router_id)
        )


def port_does_not_belong_to_subnet(lsp, ls, subnet_id):
    if lsp not in ls.ports:
        raise ConflictError(
            'Port {port} does not belong to subnet {subnet}.'.format(
                port=lsp.uuid, subnet=subnet_id
            )
        )


def cannot_delete_default_security_group(security_group, default_group_name):
    if security_group.name == default_group_name:
        raise BadRequestError('Cannot delete the \'Default\' security group')


def cannot_delete_sec_group_in_use(security_group):
    if security_group.ports:
        raise BadRequestError(
            'Security Group {sec_group_id} in use'.format(
                sec_group_id=security_group.uuid
            )
        )
