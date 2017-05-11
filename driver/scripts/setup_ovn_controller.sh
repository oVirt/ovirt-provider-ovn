#!/bin/sh
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

set -e

ovs-vsctl set open . external-ids:ovn-remote=ssl:$1:6642
ovs-vsctl set open . external-ids:ovn-encap-type=geneve
ovs-vsctl set open . external-ids:ovn-encap-ip=$2

if [ $# -eq 5 ]; then
    key_file=$3
    cert_file=$4
    ca_file=$5

    if  [ ! -f "${key_file}" ]; then
       echo "Key file does not exist. Please check the parameters and try again."
       exit 1
    fi
    if  [ ! -f "${cert_file}" ]; then
       echo "Certificate file does not exist. Please check the parameters and try again."
       exit 1
    fi
    if  [ ! -f "${ca_file}" ]; then
       echo "CA certificate file does not exist. Please check the parameters and try again."
       exit 1
    fi
else
    echo "Using default PKI files"
    key_file=/etc/pki/vdsm/keys/vdsmkey.pem
    cert_file=/etc/pki/vdsm/certs/vdsmcert.pem
    ca_file=/etc/pki/vdsm/certs/cacert.pem
fi

cat > /etc/sysconfig/ovn-controller << EOF
# this file is auto-generated by ovirt-provider-ovn-driver
OVN_CONTROLLER_OPTS="--ovn-controller-ssl-key=${key_file} --ovn-controller-ssl-cert=${cert_file} --ovn-controller-ssl-ca-cert=${ca_file}"
EOF

systemctl restart openvswitch
systemctl restart ovn-controller
