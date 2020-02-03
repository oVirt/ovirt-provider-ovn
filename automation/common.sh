#!/bin/bash

set -xe

# Common helpers
add_advanced_virt() {
    cat >>/etc/dnf/dnf.conf <<EOF


[copr:copr.fedorainfracloud.org:sbonazzo:AdvancedVirtualization]
name=Copr repo for AdvancedVirtualization owned by sbonazzo
baseurl=https://copr-be.cloud.fedoraproject.org/results/sbonazzo/AdvancedVirtualization/centos-stream-\$basearch/
type=rpm-md
gpgcheck=1
gpgkey=https://copr-be.cloud.fedoraproject.org/results/sbonazzo/AdvancedVirtualization/pubkey.gpg
repo_gpgcheck=0
enabled=1
enabled_metadata=1
module_hotfixes=1
EOF
}

