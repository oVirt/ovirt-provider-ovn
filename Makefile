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
VERSION=1.2.32
DIST_DIR=$(NAME)-$(VERSION)
GITHASH=$(shell git rev-parse --short HEAD)
TIMESTAMP:=$(shell date +'%Y%m%d%H%M%S')
RELEASE_SUFFIX=1

DIST_FILE=$(NAME)-$(VERSION).tar.gz
PYTHON ?= python2
GET_LIB_PATH_COMMAND='from distutils.sysconfig import get_python_lib; print(get_python_lib())'

PYTHON_LIBS=$(shell $(PYTHON) -c $(GET_LIB_PATH_COMMAND))
MKDIR=mkdir -p
RPM_SOURCE_DIR=$(shell rpm --eval %_sourcedir)

PROVIDER_PYTHON_FILES_DIR=$(DESTDIR)/usr/share/ovirt-provider-ovn/
DRIVER_CONFIG_PYTHON_FILES_DIR=$(DESTDIR)$(PYTHON_LIBS)
SHELL := bash

compile:
	$(PYTHON) -m compileall .
	$(PYTHON) -O -m compileall .

install_provider_python_files: compile
	for file in $(shell find provider/ -not \( -path provider/integration-tests -prune \) -not \( -path provider/tests -prune \) -regex ".*\.py[co]?"); do \
		install -m 644 -p -D $$file $(PROVIDER_PYTHON_FILES_DIR)/$${file/provider\///}; \
	done

replace_driver_shebangs:
	for file in $(shell find driver/vdsm_hooks -regex ".*\.py[co]?"); do \
		sed -ie 's+#!/usr/bin/python2+#!$(PYTHON)+' $$file; \
	done

install_driver_config_tool: compile
	for file in $(shell find driver/vdsm_tool -regex ".*\.py[co]?"); do \
		install -m 644 -p -D $$file $(DRIVER_CONFIG_PYTHON_FILES_DIR)/vdsm/tool/$${file/driver\/vdsm_tool\///}; \
	done

install: replace_driver_shebangs install_provider_python_files install_driver_config_tool provider/scripts/ovirt-provider-ovn.service provider/scripts/remove_chassis.sh
	install -d $(DESTDIR)/etc/ovirt-provider-ovn/
	install -d $(DESTDIR)/etc/ovirt-provider-ovn/conf.d
	install -m 644 -D provider/readme.conf $(DESTDIR)/etc/ovirt-provider-ovn/conf.d/README
	install -m 644 -t $(DESTDIR)/etc/ovirt-provider-ovn/ provider/logger.conf
	install -m 644 -t $(DESTDIR)/etc/ovirt-provider-ovn/ provider/ovirt-provider-ovn.conf
	install -m 644 -D ovirt-provider-ovn.logrotate $(DESTDIR)/etc/logrotate.d/ovirt-provider-ovn

	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ LICENSE
	install -m 644 -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ AUTHORS
	install -m 644 -D provider/scripts/ovirt-provider-ovn.service $(DESTDIR)/usr/lib/systemd/system/ovirt-provider-ovn.service
	install -m 644 -D provider/scripts/ovirt-provider-ovn.xml $(DESTDIR)/usr/lib/firewalld/services/ovirt-provider-ovn.xml
	install -m 544 -D provider/scripts/remove_chassis.sh $(PROVIDER_PYTHON_FILES_DIR)/scripts/remove_chassis.sh

	# install driver hooks
	install -m 555 -D driver/vdsm_hooks/ovirt_provider_ovn_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_device_create/10_ovirt_provider_ovn_hook
	install -m 555 -D driver/vdsm_hooks/ovirt_provider_ovn_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_nic_hotplug/10_ovirt_provider_ovn_hook
	install -m 555 -D driver/vdsm_hooks/ovirt_provider_ovn_vhostuser_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_nic_hotplug/20_ovirt_provider_ovn_vhostuser_hook
	install -m 555 -D driver/vdsm_hooks/ovirt_provider_ovn_vhostuser_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_device_create/20_ovirt_provider_ovn_vhostuser_hook
	install -m 555 -D driver/vdsm_hooks/delete_vhostuserclient_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/after_vm_destroy/delete_vhostuserclient_hook
	install -m 555 -D driver/vdsm_hooks/vhostuser_permissions_setter.py $(DESTDIR)/usr/libexec/vdsm/vhostuser_permissions_setter
	install -m 555 -D driver/vdsm_hooks/after_get_caps.py $(DESTDIR)/usr/libexec/vdsm/hooks/after_get_caps/ovirt_provider_ovn_hook
	install -m 644 -D driver/vdsm_hooks/sudoers $(DESTDIR)/etc/sudoers.d/50_vdsm_hook_ovirt_provider_ovn_hook

	# install driver config stuff
	install -d $(DESTDIR)/usr/libexec/ovirt-provider-ovn
	install -m 544 -D driver/scripts/setup_ovn_controller.sh $(DESTDIR)/usr/libexec/ovirt-provider-ovn/setup_ovn_controller.sh
	install -m 544 -D driver/scripts/unconfigure_ovn_controller.sh $(DESTDIR)/usr/libexec/ovirt-provider-ovn/unconfigure_ovn_controller.sh
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

provider/scripts/ovirt-provider-ovn.service provider/scripts/remove_chassis.sh: % : %.in
	sed -e "s|@PYTHON_EXECUTABLE@|${PYTHON}|" < $^ > $@

dist: version.py
	mkdir -p build/$(DIST_DIR)/

	find ./provider \( -name "*py" -o -name "*conf" -o -name "*xml" -o -name "*service.in" -o -name "*sh.in" \) -exec cp --parents \{\} build/$(DIST_DIR)/ \;
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

unittest3:
	cd provider; python3 -m pytest tests/

lint: version.py
	tox -e pylint

lint3: version.py
	tox -e pylint3

integrationtest:
	RUN_INTEG_TESTS="defined" automation/create_it_env.sh

integrationtest3:
	RUN_INTEG_TESTS="defined" \
	TEST_TARGET="integration-tests3" \
		automation/create_it_env.sh

coverage:
	tox -e coverage
