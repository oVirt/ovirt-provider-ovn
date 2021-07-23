#!/bin/bash -xe

# must override the advanced virt repo on el8
# TODO: get rid of this once advanced virt hits centOS8
source automation/common.sh
add_advanced_virt


mkdir -p exported-artifacts

mkdir -p "`rpm --eval %_topdir`" "`rpm --eval %_sourcedir`"
make rpm

cp ovirt-provider-ovn-*.tar.gz exported-artifacts/
cp ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-*.noarch.rpm exported-artifacts/
cp ~/rpmbuild/SRPMS/ovirt-provider-ovn-*.src.rpm exported-artifacts/

dnf -y install exported-artifacts/ovirt-provider-ovn-*.noarch.rpm
