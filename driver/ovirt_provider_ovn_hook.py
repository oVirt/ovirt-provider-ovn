#!/usr/bin/env python
# Copyright 2016 Red Hat, Inc.
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

import os
import hooking


BRIDGE_NAME = 'br-int'
PROVIDER_TYPE_KEY = 'provider_type'
PROVIDER_TYPE = 'EXTERNAL_NETWORK'
VNIC_ID_KEY = 'vnic_id'


def ovs_device(domxml):
    ifc_name = get_lsp_name()

    try:
        iface = domxml.getElementsByTagName('interface')[0]
    except IndexError:
        return  # skip if not an interface
    source = iface.getElementsByTagName('source')[0]

    virtualport = domxml.createElement('virtualport')
    virtualport.setAttribute('type', 'openvswitch')
    iface.appendChild(virtualport)

    parameters = domxml.createElement('parameters')
    parameters.setAttribute('interfaceid', ifc_name)
    virtualport.appendChild(parameters)

    source.setAttribute('bridge', BRIDGE_NAME)


def get_lsp_name():
    # HACK: OVN requires LSP name, not LSP id
    # VNIC_ID is actually the LSP id, but as a workaround we assign the LSP id
    # value to LSP name
    # More info: https://bugzilla.redhat.com/1377963
    return os.environ[VNIC_ID_KEY]


def main():
    provider_type = os.environ.get(PROVIDER_TYPE_KEY, None)
    if provider_type != PROVIDER_TYPE:
        return

    domxml = hooking.read_domxml()
    ovs_device(domxml)
    hooking.write_domxml(domxml)

if __name__ == '__main__':
    main()