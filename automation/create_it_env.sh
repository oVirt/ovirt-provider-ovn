#!/bin/sh -ex

EXEC_PATH=$(dirname "$(realpath "$0")")

OVN_CENTRAL_TRIPLEO_TAG="${CENTRAL_CONTAINER_TAG:-current-tripleo}"
OVN_CONTROLLER_TRIPLEO_TAG="${CONTROLLER_CONTAINER_TAG:-current-tripleo}"
OVN_CENTRAL_IMG="tripleomaster/centos-binary-ovn-northd:$OVN_CENTRAL_TRIPLEO_TAG"
OVN_CONTROLLER_IMG="tripleomaster/centos-binary-ovn-controller:$OVN_CONTROLLER_TRIPLEO_TAG"
OVIRT_PROVIDER_OVN_IMG="maiqueb/ovirt_provider_ovn"

PROJECT_ROOT=$(git rev-parse --show-toplevel)
OVN_CONTAINER_FILES="$PROJECT_ROOT/automation/containers"
OVN_NORTHD_FILES="${OVN_CONTAINER_FILES}/ovn-central"
OVN_CONTROLLER_FILES="${OVN_CONTAINER_FILES}/ovn-controller/"

PROVIDER_PATH="$PROJECT_ROOT"/provider
CONTAINER_SRC_CODE_PATH="/ovirt-provider-ovn"

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

  docker exec -t "$OVN_CONTROLLER_ID" /bin/bash -c '
      ovs-vsctl --retry --timeout=2 --no-wait set Open_vSwitch . \
          external_ids:ovn-remote="tcp:$OVN_SB_IP:6642" \
          external_ids:ovn-encap-ip=`hostname -I` \
          external_ids:ovn-encap-type=geneve
  '
}

function start_provider_container {
  PROVIDER_ID="$(docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -v $PROJECT_ROOT/:$CONTAINER_SRC_CODE_PATH -p 9696:9696 -p 35357:35357 -e OVN_NB_IP=$OVN_CENTRAL_IP -e PROVIDER_SRC_CODE=$CONTAINER_SRC_CODE_PATH $OVIRT_PROVIDER_OVN_IMG)"
  create_rpms
  install_provider_on_container
}

function create_rpms {
  cleanup_past_builds
  docker exec -t "$PROVIDER_ID" /bin/bash -c '
    cd $PROVIDER_SRC_CODE && \
    make rpm
  '
}

function cleanup_past_builds {
  rm -f "$PROVIDER_PATH"/*.tar.gz
}

function install_provider_on_container {
  docker exec -t "$PROVIDER_ID" /bin/bash -c '
    yum install -y --disablerepo=* --enablerepo=base \
	    --enablerepo=centos-opstools-release \
	    ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-1.*.rpm && \
    sed -ie "s/PLACE_HOLDER/${OVN_NB_IP}/g" /etc/ovirt-provider-ovn/conf.d/10-integrationtest.conf && \
    systemctl start ovirt-provider-ovn
  '
}

function activate_provider_traces {
  docker exec -t "$PROVIDER_ID" /bin/bash -c '
    sed -i_backup 's/INFO/DEBUG/g' /etc/ovirt-provider-ovn/logger.conf
  '
}

trap destroy_env EXIT
create_ovn_containers
start_provider_container
activate_provider_traces
if [ -n "$RUN_INTEG_TESTS" ]; then
  tox -e integration-tests27
  destroy_env
fi
trap - EXIT
