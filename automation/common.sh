#!/bin/bash

set -xe

# Common helpers
add_advanced_virt() {
    cat >>/etc/dnf/dnf.conf <<EOF


[ovirt-master-advanced-virtualization-testing]
name=Advanced Virtualization testing packages
baseurl=https://buildlogs.centos.org/centos/8/virt/x86_64/advanced-virtualization/
enabled=1
gpgcheck=0
module_hotfixes=1
EOF
}

