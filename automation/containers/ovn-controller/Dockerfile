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
        dhclient \
        iputils \
        NetworkManager-config-server \
        openvswitch \
        openvswitch-ovn-common \
        openvswitch-ovn-host \
        python3-openvswitch \
    && \
    dnf clean all

COPY ovn-controller.conf /etc/sysconfig/ovn-controller

COPY boot-controller.sh /boot-controller.sh

VOLUME ["/sys/fs/cgroup"]

CMD ["/usr/sbin/init"]
