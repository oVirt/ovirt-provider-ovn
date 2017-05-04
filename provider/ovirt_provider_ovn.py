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
from handlers.keystone import TokenHandler
from handlers.neutron import NeutronHandler


LOG_CONFIG_FILE = '/etc/ovirt-provider-ovn/logger.conf'
SSL_CONFIG_SECTION = 'SSL'
SSL_KEY_FILE = '/etc/pki/ovirt-engine/keys/ovirt-provider-ovn.pem'
SSL_CERT_FILE = '/etc/pki/ovirt-engine/certs/ovirt-provider-ovn.cer'
SSL_ENABLED = False


def _init_logging():
    logging.config.fileConfig(LOG_CONFIG_FILE)


def main():
    _init_logging()
    logging.info('Starting server')

    ovirt_provider_config.load()
    auth.init()

    server_keystone = HTTPServer(('', 35357), TokenHandler)
    _ssl_wrap(server_keystone)
    Thread(target=server_keystone.serve_forever).start()

    server_neutron = HTTPServer(('', 9696), NeutronHandler)
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
    if _ssl_enabled():
        server.socket = ssl.wrap_socket(server.socket,
                                        keyfile=_ssl_key_file(),
                                        certfile=_ssl_cert_file(),
                                        server_side=True,
                                        ssl_version=ssl.PROTOCOL_TLSv1_2)


def _ssl_enabled():
    return ovirt_provider_config.getboolean(SSL_CONFIG_SECTION, 'ssl_enabled',
                                            SSL_ENABLED)


def _ssl_key_file():
    return ovirt_provider_config.get(SSL_CONFIG_SECTION, 'key-file',
                                     SSL_KEY_FILE)


def _ssl_cert_file():
    return ovirt_provider_config.get(SSL_CONFIG_SECTION, 'cert-file',
                                     SSL_CERT_FILE)


if __name__ == '__main__':
    main()
