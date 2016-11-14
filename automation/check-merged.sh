#!/bin/bash -xe

easy_install pip
pip install -U tox

make check
make unittest
