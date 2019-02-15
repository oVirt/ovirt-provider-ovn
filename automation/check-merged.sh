#!/bin/bash -xe

easy_install pip
pip install -U tox
pip install -U requests-mock==1.5.2

make check
make unittest
make integrationtest

if grep -q 'Fedora' /etc/redhat-release; then
    make unittest3
    make integrationtest3
fi

if git diff-tree --no-commit-id --name-only -r HEAD | egrep --quiet 'ovirt-provider-ovn.spec.in|Makefile|automation' ; then
    ./automation/build-artifacts.sh
fi

make lint
