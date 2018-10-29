#!/bin/sh -ex

EXEC_PATH=$(dirname "$(realpath "$0")")

OVN_CENTRAL_IMG="tripleomaster/centos-binary-ovn-northd:current-tripleo"
OVN_CONTROLLER_IMG="tripleomaster/centos-binary-ovn-controller:current-tripleo"

OVN_CONTAINER_FILES="$(git rev-parse --show-toplevel)/automation/containers"
OVN_NORTHD_FILES="${OVN_CONTAINER_FILES}/ovn-central"
OVN_CONTROLLER_FILES="${OVN_CONTAINER_FILES}/ovn-controller/"

function docker_ip {
    docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $1
}

function destroy_env {
  docker rm -f $(docker ps -q --filter "label=purpose=ovirt_provider_ovn_integ_tests")
}

function create_ovn_containers {
  OVN_CENTRAL_ID="$(docker run --privileged -itd -v ${OVN_NORTHD_FILES}/config.json:/var/lib/kolla/config_files/config.json -v ${OVN_NORTHD_FILES}/boot-northd.sh:/usr/bin/boot-northd -e "KOLLA_CONFIG_STRATEGY=COPY_ONCE" --label purpose=ovirt_provider_ovn_integ_tests $OVN_CENTRAL_IMG)"
  OVN_CENTRAL_IP="$(docker_ip $OVN_CENTRAL_ID)"

  OVN_CONTROLLER_ID="$(docker run --privileged -itd -v ${OVN_CONTROLLER_FILES}/config.json:/var/lib/kolla/config_files/config.json -v ${OVN_CONTROLLER_FILES}/boot-controller.sh:/usr/bin/boot-controller -e KOLLA_CONFIG_STRATEGY=COPY_ONCE -e OVN_SB_IP=$OVN_CENTRAL_IP --label purpose=ovirt_provider_ovn_integ_tests $OVN_CONTROLLER_IMG)"
  OVN_CONTROLLER_IP="$(docker_ip $OVN_CONTROLLER_ID)"

  sleep 1
  docker exec -t "$OVN_CONTROLLER_ID" /bin/bash -c '
      ovs-vsctl set Open_vSwitch . \
          external_ids:ovn-remote="tcp:$OVN_SB_IP:6642" \
          external_ids:ovn-encap-ip=`hostname -I` \
          external_ids:ovn-encap-type=geneve
  '
}

trap destroy_env EXIT
create_ovn_containers
docker exec -t "$OVN_CENTRAL_ID" /bin/bash -c '
  ovn-nbctl ls-add ls0 && \
  ovn-nbctl show && \
  ovn-sbctl list chassis
'
if [ -n "$RUN_INTEG_TESTS" ]; then
  tox -e integration-tests27
  destroy_env
fi
trap - EXIT
