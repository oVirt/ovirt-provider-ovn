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


OVN_NORTHBOUND = 'OVN_Northbound'
TABLE_LS = 'Logical_Switch'
ROW_LS_NAME = 'name'
ROW_LS_OTHER_CONFIG = 'other_config'
ROW_LS_EXTERNAL_IDS = 'external_ids'
LS_OPTION_EXCLUDE_IPS = 'exclude_ips'
LS_EXCLUDED_IP_DELIMITER = '..'

TABLE_LSP = 'Logical_Switch_Port'
ROW_LSP_NAME = 'name'
ROW_LSP_ADDRESSES = 'addresses'
ROW_LSP_EXTERNAL_IDS = 'external_ids'
ROW_LSP_ENABLED = 'enabled'
ROW_LSP_DHCPV4_OPTIONS = 'dhcpv4_options'
ROW_LSP_DHCPV6_OPTIONS = 'dhcpv6_options'
ROW_LSP_TAG = 'tag'
ROW_LSP_TYPE = 'type'
ROW_LSP_OPTIONS = 'options'
ROW_LSP_PORT_SECURITY = 'port_security'
LSP_TYPE_ROUTER = 'router'
LSP_TYPE_LOCALNET = 'localnet'
LSP_ADDRESS_TYPE_DYNAMIC = 'dynamic'
LSP_ADDRESS_TYPE_ROUTER = 'router'
LSP_ADDRESS_TYPE_UNKNOWN = 'unknown'
LSP_OPTION_ROUTER_PORT = 'router-port'
LSP_OPTION_NETWORK_NAME = 'network_name'

TABLE_DHCP_Options = 'DHCP_Options'
ROW_DHCP_EXTERNAL_IDS = 'external_ids'
ROW_DHCP_OPTIONS = 'options'
ROW_DHCP_CIDR = 'cidr'

TABLE_LR = 'Logical_Router'
ROW_LR_NAME = 'name'
ROW_LR_ENABLED = 'enabled'
ROW_LR_STATIC_ROUTES = 'static_routes'
ROW_LR_EXTERNAL_IDS = 'external_ids'

TABLE_LRP = 'Logical_Router_Port'
ROW_LRP_NETWORKS = 'networks'
ROW_LRP_IPV6_RA_CONFIGS = 'ipv6_ra_configs'
ROW_LRP_IPV6_ADDRESS_MODE = 'address_mode'
ROW_LRP_IPV6_SEND_PERIODIC = 'send_periodic'
ROW_LRP_IPV6_MTU = 'mtu'

LOCALNET_SWITCH_PORT_NAME = 'localnet_port'
ROUTER_SWITCH_PORT_NAME = 'router_port'
UNASSIGNED_SWTICH_PORT_NAME = 'unassgined_port'

ROUTER_PORT_NAME_PREFIX = 'lrp'

TABLE_ROUTES = 'Logical_Router_Static_Route'
ROW_ROUTES_IP_PREFIX = 'ip_prefix'
ROW_ROUTES_NEXTHOP = 'nexthop'

DEFAULT_ROUTE4 = '0.0.0.0/0'
DEFAULT_ROUTE6 = '::/0'

TABLE_PORT_GROUP = 'Port_Group'
ROW_PG_NAME = 'name'
ROW_PG_EXTERNAL_IDS = 'external_ids'

TABLE_ACL = 'ACL'

TABLE_ADDRESS_SET = 'Address_Set'

# Extensions
EXTENSION_UPDATED = '2022-02-28T00:00:00-00:00'
SUPPORTED_EXTENSIONS = [('Neutron Extra Route', 'extraroute')]
