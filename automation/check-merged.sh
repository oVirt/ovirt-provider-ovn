#!/bin/bash -xe

pip3 install -U tox tox-pip-version
pip3 install -U requests-mock==1.5.2

export PATH=/usr/local/bin:$PATH

make check
make unittest

# FIXME Intergration tests require container backend let's revive them once one is available
# make integrationtest

if git diff-tree --no-commit-id --name-only -r HEAD | egrep --quiet 'ovirt-provider-ovn.spec.in|Makefile|automation' ; then
    ./automation/build-artifacts.sh
fi

make lint
make coverage

