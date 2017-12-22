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
