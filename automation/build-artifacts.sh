#!/bin/bash -xe

# mock runner is not setting up the system correctly
# https://issues.redhat.com/browse/CPDEVOPS-242
readarray -t pkgs < automation/build-artifacts.packages
dnf install -y "${pkgs[@]}"

mkdir -p exported-artifacts

mkdir -p "`rpm --eval %_topdir`" "`rpm --eval %_sourcedir`"
make rpm

cp ovirt-provider-ovn-*.tar.gz exported-artifacts/
cp ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-*.noarch.rpm exported-artifacts/
cp ~/rpmbuild/SRPMS/ovirt-provider-ovn-*.src.rpm exported-artifacts/

dnf -y install exported-artifacts/ovirt-provider-ovn-*.noarch.rpm
