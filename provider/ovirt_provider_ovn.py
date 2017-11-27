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
#
from __future__ import absolute_import

from BaseHTTPServer import HTTPServer
from threading import Thread
import atexit
import logging
import logging.config
import ssl

import auth
import ovirt_provider_config
import version

from handlers.keystone import TokenHandler
from handlers.neutron import NeutronHandler
from ovirt_provider_config_common import ssl_enabled
from ovirt_provider_config_common import ssl_key_file
from ovirt_provider_config_common import ssl_cert_file
from ovirt_provider_config_common import neturon_port
from ovirt_provider_config_common import keystone_port


LOG_CONFIG_FILE = '/etc/ovirt-provider-ovn/logger.conf'


def _init_logging():
    logging.config.fileConfig(LOG_CONFIG_FILE)
    logging.info('Starting server')
    _log_rpm_version()


def _log_rpm_version():
    logging.info(
        'Version: {version}-{release}'.format(
            version=version.VERSION,
            release=version.RELEASE,
        )
    )
    logging.info(
        'Build date: {date}'.format(
            date=version.TIMESTAMP,
        )
    )
    logging.info(
        'Githash: {githash}'.format(
            githash=version.GITHASH,
        )
    )


def main():
    _init_logging()

    ovirt_provider_config.load()
    auth.init()

    server_keystone = HTTPServer(('', keystone_port()), TokenHandler)
    _ssl_wrap(server_keystone)
    Thread(target=server_keystone.serve_forever).start()

    server_neutron = HTTPServer(('', neturon_port()), NeutronHandler)
    _ssl_wrap(server_neutron)
    Thread(target=server_neutron.serve_forever).start()

    def kill_handler(signal, frame):
        logging.info('Shutting down http ...')
        server_keystone.shutdown()
        server_neutron.shutdown()
        logging.info('Http shut down successfully, exiting. Bye.')
        logging.shutdown()

    atexit.register(kill_handler)


def _ssl_wrap(server):
    if ssl_enabled():
        server.socket = ssl.wrap_socket(server.socket,
                                        keyfile=ssl_key_file(),
                                        certfile=ssl_cert_file(),
                                        server_side=True,
                                        ssl_version=ssl.PROTOCOL_TLSv1_2)


if __name__ == '__main__':
    main()
