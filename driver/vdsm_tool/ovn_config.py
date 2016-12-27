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

from __future__ import absolute_import
import sys

from .. import commands
from . import expose, ExtraArgsError

OVN_CONFIG_SCRIPT = \
    '/usr/libexec/ovirt-provider-ovn/setup_ovn_controller.sh'


@expose('ovn-config')
def ovn_config(*args):
    """
    ovn-config IP-central tunneling-IP
    Configures the ovn-controller on the host.

    Parameters:
    IP-central - the IP of the engine (the host where OVN central is located)
    tunneling-IP - the local IP which is to be used for OVN tunneling
    """
    if len(args) != 3:
        raise ExtraArgsError()

    cmd = [OVN_CONFIG_SCRIPT, args[1], args[2]]
    exec_ovn_config(cmd)


def exec_ovn_config(cmd):
    rc, out, err = commands.execCmd(cmd, raw=True)
    sys.stdout.write(out)
    sys.stderr.write(err)
    if rc != 0:
        raise EnvironmentError('Failed to configure OVN controller.')
