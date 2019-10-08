#!/bin/sh -ex

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_ROOT=$(git rev-parse --show-toplevel)
EXPORTED_ARTIFACTS_DIR="$PROJECT_ROOT/exported-artifacts/"

OVN_CENTRAL_TRIPLEO_TAG="${CENTRAL_CONTAINER_TAG:-current-tripleo-rdo}"
OVN_CONTROLLER_TRIPLEO_TAG="${CONTROLLER_CONTAINER_TAG:-current-tripleo-rdo}"
OVN_CENTRAL_IMG="tripleomaster/centos-binary-ovn-northd:$OVN_CENTRAL_TRIPLEO_TAG"
OVN_CONTROLLER_IMG="tripleomaster/centos-binary-ovn-controller:$OVN_CONTROLLER_TRIPLEO_TAG"
OVIRT_PROVIDER_OVN_IMG="${PROVIDER_IMG:-maiqueb/ovirt_provider_ovn}"

OVN_CONTAINER_FILES="$PROJECT_ROOT/automation/containers"
OVN_NORTHD_FILES="${OVN_CONTAINER_FILES}/ovn-central"
OVN_CONTROLLER_FILES="${OVN_CONTAINER_FILES}/ovn-controller/"

PROVIDER_PATH="$PROJECT_ROOT"/provider
CONTAINER_SRC_CODE_PATH="/ovirt-provider-ovn"

AUTOMATED_TEST_TARGET="${TEST_TARGET:-integration-tests27}"

function docker_ip {
    docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $1
}

function destroy_env {
  if [ -n "$(filter_integration_test_containers)" ]; then
    collect_ovn_data
    collect_provider_logs
    docker rm -f $(filter_integration_test_containers)
  else
    echo "No containers to destroy; Bailing out."
    return 0
  fi
}

function filter_integration_test_containers {
  docker ps -q --filter "label=purpose=ovirt_provider_ovn_integ_tests"
}

function create_ovn_containers {
  OVN_CENTRAL_ID="$(docker run --privileged -itd -v ${OVN_NORTHD_FILES}/config.json:/var/lib/kolla/config_files/config.json -v ${OVN_NORTHD_FILES}/boot-northd.sh:/usr/bin/boot-northd -e "KOLLA_CONFIG_STRATEGY=COPY_ONCE" --label purpose=ovirt_provider_ovn_integ_tests $OVN_CENTRAL_IMG)"
  OVN_CENTRAL_IP="$(docker_ip $OVN_CENTRAL_ID)"

  OVN_CONTROLLER_ID="$(docker run --privileged -itd -v ${OVN_CONTROLLER_FILES}/config.json:/var/lib/kolla/config_files/config.json -v ${OVN_CONTROLLER_FILES}/boot-controller.sh:/usr/bin/boot-controller -e KOLLA_CONFIG_STRATEGY=COPY_ONCE -e OVN_SB_IP=$OVN_CENTRAL_IP --label purpose=ovirt_provider_ovn_integ_tests $OVN_CONTROLLER_IMG)"
  OVN_CONTROLLER_IP="$(docker_ip $OVN_CONTROLLER_ID)"
}

function start_provider_container {
  PROVIDER_ID="$(docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -v $PROJECT_ROOT/:$CONTAINER_SRC_CODE_PATH -p 9696:9696 -p 35357:35357 -e OVN_NB_IP=$OVN_CENTRAL_IP -e PROVIDER_SRC_CODE=$CONTAINER_SRC_CODE_PATH $OVIRT_PROVIDER_OVN_IMG)"
  create_rpms
  install_provider_on_container
}

function create_rpms {
  cleanup_past_builds
  docker exec -t "$PROVIDER_ID" /bin/bash -c '
    touch /var/log/ovirt-provider-ovn.log
  '
  docker exec -t "$PROVIDER_ID" /bin/bash -c '
    cd $PROVIDER_SRC_CODE && \
    make rpm
  '
}

function cleanup_past_builds {
  rm -f "$PROJECT_ROOT"/*.tar.gz
}

function install_provider_on_container {
  docker exec -t "$PROVIDER_ID" /bin/bash -c '
    yum install -y --disablerepo=* \
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

function collect_ovn_data {
  echo "Collecting data from OVN containers ..."
  mkdir -p "$EXPORTED_ARTIFACTS_DIR"
  if [ -n "$OVN_CENTRAL_ID" ]; then
    docker cp "$OVN_CENTRAL_ID":/etc/openvswitch/ovnnb_db.db "$EXPORTED_ARTIFACTS_DIR"
    docker cp "$OVN_CENTRAL_ID":/etc/openvswitch/ovnsb_db.db "$EXPORTED_ARTIFACTS_DIR"
    docker cp "$OVN_CENTRAL_ID":/var/log/openvswitch/ovn-northd.log "$EXPORTED_ARTIFACTS_DIR"
  fi
  if [ -n "$OVN_CONTROLLER_ID" ]; then
    docker cp "$OVN_CONTROLLER_ID":/var/log/openvswitch/ovn-controller.log "$EXPORTED_ARTIFACTS_DIR"
  fi
}

function collect_provider_logs {
  if [ -n "$PROVIDER_ID" ]; then
    docker cp "$PROVIDER_ID":/var/log/ovirt-provider-ovn.log "$EXPORTED_ARTIFACTS_DIR"
  fi
}

trap destroy_env EXIT
create_ovn_containers
start_provider_container
activate_provider_traces
if [ -n "$RUN_INTEG_TESTS" ]; then
  tox -e "$AUTOMATED_TEST_TARGET"
  destroy_env
fi
trap - EXIT
