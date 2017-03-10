#!/bin/bash -xe

easy_install pip
pip install -U tox
pip install -U requests-mock

make check
make unittest
