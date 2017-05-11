#!/bin/sh
set -e
CLUSTER_NAME=Default
TUNNELING_NETWORK=OVN_underlay
DYNAMIC_INVENTORY=/usr/share/ovirt-engine-metrics/setup/ansible/inventory/dynamic_ovirt_hosts
ansible-playbook -i ${DYNAMIC_INVENTORY} local_engine_cluster.yml \
  --extra-vars="ovirt_cluster_name=${CLUSTER_NAME} ovn_tunneling_network=${TUNNELING_NETWORK}"

