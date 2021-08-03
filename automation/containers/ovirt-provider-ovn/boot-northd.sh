#!/bin/bash

systemctl start ovn-northd

ovn-nbctl set-connection ptcp:6641:0.0.0.0 -- \
    set connection . inactivity_probe=60000

ovn-sbctl set-connection ptcp:6642:0.0.0.0 -- \
    set connection . inactivity_probe=60000
