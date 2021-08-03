# This Dockerfile is based on the recommendations provided in the
# Centos official repository (https://hub.docker.com/_/centos/).
# It enables systemd to be operational.
FROM centos/centos:stream8
LABEL maintainer="amusil@redhat.com" purpose="ovirt_provider_ovn_integ_tests"

RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
     systemd-tmpfiles-setup.service ] || rm -f $i; done); \
    rm -f /lib/systemd/system/multi-user.target.wants/*;\
    rm -f /etc/systemd/system/*.wants/*;\
    rm -f /lib/systemd/system/local-fs.target.wants/*; \
    rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
    rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
    rm -f /lib/systemd/system/basic.target.wants/*;\
    rm -f /lib/systemd/system/anaconda.target.wants/*;

RUN dnf install -y \
        https://resources.ovirt.org/pub/yum-repo/ovirt-release-master.rpm \
    && \
    dnf update -y \
    && \
    dnf install -y \
        git \
        kernel \
        make \
        openvswitch \
        openvswitch-ovn-central \
        openvswitch-ovn-common \
        python3-devel  \
        python3-netaddr \
        python3-openvswitch \
        python3-ovsdbapp \
        python3-requests \
        rpm-build \
    && \
    dnf clean all \
    && \
    mkdir -p /etc/ovirt-provider-ovn/conf.d/

COPY 10-integrationtest.conf /etc/ovirt-provider-ovn/conf.d/

COPY ovn-northd.conf /etc/sysconfig/ovn-northd

COPY boot-northd.sh /boot-northd.sh

VOLUME [ "/sys/fs/cgroup" , "/ovirt-provider-ovn-rpms"]

CMD ["/usr/sbin/init"]
