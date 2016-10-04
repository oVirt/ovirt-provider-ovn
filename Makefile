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
VERSION=0.1
DIST_DIR=$(NAME)-$(VERSION)
DIST_FILE=$(NAME)-$(VERSION).tar.gz
PYTHON ?= $(shell which python)

install:
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/neutron/
	install -d $(DESTDIR)/usr/share/ovirt-provider-ovn/ovndb/
	install -d $(DESTDIR)/etc/ovirt-provider-ovn/
	install -t $(DESTDIR)/etc/ovirt-provider-ovn/ provider/logger.conf
	install -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ provider/*py
	install -t $(DESTDIR)/usr/share/ovirt-provider-ovn/ovndb/ provider/ovndb/*py
	install -D provider/scripts/ovirt-provider-ovn.service $(DESTDIR)/usr/lib/systemd/system/ovirt-provider-ovn.service

distcheck: check dist

dist:
	mkdir -p build/$(DIST_DIR)
	cp -r provider build/$(DIST_DIR)/
	cp Makefile build/$(DIST_DIR)/
	tar -zcf $(DIST_FILE) -C build $(DIST_DIR)
	rm -rf build

rpm: dist
	cp $(DIST_FILE) `rpm --eval %_sourcedir`
	rpmbuild -ba ovirt-provider-ovn.spec

check: flake8

flake8:
	tox -e flake8
	@echo 'FLAKE8 test passed.'

unittest:
	cd provider; python -m pytest tests/
