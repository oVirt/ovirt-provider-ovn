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

from __future__ import absolute_import

import ConfigParser
import glob
import os


CONFIG_FILE = '/etc/ovirt-provider-ovn/ovirt-provider-ovn.conf'
CONFD_DIR = '/etc/ovirt-provider-ovn/conf.d'
CONFD_FILES = '*.conf'

_config = None


def load():
    global _config
    _config = ConfigParser.ConfigParser()
    _config.read(CONFIG_FILE)
    _config.read(
        sorted(
            glob.glob(
                os.path.join(CONFD_DIR, CONFD_FILES)
            )
        )
    )


def get(section, key, default=None):
    global _config
    try:
        return _config.get(section, key) if _config else default
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        return default


def getboolean(section, key, default=None):
    global _config
    try:
        return _config.getboolean(section, key) if _config else default
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        return default


def getfloat(section, key, default=None):
    global _config
    try:
        return _config.getfloat(section, key) if _config else default
    except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
        return default
