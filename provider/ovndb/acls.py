# Copyright 2018-2021 Red Hat, Inc.
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

import uuid

import neutron.constants as neutron_constants

from neutron.neutron_api_mappers import RestDataError
from neutron.neutron_api_mappers import SecurityGroupMapper
from neutron.neutron_api_mappers import SecurityGroupRuleMapper


class ProtocolNotSupported(RestDataError):
    message = (
        'The protocol "{protocol}" is not supported. Valid protocols '
        'are: {valid_protocols}, or protocol numbers ranging from '
        '0 to 255.'
    )

    def __init__(self, protocol):
        super(ProtocolNotSupported, self).__init__(
            self.message.format(
                protocol=protocol,
                valid_protocols=', '.join(
                    neutron_constants.PROTOCOL_NAME_TO_NUM_MAP.keys()
                ),
            )
        )


def acl_direction(api_direction, port_group_name):
    return u'{direction} == @{port_group}'.format(
        direction=neutron_constants.OVN_DIRECTION_MATCH_MAPPER[api_direction],
        port_group=port_group_name,
    )


def get_acl_protocol_info(ether_type):
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
    return '{ip_version}.{direction} == {prefix}'.format(
        ip_version=ip_version,
        direction=neutron_constants.OVN_ACL_IP_DIRECTION_MAPPER[direction],
        prefix=ip_prefix,
    )


def _get_protocol_number(protocol):
    if protocol is None:
        return
    if protocol.isdigit() and 0 <= int(protocol) <= 255:
        return protocol
    else:
        protocol = neutron_constants.PROTOCOL_NAME_TO_NUM_MAP.get(protocol)
        if protocol:
            return protocol
    raise ProtocolNotSupported(protocol)


def process_acl_protocol_and_ports(protocol, min_port, max_port, icmp):
    match = []
    if not protocol:
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
            '{proto}.dst == {port}'.format(proto=protocol, port=min_port)
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


def create_acl(
    security_group,
    direction,
    description=None,
    ether_type=None,
    ip_prefix=None,
    port_min=None,
    port_max=None,
    protocol=None,
    remote_group=None,
):
    match = create_acl_match(
        direction,
        ether_type,
        ip_prefix,
        port_min,
        port_max,
        protocol,
        security_group.name,
        remote_group_name=remote_group.name if remote_group else None,
    )
    acl = build_acl_parameters(
        port_group=security_group,
        direction=direction,
        match=create_acl_match_string(match),
        action=neutron_constants.ACL_ACTION_ALLOW_RELATED,
        priority=neutron_constants.ACL_ALLOW_PRIORITY,
    )
    external_ids = get_acl_external_ids(
        description=description,
        ether_type=ether_type,
        ip_prefix=ip_prefix,
        max_port=port_max,
        min_port=port_min,
        protocol=protocol,
        port_group_id=security_group.name,
        remote_group_id=remote_group.name if remote_group else None,
    )
    return dict(acl, external_ids=external_ids)


def create_acl_match(
    direction,
    ether_type,
    ip_prefix,
    min_port,
    max_port,
    protocol,
    port_group_id,
    remote_group_name=None,
):
    match = [acl_direction(direction, port_group_id)]
    ip_version, icmp = get_acl_protocol_info(ether_type)

    match.append(ip_version)
    match.append(acl_remote_ip_prefix(ip_prefix, direction, ip_version))
    match.append(
        get_remote_group_id_match(remote_group_name, ip_version, direction)
    )
    match.extend(
        process_acl_protocol_and_ports(protocol, min_port, max_port, icmp)
    )
    return list(filter(lambda s: s, match))


def create_acl_match_string(match_list):
    return ' && '.join(match_list)


def build_acl_parameters(port_group, direction, match, action, priority):
    acl_id = uuid.uuid4()
    return {
        'port_group': port_group,
        'priority': priority,
        'action': action,
        'log': False,
        'name': str(acl_id),
        'severity': [],
        'direction': neutron_constants.API_TO_OVN_DIRECTION_MAPPER[direction],
        'match': match,
    }


def get_acl_external_ids(
    description,
    ether_type,
    ip_prefix,
    max_port,
    min_port,
    protocol,
    port_group_id,
    remote_group_id,
):
    rule_external_id_data = {
        SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_SEC_GROUP_ID: port_group_id
    }
    if ether_type:
        rule_external_id_data[
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_ETHERTYPE
        ] = ether_type
    if max_port:
        rule_external_id_data[
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_MAX_PORT
        ] = str(max_port)
    if min_port:
        rule_external_id_data[
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_MIN_PORT
        ] = str(min_port)
    if ip_prefix:
        rule_external_id_data[
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_IP_PREFIX
        ] = ip_prefix
    if protocol:
        rule_external_id_data[
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_PROTOCOL
        ] = protocol
    if description:
        rule_external_id_data[
            SecurityGroupRuleMapper.REST_SEC_GROUP_RULE_DESCRIPTION
        ] = description
    if remote_group_id:
        rule_external_id_data[
            SecurityGroupRuleMapper.OVN_SEC_GROUP_RULE_REMOTE_GROUP_ID
        ] = remote_group_id
    return rule_external_id_data


def create_drop_all_traffic_acls(port_group):
    acl_list = []
    for (
        _,
        openstack_direction,
    ) in neutron_constants.OVN_TO_API_DIRECTION_MAPPER.items():
        acl_list.append(
            dict(
                build_acl_parameters(
                    port_group.name,
                    openstack_direction,
                    acl_direction(
                        openstack_direction,
                        SecurityGroupMapper.DROP_ALL_IP_PG_NAME,
                    )
                    + ' && ip',
                    neutron_constants.ACL_ACTION_DROP,
                    neutron_constants.ACL_DROP_PRIORITY,
                ),
                external_ids=get_acl_external_ids(
                    description='drop all {} ip traffic'.format(
                        openstack_direction
                    ),
                    ether_type=None,
                    ip_prefix=None,
                    max_port=None,
                    min_port=None,
                    protocol=None,
                    port_group_id=str(port_group.name),
                    remote_group_id=None,
                ),
            )
        )

    return acl_list


def create_default_allow_egress_acls(port_group):
    return [
        create_acl(
            port_group,
            neutron_constants.EGRESS_DIRECTION,
            ether_type=ip_version,
            description='automatically added allow all egress ip traffic',
        )
        for ip_version in neutron_constants.ETHER_TYPE_MAPPING.keys()
    ]


def get_remote_group_id_match(remote_group_name, ip_version, direction):
    if remote_group_name:
        remote_group_acl_name = get_assoc_addr_set_name(
            remote_group_name, ip_version
        )
        return build_remote_group_id_match(
            remote_group_acl_name, ip_version, direction
        )
    else:
        return ''


def build_remote_group_id_match(remote_group_name, ip_version, direction):
    return '{ip_version}.{direction} == ${address_set_name}'.format(
        ip_version=ip_version,
        direction=neutron_constants.OVN_ACL_IP_DIRECTION_MAPPER[direction],
        address_set_name=remote_group_name,
    )


def get_assoc_addr_set_name(sec_group_name, ip_version):
    return u'{pg_name}_{ip_v}'.format(pg_name=sec_group_name, ip_v=ip_version)
