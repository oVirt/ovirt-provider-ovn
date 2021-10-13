#!/usr/bin/python3
#
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
#
from __future__ import print_function

import errno
import getopt
import sys

CAPS_BINDING_KEY = 'openstack_binding_host_ids'
PLUGIN_TYPE_OVN = 'OVIRT_PROVIDER_OVN'
TEST_ID = '6bba738b-58be-4b4b-9ee1-c822113606c9'

CMD_LINE = ['ovs-vsctl', 'get', 'Open_vSwitch', '.', 'external_ids:system-id']


def _usage():
    print('Usage: %s option' % (sys.argv[0],))
    print('\t-h, --help\t\tdisplay this help')
    print('\t-t, --test\t\trun tests')


def _test():
    print(_update_ovirt_provider_ovn_host_id({}, TEST_ID))


def _update_openstack_binding_host_ids(caps):
    host_id = _get_open_vswitch_host_id()
    return _update_ovirt_provider_ovn_host_id(caps, host_id)


def _get_open_vswitch_host_id():
    retcode, out, err = hooking.execCmd(CMD_LINE, sudo=True)
    if retcode == 0:
        return out[0].decode('utf-8').replace('"', '')

    hooking.log('Failed to get Open VSwitch system-id . err = %s' % (err))
    return None


def _is_ovs_service_running():
    OVS_CTL = '/usr/share/openvswitch/scripts/ovs-ctl'
    try:
        rc, _, _ = hooking.execCmd([OVS_CTL, 'status'])
    except OSError as err:
        # Silently ignore the missing file and consider the service as down.
        if err.errno == errno.ENOENT:
            rc = errno.ENOENT
        else:
            raise
    return rc == 0


def _update_ovirt_provider_ovn_host_id(caps, host_id):
    if host_id is not None:
        bindings = caps.get(CAPS_BINDING_KEY, {})
        bindings[PLUGIN_TYPE_OVN] = host_id
        caps[CAPS_BINDING_KEY] = bindings
    return caps


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ht', ['help', 'test'])
    except getopt.GetoptError as err:
        print(str(err))
        _usage()
        sys.exit(1)

    for option, _ in opts:
        if option in ('-h', '--help'):
            _usage()
            sys.exit()
        elif option in ('-t', '--test'):
            _test()
            sys.exit()

    # Why here? So anyone can run -t and -h without setting the path.
    try:
        import hooking
    except ImportError:
        print(
            'Could not import hooking module. You should only run this '
            'script directly with option specified.'
        )
        _usage()
        sys.exit(1)

    if not _is_ovs_service_running():
        hooking.exit_hook('OVS is not running', return_code=0)

    caps = hooking.read_json()
    caps = _update_openstack_binding_host_ids(caps)
    hooking.write_json(caps)
