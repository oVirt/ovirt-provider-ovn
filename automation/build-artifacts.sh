#!/bin/bash -xe

mkdir -p exported-artifacts

mkdir -p "`rpm --eval %_topdir`" "`rpm --eval %_sourcedir`"
make rpm

cp ovirt-provider-ovn-*.tar.gz exported-artifacts/
cp ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-*.noarch.rpm exported-artifacts/
cp ~/rpmbuild/SRPMS/ovirt-provider-ovn-*.src.rpm exported-artifacts/

yum -y install exported-artifacts/ovirt-provider-ovn-*.noarch.rpm
