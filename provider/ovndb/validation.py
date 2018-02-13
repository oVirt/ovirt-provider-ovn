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


from handlers.base_handler import ElementNotFoundError
from ovndb.ovn_north_mappers import PortMapper
from ovndb.ovn_north_mappers import RestDataError


def attach_network_to_router_by_subnet(subnet, network_id, router_id):
    subnet_gateway = subnet.options.get('router')
    if not subnet_gateway:
        raise ElementNotFoundError(
            'Unable to attach network {network_id} to router '
            '{router_id} by subnet {subnet_id}.'
            'Attaching by subnet requires the subnet to have '
            'a default gateway specified.'
            .format(
                network_id=network_id, subnet_id=subnet.uuid,
                router_id=router_id
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
            '{subnet_id} of the port\'s network'
            .format(
                subnet_id=PortMapper.REST_PORT_SUBNET_ID,
                fixed_ips=PortMapper.REST_PORT_FIXED_IPS,
            )
        )


def fixed_ip_port_has_mac(mac, fixed_ips):
    if fixed_ips and not mac:
        raise RestDataError(
            'Unable to set {fixed_ips} on a port with no mac address defined'
            .format(fixed_ips=PortMapper.REST_PORT_FIXED_IPS,)
        )
