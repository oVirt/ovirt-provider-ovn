#!/bin/bash -xe

CONTAINER_CMD=${CONTAINER_CMD:=podman}

function build_container {
  cd "automation/containers/$1"
  ${CONTAINER_CMD} build --no-cache --rm -t "ovirt/$1" -f Dockerfile  .
  cd -
}


for name in ovn-controller ovirt-provider-ovn; do
  echo "Building $name container image..."
  build_container $name
done
