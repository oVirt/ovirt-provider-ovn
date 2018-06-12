#!/bin/bash -xe

DISTVER="$(rpm --eval "%dist"|cut -c2-3)"
PACKAGER=""
if [[ "${DISTVER}" == "el" ]]; then
    PACKAGER=yum
else
    PACKAGER=dnf
fi


mkdir -p exported-artifacts

mkdir -p "`rpm --eval %_topdir`" "`rpm --eval %_sourcedir`"
make rpm

cp ovirt-provider-ovn-*.tar.gz exported-artifacts/
cp ~/rpmbuild/RPMS/noarch/ovirt-provider-ovn-*.noarch.rpm exported-artifacts/
cp ~/rpmbuild/SRPMS/ovirt-provider-ovn-*.src.rpm exported-artifacts/

${PACKAGER} -y install exported-artifacts/ovirt-provider-ovn-*.noarch.rpm
