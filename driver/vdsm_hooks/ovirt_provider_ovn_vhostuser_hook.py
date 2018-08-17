#!/usr/bin/env python
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
#
import os
import json

import hooking


PROVIDER_TYPE_KEY = 'provider_type'
PROVIDER_TYPE = 'EXTERNAL_NETWORK'
VNIC_ID_KEY = 'vnic_id'
VHOST_PERM_SETTER = '/usr/libexec/vdsm/vhostuser_permissions_setter'


def exec_cmd(*args):
    retcode, out, err = hooking.execCmd(args, sudo=True)
    if retcode != 0:
        raise RuntimeError("Failed to execute %s, due to: %s" %
                           (args, err))
    return out


def list_ovs_table(table):
    result = json.loads(
        exec_cmd('ovs-vsctl', '--format=json', 'list', table)[0]
    )
    data = result['data']
    headings = result['headings']
    return data, headings


def get_lsp_name():
    # HACK: OVN requires LSP name, not LSP id
    # VNIC_ID is actually the LSP id, but as a workaround we assign the LSP id
    # value to LSP name
    # More info: https://bugzilla.redhat.com/1377963
    return os.environ[VNIC_ID_KEY]


def set_br_int_datapath_type():
    exec_cmd('ovs-vsctl', 'set', 'Bridge', 'br-int', 'datapath_type=netdev')


def add_vhostuser_client():
    vhostuser = vhostuser_name()
    exec_cmd(
        'ovs-vsctl', 'add-port', 'br-int', vhostuser, '--', 'set',
        'Interface', vhostuser, 'type=dpdkvhostuserclient',
        'options:vhost-server-path={}'.format(vhostuser_path())
    )
    exec_cmd(
        'ovs-vsctl', 'set', 'Interface', vhostuser,
        'external-ids:iface-id={}'.format(get_lsp_name())
    )


def add_vhostuser_server(domxml):
    iface = domxml.getElementsByTagName('interface')[0]
    mac_address = iface.getElementsByTagName('mac')[0].getAttribute('address')

    for child in list(iface.childNodes):
        iface.removeChild(child)

    iface.setAttribute('type', 'vhostuser')

    mac = domxml.createElement('mac')
    mac.setAttribute('address', mac_address)
    iface.appendChild(mac)

    source = domxml.createElement('source')
    source.setAttribute('type', 'unix')
    source.setAttribute('path', vhostuser_path())
    source.setAttribute('mode', 'server')
    iface.appendChild(source)

    model = domxml.createElement('model')
    model.setAttribute('type', 'virtio')
    iface.appendChild(model)


def vhostuser_path():
    return os.path.join(
        os.sep, 'var', 'run', 'vdsm', 'vhostuser', vhostuser_name()
    )


def vhostuser_name():
    ifc_name = get_lsp_name()
    return '-'.join(['dpdk', 'vhostuser', ifc_name])


def is_netdev_datapath():
    data, headings = list_ovs_table('bridge')
    datapath_type_idx = headings.index('datapath_type')
    return any(br[datapath_type_idx] == 'netdev' for br in data)


def main():
    provider_type = os.environ.get(PROVIDER_TYPE_KEY, None)
    if provider_type != PROVIDER_TYPE:
        return

    if not is_netdev_datapath():
        return

    domxml = hooking.read_domxml()
    add_vhostuser_server(domxml)
    set_br_int_datapath_type()
    add_vhostuser_client()
    hooking.execCmd(
        [VHOST_PERM_SETTER, vhostuser_path()], sudo=True, sync=False
    )
    hooking.write_domxml(domxml)


if __name__ == '__main__':
    main()
