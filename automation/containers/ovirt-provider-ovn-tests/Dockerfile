ARG CENTOS_VERSION=9
FROM centos/centos:stream${CENTOS_VERSION}
LABEL maintainer="devel@ovirt.org" purpose="ovirt_provider_ovn_tests"

ARG CENTOS_VERSION

RUN dnf -y install yum-plugin-copr epel-release \
    && \
    dnf copr enable -y ovirt/ovirt-master-snapshot centos-stream-${CENTOS_VERSION}-x86_64 \
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
