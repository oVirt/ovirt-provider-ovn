# Copyright 2016 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license

%define        __spec_install_post %{nil}
%define          debug_package %{nil}
%define        __os_install_post %{_dbpath}/brp-compress

Name:           ovirt-provider-ovn
Version:        0.1
Release:        1%{?dist}
Summary:        The oVirt external network provider for OVN
License:        GPLv2+
BuildArch:      noarch
URL:            https://gerrit.ovirt.org/#/admin/projects/ovirt-provider-ovn
Source0:        %{name}-%{version}.tar.gz

Requires: openvswitch-ovn-central >= 2.6, python-openvswitch >= 2.6, firewalld-filesystem

%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
%make_install


%description
The oVirt external network provider for OVN allows to integrate oVirt with the
Open vSwitch Open Virtual Network (OVN) solution. OVN is a Software Defined
Networking extension to Open vSwitch. OVN is integrated into oVirt using the
external network API. The oVirt provider for OVN serves as a proxy between
oVirt engine and OVN northd.

%post
%systemd_post ovirt-provider-ovn.service


%preun
%systemd_preun ovirt-provider-ovn.service


%files
%config(noreplace) %{_sysconfdir}/ovirt-provider-ovn/logger.conf
%{_datadir}/ovirt-provider-ovn/*
%{_unitdir}/ovirt-provider-ovn.service


%changelog
* Fri Aug  26 2016 Marcin Mirecki
-
