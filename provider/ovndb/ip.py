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


def get_port_static_ip(port):
    return _get_ip_from_addresses(port.addresses)


def get_port_dynamic_ip(port):
    return _get_ip_from_addresses(port.dynamic_addresses)


def _get_ip_from_addresses(addresses):
    if not addresses:
        return None
    address_parts = addresses[0].split(' ')
    return address_parts[1] if len(address_parts) > 1 else None
