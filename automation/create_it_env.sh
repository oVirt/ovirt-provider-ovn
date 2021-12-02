#!/bin/bash -ex

CONTAINER_CMD=${CONTAINER_CMD:=podman}

EXEC_PATH=$(dirname "$(realpath "$0")")
PROJECT_ROOT=$(git rev-parse --show-toplevel)
EXPORTED_ARTIFACTS_DIR="$PROJECT_ROOT/exported-artifacts/"

IMAGE_TAG="${IMAGE_TAG:=centos-8}"
OVN_CONTROLLER_IMG="${CONTROLLER_IMG:=ovirt/ovn-controller}"
OVIRT_PROVIDER_OVN_IMG="${PROVIDER_IMG:=ovirt/ovirt-provider-ovn}"

PROVIDER_PATH="$PROJECT_ROOT"/provider
CONTAINER_SRC_CODE_PATH="/ovirt-provider-ovn"

AUTOMATED_TEST_TARGET="${TEST_TARGET:-integration-tests}"

test -t 1 && USE_TTY="t"

function container_ip {
    ${CONTAINER_CMD} inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $1
}

function container_exec {
    ${CONTAINER_CMD} exec "-i$USE_TTY" "$1" /bin/bash -c "$2"
}

function load_kernel_modules {
  modprobe openvswitch
}

function enable_ipv6 {
    container_exec "$1" "echo 0 > /proc/sys/net/ipv6/conf/all/disable_ipv6"
}

function destroy_env {
  mkdir -p "$EXPORTED_ARTIFACTS_DIR"
  collect_sys_info
  collect_ovn_data
  collect_provider_logs
  collect_journalctl_data
  chmod -R a+rw "$EXPORTED_ARTIFACTS_DIR"
  if [ -n "$OVN_CONTROLLER_ID" ]; then
     ${CONTAINER_CMD} rm -f "$OVN_CONTROLLER_ID"
  fi
  if [ -n "$PROVIDER_ID" ]; then
     ${CONTAINER_CMD} rm -f "$PROVIDER_ID"
  fi
}

function start_provider_container {
  kernel_version="$(uname -r)"
  PROVIDER_ID="$(
    ${CONTAINER_CMD} run --privileged -d \
	  -v $PROJECT_ROOT/:$CONTAINER_SRC_CODE_PATH \
	  -v /lib/modules/$kernel_version:/lib/modules/$kernel_version:ro \
	  -p 9696:9696 -p 35357:35357 \
    $OVIRT_PROVIDER_OVN_IMG:$IMAGE_TAG
  )"
  enable_ipv6 "$PROVIDER_ID"
  PROVIDER_IP="$(container_ip $PROVIDER_ID)"
  create_rpms
  install_provider_on_container
  activate_provider_traces
  start_provider_container_services
}

function start_controller_container {
  OVN_CONTROLLER_ID="$(${CONTAINER_CMD} run --privileged -d $OVN_CONTROLLER_IMG:$IMAGE_TAG)"
  enable_ipv6 "$OVN_CONTROLLER_ID"
  OVN_CONTROLLER_IP="$(container_ip $OVN_CONTROLLER_ID)"
  container_exec "$OVN_CONTROLLER_ID" "OVN_SB_IP=$PROVIDER_IP ./boot-controller.sh"
}

function create_rpms {
  cleanup_past_builds
  container_exec "$PROVIDER_ID" "touch /var/log/ovirt-provider-ovn.log"
  container_exec "$PROVIDER_ID" "
    cd $CONTAINER_SRC_CODE_PATH && \
    make rpm
  "
}

function cleanup_past_builds {
  rm -f "$PROJECT_ROOT"/ovirt-provider-ovn-*.tar.gz
}

function install_provider_on_container {
  container_exec "$PROVIDER_ID" "dnf install -y --disablerepo=* ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-1.*.rpm"
}

function start_provider_container_services {
  container_exec "$PROVIDER_ID" "./boot-northd.sh && systemctl start ovirt-provider-ovn"
}

function activate_provider_traces {
  container_exec "$PROVIDER_ID" "sed -i_backup s/INFO/DEBUG/g /etc/ovirt-provider-ovn/logger.conf"
}

function collect_ovn_data {
  echo "Collecting data from OVN containers ..."
  if [ -n "$PROVIDER_ID" ]; then
    ${CONTAINER_CMD} cp "$PROVIDER_ID":/var/lib/ovn/ovnnb_db.db "$EXPORTED_ARTIFACTS_DIR"
    ${CONTAINER_CMD} cp "$PROVIDER_ID":/var/lib/ovn/ovnsb_db.db "$EXPORTED_ARTIFACTS_DIR"
    ${CONTAINER_CMD} cp "$PROVIDER_ID":/var/log/ovn/ovn-northd.log "$EXPORTED_ARTIFACTS_DIR"
  fi
  if [ -n "$OVN_CONTROLLER_ID" ]; then
    ${CONTAINER_CMD} cp "$OVN_CONTROLLER_ID":/var/log/ovn/ovn-controller.log "$EXPORTED_ARTIFACTS_DIR"
  fi
}

function collect_provider_logs {
  if [ -n "$PROVIDER_ID" ]; then
    ${CONTAINER_CMD} cp "$PROVIDER_ID":/var/log/ovirt-provider-ovn.log "$EXPORTED_ARTIFACTS_DIR"
  fi
}

function collect_sys_info {
    cp /etc/os-release $EXPORTED_ARTIFACTS_DIR
    uname -a > $EXPORTED_ARTIFACTS_DIR/kernel_info.txt
}

function collect_journalctl_data {
  if [ -n "$PROVIDER_ID" ]; then
    container_exec "$PROVIDER_ID" "journalctl -xe > /var/log/journalctl.log"
    ${CONTAINER_CMD} cp "$PROVIDER_ID":/var/log/journalctl.log "$EXPORTED_ARTIFACTS_DIR"
  fi
}

trap destroy_env EXIT
load_kernel_modules
start_provider_container
start_controller_container
if [ -n "$RUN_INTEG_TESTS" ]; then
  export PROVIDER_CONTAINER_ID=$PROVIDER_ID
  export CONTROLLER_CONTAINER_ID=$OVN_CONTROLLER_ID
  export CONTAINER_PLATFORM=$CONTAINER_CMD
  tox -e "$AUTOMATED_TEST_TARGET"
  destroy_env
fi
trap - EXIT
cleanup_past_builds
