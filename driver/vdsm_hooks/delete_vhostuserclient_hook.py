#!/usr/bin/python2
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
import os
import hooking


def exec_cmd(*args):
    retcode, out, err = hooking.execCmd(args, sudo=True)
    if retcode != 0:
        raise RuntimeError("Failed to execute %s, due to: %s" % (args, err))
    return out


if __name__ == '__main__':
    domxml = hooking.read_domxml()
    interfaces = domxml.getElementsByTagName('interface')
    for interface in interfaces:
        if interface.getAttribute('type') == 'vhostuser':
            source = interface.getElementsByTagName('source')[0]
            path = source.getAttribute('path')
            name = os.path.split(path)[1]

            exec_cmd('ovs-vsctl', 'del-port', name)
