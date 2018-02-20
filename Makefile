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

NAME=ovirt-provider-ovn
VERSION=1.2.7
DIST_DIR=$(NAME)-$(VERSION)
GITHASH=$(shell git rev-parse --short HEAD)
TIMESTAMP:=$(shell date +'%Y%m%d%H%M%S')
RELEASE_SUFFIX=2

DIST_FILE=$(NAME)-$(VERSION).tar.gz
PYTHON ?= $(shell which python)
MKDIR=mkdir -p
RPM_SOURCE_DIR=$(shell rpm --eval %_sourcedir)

install:
	python -m compileall .
	python -O -m compileall .
	install -d $(DESTDIR)/etc/ovirt-provider-ovn/
	install -d $(DESTDIR)/etc/ovirt-provider-ovn/conf.d
	install -m 644 -D provider/readme.conf $(DESTDIR)/etc/ovirt-provider-ovn/conf.d/README
	install -m 644 -t $(DESTDIR)/etc/ovirt-provider-ovn/ provider/logger.conf
	install -m 644 -t $(DESTDIR)/etc/ovirt-provider-ovn/ provider/ovirt-provider-ovn.conf
	install -m 644 -D ovirt-provider-ovn.logrotate $(DESTDIR)/etc/logrotate.d/ovirt-provider-ovn
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ provider/*.py*
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ version.py*
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ LICENSE
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ AUTHORS
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/ provider/auth/*.py*
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/plugins/
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/plugins provider/auth/plugins/*.py*
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/plugins/static_token/
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/plugins/static_token provider/auth/plugins/static_token/*.py*
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/plugins/ovirt/
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/auth/plugins/ovirt provider/auth/plugins/ovirt/*.py*
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/handlers/
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/handlers provider/handlers/*.py*
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/ovndb/
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ovndb/ provider/ovndb/*.py*
	install -m 644 -D provider/scripts/ovirt-provider-ovn.service $(DESTDIR)/usr/lib/systemd/system/ovirt-provider-ovn.service

	install -m 644 -D provider/scripts/ovirt-provider-ovn.xml $(DESTDIR)/usr/lib/firewalld/services/ovirt-provider-ovn.xml
	install -m 555 -D driver/vdsm_hooks/ovirt_provider_ovn_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_device_create/ovirt_provider_ovn_hook
	install -m 555 -D driver/vdsm_hooks/ovirt_provider_ovn_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_nic_hotplug/ovirt_provider_ovn_hook
	install -m 555 -D driver/vdsm_hooks/after_get_caps.py $(DESTDIR)/usr/libexec/vdsm/hooks/after_get_caps/ovirt_provider_ovn_hook
	install -m 644 -D driver/vdsm_hooks/sudoers $(DESTDIR)/etc/sudoers.d/50_vdsm_hook_ovirt_provider_ovn_hook

	install -d $(DESTDIR)/usr/libexec/ovirt-provider-ovn
	install -m 544 -D driver/scripts/setup_ovn_controller.sh $(DESTDIR)/usr/libexec/ovirt-provider-ovn/setup_ovn_controller.sh
	install -d $(DESTDIR)/usr/lib/python2.7/site-packages/vdsm/tool/
	install -m 644 -t $(DESTDIR)/usr/lib/python2.7/site-packages/vdsm/tool/ driver/vdsm_tool/ovn_config.py*
	install -m 644 -D README.adoc $(DESTDIR)/usr/share/doc/ovirt-provider-ovn/README.adoc
	install -m 644 -t $(DESTDIR)/usr/libexec/ovirt-provider-ovn/ LICENSE
	install -m 644 -t $(DESTDIR)/usr/libexec/ovirt-provider-ovn/ AUTHORS

distcheck: check dist

.PHONY: version.py
version.py: version.py.in
	sed \
	    -e s/@VERSION@/\'${VERSION}\'/ \
	    -e s/@RELEASE_SUFFIX@/\'${RELEASE_SUFFIX}\'/ \
	    -e s/@GITHASH@/\'${GITHASH}\'/ \
	    -e s/@TIMESTAMP@/\'${TIMESTAMP}\'/ \
	    < version.py.in \
	    > provider/version.py

dist: version.py
	mkdir -p build/$(DIST_DIR)/

	find ./provider \( -name "*py" -o -name "*conf" -o -name "*xml" -o -name "*service" \)   -exec cp --parents \{\} build/$(DIST_DIR)/ \;
	find ./driver \( -name "*py" -o -name "*conf" -o -name "*sh" \)   -exec cp --parents \{\} build/$(DIST_DIR)/ \;

	cp Makefile build/$(DIST_DIR)/
	cp ovirt-provider-ovn.spec.in build/$(DIST_DIR)/ovirt-provider-ovn.spec
	cp provider/version.py build/$(DIST_DIR)/version.py
	cp README.adoc build/$(DIST_DIR)/
	cp LICENSE build/$(DIST_DIR)/
	cp AUTHORS build/$(DIST_DIR)/
	cp ovirt-provider-ovn.logrotate build/$(DIST_DIR)/
	cp driver/vdsm_hooks/sudoers build/$(DIST_DIR)/driver/vdsm_hooks/
	sed -i \
		-e s/@RELEASE_SUFFIX@/$(RELEASE_SUFFIX)/ \
		-e s/@VERSION@/$(VERSION)/ \
		build/$(DIST_DIR)/ovirt-provider-ovn.spec
	tar -zcf $(DIST_FILE) -C build $(DIST_DIR)
	rm -rf build

rpm: dist
	$(MKDIR) $(RPM_SOURCE_DIR)
	cp $(DIST_FILE) $(RPM_SOURCE_DIR)
	rpmbuild -ta $(DIST_FILE)

check: flake8

flake8:
	tox -e flake8
	@echo 'FLAKE8 test passed.'

unittest:
	cd provider; python -m pytest tests/
