#!/bin/sh
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

# TODO - Currently, gracefully stopping the ovn-controller removes the chassis
# from the ovn-sb table. That will trigger the ovn tunnel interface to be torn
# down, thus stopping traffic.
# This means that an ovn-controller restart will lead to traffic interruption.
# The following bug https://bugzilla.redhat.com/show_bug.cgi?id=1601795 tracks
# that behavior to change, asking for a command to explicitly remove the
# chassis from the sb database.
# The line below should be updated (remove chassis + stop controller) when the
# bug is fixed.
systemctl stop ovn-controller

systemctl is-active --quiet ovsdb-server
OVSDB_STATUS="$?"
systemctl start ovsdb-server    # commands below require ovsdb-server
ovs-vsctl --no-wait remove open . external-ids ovn-remote
ovs-vsctl --no-wait remove open . external-ids ovn-encap-type
ovs-vsctl --no-wait remove open . external-ids ovn-encap-ip
ovs-vsctl --no-wait remove open . external_ids ovn-remote-probe-interval
ovs-vsctl --no-wait remove open . external_ids ovn-openflow-probe-interval
if [ "$OVSDB_STATUS" -ne 0 ]; then
  systemctl stop ovsdb-server
fi

