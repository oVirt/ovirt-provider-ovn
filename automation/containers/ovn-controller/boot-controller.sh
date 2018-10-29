#!/bin/bash

mkdir -p /var/run/openvswitch/
ovn_controller_opts=${OVN_CONTROLLER_OPTS:-"--ovn-controller-log=-vconsole:emer"}

echo "Start ovsdb-server & ovs-vswitchd ..."
/usr/share/openvswitch/scripts/ovs-ctl --no-monitor --system-id=random start

echo "Start ovn-controller ..."
/usr/share/openvswitch/scripts/ovn-ctl --no-monitor start_controller

while true; do
    sleep 1
done
