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


import random

import ovndb.constants as ovnconst

from netaddr import IPAddress
from netaddr.core import AddrFormatError


def get_port_ip(lsp, lrp=None):
    if not lsp.addresses:
        return None
    if 'router' in lsp.addresses[0]:
        return get_port_router_ip(lrp)
    elif 'dynamic' in lsp.addresses[0]:
        return get_port_dynamic_ip(lsp)
    return get_port_static_ip(lsp)


def get_port_static_ip(port):
    return _get_ip_from_addresses(port.addresses)


def get_port_dynamic_ip(port):
    return _get_ip_from_addresses(port.dynamic_addresses)


def get_port_router_ip(lrp):
    return lrp.networks[0].split('/')[0] if lrp and lrp.networks else None


def get_port_mac(port):
    return port.addresses[0].split()[0] if port.addresses else None


def random_mac():
    macparts = [0]
    macparts.extend([random.randint(0x00, 0xff) for i in range(5)])
    return ':'.join(map(lambda x: "%02x" % x, macparts))


def get_mask_from_subnet(subnet):
    return subnet.cidr.split('/')[1]


def _get_ip_from_addresses(addresses):
    if not addresses:
        return None
    address_parts = addresses[0].split(' ')
    candidate = address_parts[1] if len(address_parts) > 1 else None
    return candidate if _is_valid_ip(candidate) else None


def _is_valid_ip(candidate):
    try:
        IPAddress(candidate)
    except AddrFormatError:
        return False
    return True


def get_network_exclude_ips(network):
    exclude_values = network.other_config.get(
        ovnconst.LS_OPTION_EXCLUDE_IPS
    )
    # TODO: should we care about IP ranges? we do not use them, but
    # what if someone else will?
    # lets raise for now
    result = []
    for exclude_value in exclude_values.split():
        if ovnconst.LS_EXCLUDED_IP_DELIMITER in exclude_value:
            raise NotImplementedError(
                'Handling of ip ranges not yet implemented'
            )
        result.append(exclude_value)
    return result


def is_ip_available_in_network(network, ip):
    if any(
        ip == get_port_ip(port)
        for port in network.ports
    ):
        return False
    exclude_ips = get_network_exclude_ips(network)
    return ip not in exclude_ips
