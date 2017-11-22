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
#

from __future__ import absolute_import
import subprocess
import sys

from netaddr import IPAddress
from netaddr.core import AddrFormatError

from vdsm.network.api import network_caps

from . import expose, ExtraArgsError

OVN_CONFIG_SCRIPT = \
    '/usr/libexec/ovirt-provider-ovn/setup_ovn_controller.sh'

class NetworkNotFoundError(Exception):
    pass

class IpAddressNotFoundError(Exception):
    pass

@expose('ovn-config')
def ovn_config(*args):
    """
    ovn-config IP-central [tunneling-IP|tunneling-network]
    Configures the ovn-controller on the host.

    Parameters:
    IP-central - the IP of the engine (the host where OVN central is located)
    tunneling-IP - the local IP which is to be used for OVN tunneling
    tunneling-network - the vdsm network name which is to be used for OVN tunneling
    """
    if len(args) != 3:
        raise ExtraArgsError()

    if is_ipaddress(args[2]):
        ip_address = args[2]
    else:
        net_name = args[2]
        ip_address = get_ip_addr(get_network(network_caps(), net_name))
        if not ip_address:
            raise IpAddressNotFoundError(net_name)

    cmd = [OVN_CONFIG_SCRIPT, args[1], ip_address]
    exec_ovn_config(cmd)


def is_ipaddress(candidate):
    try:
        IPAddress(candidate)
    except AddrFormatError:
        return False
    return True


def get_network(net_caps, net_name):
    networks = net_caps['networks']
    try:
        return networks[net_name]
    except KeyError:
        raise NetworkNotFoundError(net_name)


def get_ip_addr(net):
    """
    Gets an IP address for the VDSM network. If no primary address, which is
    an IPv4 address, is known by VDSM, one of the IPv6 addresses is returned.
    :param net: network from VDSM network caps
    :return: IP address as a string or None
    """
    if net['addr']:
        ip = net['addr']
    elif net['ipv6addrs']:
        ip = net['ipv6addrs'][0].split('/')[0]
    else:
        return None
    return ip


def exec_ovn_config(cmd):
    rc = subprocess.call(cmd)
    if rc != 0:
        raise EnvironmentError('Failed to configure OVN controller.')
