#!/bin/bash -xe

if [ "$(rpm --eval "%dist"|cut -c2-4)" == "el7" ] ; then
    pip install --upgrade pip
    PIP=pip
    VARIANT=
else
    PIP=pip-3
    VARIANT="3"
fi
$PIP install -U tox
$PIP install -U requests-mock==1.5.2

export PATH=/usr/local/bin:$PATH

make check
make unittest$VARIANT
if [ "$(rpm --eval "%dist"|cut -c2-4)" == "el7" ] ; then
    make integrationtest$VARIANT
fi

if git diff-tree --no-commit-id --name-only -r HEAD | egrep --quiet 'ovirt-provider-ovn.spec.in|Makefile|automation' ; then
    ./automation/build-artifacts.sh
fi

make lint$VARIANT
make coverage

