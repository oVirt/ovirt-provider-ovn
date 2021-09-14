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
#

from __future__ import absolute_import
import subprocess

from netaddr import IPAddress
from netaddr.core import AddrConversionError
from netaddr.core import AddrFormatError

from vdsm.network.api import network_caps
from vdsm.tool import expose, ExtraArgsError


OVN_SCRIPT_DIR = '/usr/libexec/ovirt-provider-ovn'
OVN_CONFIG_SCRIPT = '{}/setup_ovn_controller.sh'.format(OVN_SCRIPT_DIR)
OVN_UNCONFIGURE_SCRIPT = '{}/unconfigure_ovn_controller.sh'.format(
    OVN_SCRIPT_DIR
)


class NetworkNotFoundError(Exception):
    pass


class IpAddressNotFoundError(Exception):
    pass


@expose('ovn-config')
def ovn_config(*args):
    """
    ovn-config IP-central [tunneling-IP|tunneling-network] host-fqdn
    Configures the ovn-controller on the host.

    Parameters:
    IP-central - the IP of the engine (the host where OVN central is located)
    tunneling-IP - the local IP which is to be used for OVN tunneling
    tunneling-network - the vdsm network meant to be used for OVN tunneling
    host-fqdn - FQDN that will be set as system-id for OvS (optional)
    """

    args_len = len(args)
    if args_len < 3 or args_len > 4:
        raise ExtraArgsError(n=3)

    if is_ipaddress(args[2]):
        ip_address = args[2]
    else:
        net_name = args[2]
        ip_address = get_ip_addr(get_network(network_caps(), net_name))
        if not ip_address:
            raise IpAddressNotFoundError(net_name)

    cmd = [
        OVN_CONFIG_SCRIPT,
        f'--central-ip={format_literal_ipaddress(args[1])}',
        f'--tunnel-ip={ip_address}',
    ]
    if args_len == 4:
        cmd.append(f'--host-fqdn={args[3]}')

    exec_command(cmd, 'Failed to configure OVN controller.')


@expose('ovn-unconfigure')
def ovn_unconfigure(*args):
    """
    ovn-unconfigure
    Unconfigures the ovn-controller on the host.

    """
    if len(args) != 1:
        raise ExtraArgsError(n=0)

    exec_command(
        [OVN_UNCONFIGURE_SCRIPT], 'Failed to unconfigure OVN controller.'
    )


def is_ipaddress(candidate):
    try:
        IPAddress(candidate)
    except AddrFormatError:
        return False
    return True


def format_literal_ipaddress(ip_address):
    """
    Formats a literal IP address according to rfc 2732
    """
    if is_ipv6(ip_address):
        return '[{ip_address}]'.format(ip_address=ip_address)
    return ip_address


def is_ipv6(candidate):
    try:
        IPAddress(candidate).ipv4()
        return False
    except AddrConversionError:
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


def exec_command(cmd, error_msg):
    rc = subprocess.call(cmd)
    if rc != 0:
        raise EnvironmentError(error_msg)
