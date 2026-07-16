ARG BASE_IMAGE=quay.io/centos/centos:stream9
FROM ${BASE_IMAGE}
LABEL maintainer="devel@ovirt.org" purpose="ovirt_provider_ovn_tests"

ARG COPR_CHROOT=centos-stream-9-x86_64

RUN dnf -y install dnf-plugins-core epel-release \
    && \
    dnf copr enable -y ovirt/ovirt-master-snapshot ${COPR_CHROOT} \
    && \
    dnf install -y ovirt-release-master \
    && \
    dnf update -y \
    && \
    dnf install -y \
        createrepo_c \
        git \
        make \
        ovirt-python-openvswitch \
        python3-devel \
        python3-pip \
        python3-pytest \
        python3-requests \
        python3-ovsdbapp \
        python3-requests-mock \
        python3-setuptools \
        rpm-build \
    && \
    dnf clean all

# Add tox
RUN python3 -m pip install --upgrade pip \
    && \
    python3 -m pip install --ignore-installed tox

CMD ["/usr/sbin/init"]
