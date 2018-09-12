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

import neutron.constants as neutron_constants

from neutron.neutron_api_mappers import RestDataError
from neutron.ip import is_valid_cidr


class ProtocolNotSupported(RestDataError):
    message = (
        'The protocol "{protocol}" is not supported. Valid protocols '
        'are: {valid_protocols}, or protocol numbers ranging from '
        '0 to 255.'
    )

    def __init__(self, protocol):
        super(ProtocolNotSupported, self).__init__(self.message.format(
            protocol=protocol, valid_protocols=', '.join(
                neutron_constants.PROTOCOL_NAME_TO_NUM_MAP.keys()
            )
        ))


def acl_direction(api_direction, port_group_name):
    return '{direction} == @{port_group}'.format(
        direction=neutron_constants.API_TO_OVN_DIRECTION_MAPPER[api_direction],
        port_group=port_group_name
    )


def acl_ethertype(ether_type):
    match = ''
    ip_version = None
    icmp = None
    if ether_type == 'IPv4':
        match = ' && ip4'
        ip_version = 'ip4'
        icmp = 'icmp4'
    elif ether_type == 'IPv6':
        match = ' && ip6'
        ip_version = 'ip6'
        icmp = 'icmp6'
    return match, ip_version, icmp


def acl_remote_ip_prefix(ip_prefix, direction, ip_version):
    if not ip_prefix:
        return ''
    if not is_valid_cidr(ip_prefix):
        raise RestDataError('Invalid IP prefix')
    src_or_dst = (
        'src' if direction == neutron_constants.INGRESS_DIRECTION else 'dst'
    )
    return ' && {ip_version}.{direction} == {prefix}'.format(
        ip_version=ip_version,
        direction=src_or_dst,
        prefix=ip_prefix
    )


def _get_protocol_number(protocol):
    if protocol is None:
        return
    try:
        protocol = int(protocol)
        if 0 <= protocol <= 255:
            return str(protocol)
    except (ValueError, TypeError):
        protocol = neutron_constants.PROTOCOL_NAME_TO_NUM_MAP.get(protocol)
        if protocol is not None:
            return protocol

    raise ProtocolNotSupported(protocol)
