ARG CENTOS_VERSION=9
FROM centos/centos:stream${CENTOS_VERSION}
LABEL maintainer="devel@ovirt.org" purpose="ovirt_provider_ovn_integ_tests"

ARG CENTOS_VERSION

RUN dnf -y install yum-plugin-copr \
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
