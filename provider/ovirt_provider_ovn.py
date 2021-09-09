# Copyright 2016-2021 Red Hat, Inc.
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

from threading import Thread
import atexit
import logging
import logging.config
import os
import socket
import ssl
import sys
import threading
from six.moves.BaseHTTPServer import HTTPServer

from ovsdbapp.backend.ovs_idl import vlog

import auth
import ovirt_provider_config
import version

from handlers.keystone import TokenHandler
from handlers.neutron import NeutronHandler
from ovirt_provider_config_common import ssl_ciphers_string
from ovirt_provider_config_common import ssl_enabled
from ovirt_provider_config_common import ssl_key_file
from ovirt_provider_config_common import ssl_cert_file
from ovirt_provider_config_common import neturon_port
from ovirt_provider_config_common import keystone_port


LOG_CONFIG_FILE = '/etc/ovirt-provider-ovn/logger.conf'


def setup_thread_excepthook():
    """
    Workaround for `sys.excepthook` thread bug from:
    http://bugs.python.org/issue1230540
    TODO: remove once bug is fixed
    """

    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):
        init_original(self, *args, **kwargs)
        run_original = self.run

        def run_with_except_hook(*args2, **kwargs2):
            try:
                run_original(*args2, **kwargs2)
            except Exception:
                sys.excepthook(*sys.exc_info())

        self.run = run_with_except_hook

    threading.Thread.__init__ = init


def uncaught_error_hook(exc_type, exc_value, exc_traceback):
    logging.error(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )
    logging.error("Irrecoverable error. Exiting!")
    logging.getLogger().handlers[0].flush()
    os._exit(-1)


def _init_logging():
    setup_thread_excepthook()
    logging.config.fileConfig(LOG_CONFIG_FILE)
    sys.excepthook = uncaught_error_hook
    logging.info('Starting server')
    _log_rpm_version()
    _init_ovs_logging()


def _init_ovs_logging():
    vlog.use_python_logger(max_level=vlog.DEBUG)


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

    server_keystone = HTTPServerIPv6(('', keystone_port()), TokenHandler)
    _ssl_wrap(server_keystone)
    Thread(target=server_keystone.serve_forever).start()

    server_neutron = HTTPServerIPv6(('', neturon_port()), NeutronHandler)
    _ssl_wrap(server_neutron)
    Thread(target=server_neutron.serve_forever).start()

    def kill_handler(signal, frame):
        logging.info('Shutting down http ...')
        server_keystone.shutdown()
        server_neutron.shutdown()
        logging.info('Http shut down successfully, exiting. Bye.')
        logging.shutdown()

    atexit.register(kill_handler)


class HTTPServerIPv6(HTTPServer):
    address_family = socket.AF_INET6


def _ssl_wrap(server):
    if ssl_enabled():
        server.socket = ssl.wrap_socket(
            server.socket,
            keyfile=ssl_key_file(),
            certfile=ssl_cert_file(),
            server_side=True,
            ssl_version=ssl.PROTOCOL_TLSv1_2,
            ciphers=ssl_ciphers_string(),
        )


if __name__ == '__main__':
    main()
