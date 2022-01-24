#!/bin/bash -xe

EXPORT_DIR="${EXPORT_DIR:=exported-artifacts}"

mkdir -p $EXPORT_DIR

mkdir -p "`rpm --eval %_topdir`" "`rpm --eval %_sourcedir`"
make rpm

cp ovirt-provider-ovn-*.tar.gz $EXPORT_DIR/
cp ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-*.noarch.rpm $EXPORT_DIR/
cp ~/rpmbuild/SRPMS/ovirt-provider-ovn-*.src.rpm $EXPORT_DIR/
