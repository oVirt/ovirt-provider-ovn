ARG BASE_IMAGE=quay.io/centos/centos:stream9
FROM ${BASE_IMAGE}
LABEL maintainer="devel@ovirt.org" purpose="ovirt_provider_ovn_integ_tests"

ARG COPR_CHROOT=centos-stream-9-x86_64

RUN dnf -y install dnf-plugins-core epel-release \
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
        git \
        kernel \
        make \
        python3-devel  \
        rpm-build \
        firewalld-filesystem \
        python3-requests \
        ovirt-openvswitch \
        ovirt-openvswitch-ovn-central \
        ovirt-openvswitch-ovn-common \
        ovirt-python-openvswitch \
        python3-netaddr \
        python3-ovsdbapp \
    && \
    dnf clean all \
    && \
    mkdir -p /etc/ovirt-provider-ovn/conf.d/

COPY 10-integrationtest.conf /etc/ovirt-provider-ovn/conf.d/

COPY ovn-northd.conf /etc/sysconfig/ovn-northd

COPY boot-northd.sh /boot-northd.sh

VOLUME ["/ovirt-provider-ovn-rpms"]

CMD ["/usr/sbin/init"]
