#!/bin/bash

mkdir -p /var/run/openvswitch/

echo "Start ovsdb-server & ovs-vswitchd ..."
/usr/share/openvswitch/scripts/ovs-ctl --no-monitor --system-id=random start

echo "Configuring controller ..."
ovs-vsctl --retry --timeout=2 --no-wait set Open_vSwitch . \
	external_ids:ovn-remote="tcp:$OVN_SB_IP:6642" \
	external_ids:ovn-encap-ip=`hostname -I` \
	external_ids:ovn-encap-type=geneve

echo "Start ovn-controller ..."
/usr/share/openvswitch/scripts/ovn-ctl --no-monitor start_controller --ovn-controller-log=-vconsole:dbg
