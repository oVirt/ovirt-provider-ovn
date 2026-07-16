ARG BASE_IMAGE=quay.io/centos/centos:stream9
FROM ${BASE_IMAGE}
LABEL maintainer="devel@ovirt.org" purpose="ovirt_provider_ovn_integ_tests"

ARG COPR_CHROOT=centos-stream-9-x86_64

RUN dnf -y install dnf-plugins-core \
    && \
    dnf copr enable -y ovirt/ovirt-master-snapshot ${COPR_CHROOT} \
    && \
    dnf install -y ovirt-release-master \
    && \
    dnf update -y \
    && \
    # Without it the ovirt-openvswitch fails to install
    dnf install -y systemd \
    && \
    dnf install -y \
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
