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
        direction=neutron_constants.OVN_DIRECTION_MATCH_MAPPER[api_direction],
        port_group=port_group_name
    )


def acl_ethertype(ether_type):
    ip_version = None
    icmp = None
    if ether_type == neutron_constants.IPV4_ETHERTYPE:
        ip_version = neutron_constants.OVN_IPV4_ETHERTYPE
        icmp = neutron_constants.ICMP_V4
    elif ether_type == neutron_constants.IPV6_ETHERTYPE:
        ip_version = neutron_constants.OVN_IPV6_ETHERTYPE
        icmp = neutron_constants.ICMP_V6
    return ip_version, icmp


def acl_remote_ip_prefix(ip_prefix, direction, ip_version):
    if not ip_prefix:
        return ''
    if not is_valid_cidr(ip_prefix):
        raise RestDataError('Invalid IP prefix')
    src_or_dst = (
        'src' if direction == neutron_constants.INGRESS_DIRECTION else 'dst'
    )
    return '{ip_version}.{direction} == {prefix}'.format(
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


def process_acl_protocol_and_ports(protocol, min_port, max_port, icmp):
    match = []
    if protocol is None:
        return match

    protocol = _get_protocol_number(protocol)
    if protocol in neutron_constants.TRANSPORT_PROTOCOLS:
        protocol = neutron_constants.PROTOCOL_NUM_TO_NAME_MAP[protocol]
        match.extend(handle_ports(protocol, min_port, max_port))
    elif protocol in neutron_constants.ICMP_PROTOCOLS:
        match.extend(handle_icmp_protocol(icmp, min_port, max_port))
    else:
        match.append('ip.proto == {}'.format(protocol))

    return match


def handle_ports(protocol, min_port, max_port):
    match = [protocol]
    if min_port is not None and min_port == max_port:
        match.append(
            '{proto}.dst == {port}'.format(
                proto=protocol, port=min_port
            )
        )
    else:
        ports_acl_part = [
            '{protocol}.dst {operator} {port_num}'.format(
                protocol=protocol, operator=op, port_num=port
            )
            for op, port in _get_port_operators(min_port, max_port)
            if port is not None
        ]
        match.extend(ports_acl_part)

    return match


def _get_port_operators(min_port, max_port):
    return [('>=', min_port), ('<=', max_port)]


def handle_icmp_protocol(protocol, min_port, max_port):
    match = [protocol]
    icmp_protocol_acl = [
        '{icmp_protocol}.{attribute} == {value}'.format(
            icmp_protocol=protocol, attribute=k, value=v
        )
        for k, v in _get_icmp_protocol_data(min_port, max_port)
        if v is not None
    ]
    match.extend(icmp_protocol_acl)
    return match


def _get_icmp_protocol_data(min_port, max_port):
    return [('type', min_port), ('code', max_port)]
