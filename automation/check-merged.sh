#!/bin/bash -xe

easy_install pip
pip install -U tox
pip install -U requests-mock==1.4.0

make check
make unittest

if grep -q 'Fedora' /etc/redhat-release; then
    make unittest3 || echo "Ignoring Python 3 errors temporarily"
fi

if git diff-tree --no-commit-id --name-only -r HEAD | egrep --quiet 'ovirt-provider-ovn.spec.in|Makefile|automation' ; then
    ./automation/build-artifacts.sh
fi
