ARG CENTOS_VERSION=9
FROM centos/centos:stream${CENTOS_VERSION}
LABEL maintainer="devel@ovirt.org" purpose="ovirt_provider_ovn_integ_tests"

ARG CENTOS_VERSION

RUN dnf -y install yum-plugin-copr epel-release \
    && \
    dnf copr enable -y ovirt/ovirt-master-snapshot centos-stream-${CENTOS_VERSION}-x86_64 \
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
