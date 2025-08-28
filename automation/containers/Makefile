# Copyright 2021 Red Hat, Inc.
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

CONTAINER_CMD = podman

prefix := ovirt
targets := 9 10
types := ovn-controller ovirt-provider-ovn ovirt-provider-ovn-tests

.PHONY: $(targets) $(types)

all: $(targets)

$(targets):
	for name in $(types); do \
		cd $$name; \
		$(CONTAINER_CMD) build --no-cache --rm --build-arg CENTOS_VERSION=$@ -t $(prefix)/$$name:centos-$@ -f Dockerfile . || exit $$?; \
		cd -; \
	done

$(types):
	for target in $(targets); do \
		cd $@; \
		$(CONTAINER_CMD) build --no-cache --rm --build-arg CENTOS_VERSION=$$target -t $(prefix)/$@:centos-$$target -f Dockerfile . || exit $$?; \
		cd -; \
	done
