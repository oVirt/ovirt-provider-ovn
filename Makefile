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
VERSION=1.0
DIST_DIR=$(NAME)-$(VERSION)
GITHASH=$(shell git rev-parse --short HEAD)
TIMESTAMP=$(shell date +'%Y%m%d%H%M%S')
#RELEASE_SUFFIX=2.$(TIMESTAMP).git$(GITHASH)
RELEASE_SUFFIX=6

DIST_FILE=$(NAME)-$(VERSION)-${RELEASE_SUFFIX}.tar.gz
PYTHON ?= $(shell which python)

install:
	python -m compileall .
	python -O -m compileall .
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/ovndb/
	install -d $(DESTDIR)/etc/ovirt-provider-ovn/
	install -t $(DESTDIR)/etc/ovirt-provider-ovn/ provider/logger.conf
	install -t $(DESTDIR)/etc/ovirt-provider-ovn/ provider/ovirt-provider-ovn.conf
	install -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ provider/*.py*
	install -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ovndb/ provider/ovndb/*.py*
	install -D provider/scripts/ovirt-provider-ovn.service $(DESTDIR)/usr/lib/systemd/system/ovirt-provider-ovn.service

	install -D provider/scripts/ovirt-provider-ovn.xml $(DESTDIR)/etc/firewalld/services/ovirt-provider-ovn.xml
	install -D provider/scripts/ovirt-provider-ovn-central.xml $(DESTDIR)/etc/firewalld/services/ovirt-provider-ovn-central.xml
	install -m 555 -D driver/ovirt_provider_ovn_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_device_create/ovirt_provider_ovn_hook
	install -m 555 -D driver/ovirt_provider_ovn_hook.py $(DESTDIR)/usr/libexec/vdsm/hooks/before_nic_hotplug/ovirt_provider_ovn_hook

	install -d $(DESTDIR)/usr/libexec/ovirt-provider-ovn
	install -m 544 -D driver/scripts/setup_ovn_controller.sh $(DESTDIR)/usr/libexec/ovirt-provider-ovn/setup_ovn_controller.sh
	install -d $(DESTDIR)/usr/lib/python2.7/site-packages/vdsm/tool/
	install -t $(DESTDIR)/usr/lib/python2.7/site-packages/vdsm/tool/ driver/vdsm_tool/ovn_config.py*

distcheck: check dist

dist:
	mkdir -p build/$(DIST_DIR)/

	find ./provider \( -name "*py" -o -name "*conf" -o -name "*xml" -o -name "*service" \)   -exec cp --parents \{\} build/$(DIST_DIR)/ \;
	find ./driver \( -name "*py" -o -name "*conf" -o -name "*sh" \)   -exec cp --parents \{\} build/$(DIST_DIR)/ \;

	cp Makefile build/$(DIST_DIR)/
	cp ovirt-provider-ovn.spec.in build/$(DIST_DIR)/ovirt-provider-ovn.spec
	sed -i s/%{release_suffix}/$(RELEASE_SUFFIX)/ build/$(DIST_DIR)/ovirt-provider-ovn.spec
	tar -zcf $(DIST_FILE) -C build $(DIST_DIR)
	rm -rf build

rpm: dist
	cp $(DIST_FILE) `rpm --eval %_sourcedir`
	rpmbuild -ta $(DIST_FILE)

check: flake8

flake8:
	tox -e flake8
	@echo 'FLAKE8 test passed.'

unittest:
	cd provider; python -m pytest tests/
