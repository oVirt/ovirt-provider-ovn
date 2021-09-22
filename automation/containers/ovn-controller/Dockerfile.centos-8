FROM centos/centos:stream8
LABEL maintainer="amusil@redhat.com" purpose="ovirt_provider_ovn_integ_tests"

RUN dnf install -y \
        https://resources.ovirt.org/pub/yum-repo/ovirt-release-master.rpm \
    && \
    dnf update -y \
    && \
    dnf install -y \
        dhclient \
        iputils \
        NetworkManager-config-server \
        ovirt-openvswitch \
        ovirt-openvswitch-ovn-common \
        ovirt-openvswitch-ovn-host \
        ovirt-python-openvswitch \
    && \
    dnf clean all

COPY ovn-controller.conf /etc/sysconfig/ovn-controller

COPY boot-controller.sh /boot-controller.sh

CMD ["/usr/sbin/init"]
