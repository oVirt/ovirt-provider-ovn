#!/bin/bash -xe

easy_install pip
pip install -U tox
pip install -U requests-mock

make check
make unittest

if git diff-tree --no-commit-id --name-only -r HEAD | egrep --quiet 'vdsm.spec.in|Makefile.am' ; then
    ./automation/build-artifacts.sh
fi
