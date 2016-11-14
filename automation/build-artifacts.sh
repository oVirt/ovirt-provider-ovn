#!/bin/bash -xe

mkdir -p exported-artifacts

make rpm

cp ovirt-provider-ovn-*.tar.gz exported-artifacts/
cp ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-*.noarch.rpm exported-artifacts/
