#!/bin/sh -xe
HOST_LIST='deploytest,'
ansible-playbook -i $HOST_LIST single_host.yml
