# This Dockerfile is based on the recommendations provided in the
# Centos official repository (https://hub.docker.com/_/centos/).
# It enables systemd to be operational.
FROM centos:7
LABEL maintainer="mdbarroso@redhat.com" purpose="ovirt_provider_ovn_integ_tests"
ENV container docker

RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
     systemd-tmpfiles-setup.service ] || rm -f $i; done); \
    rm -f /lib/systemd/system/multi-user.target.wants/*;\
    rm -f /etc/systemd/system/*.wants/*;\
    rm -f /lib/systemd/system/local-fs.target.wants/*; \
    rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
    rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
    rm -f /lib/systemd/system/basic.target.wants/*;\
    rm -f /lib/systemd/system/anaconda.target.wants/*;

RUN yum install -y \
      http://resources.ovirt.org/pub/yum-repo/ovirt-release-master.rpm \
      make \
      rpm-build \
      git && \
    mkdir -p /etc/ovirt-provider-ovn/conf.d/

COPY 10-integrationtest.conf /etc/ovirt-provider-ovn/conf.d/

VOLUME [ "/sys/fs/cgroup" , "/ovirt-provider-ovn-rpms"]

CMD ["/usr/sbin/init"]