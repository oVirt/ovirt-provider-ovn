# Copyright 2018 Red Hat, Inc.
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

import requests


# TODO: this network was created out of band in the create_it_env.sh
#       script. This test should be updated in a later patch to
#       create the network in a fixture in this same module.
def test_get_network():
    r = requests.get('http://localhost:9696/v2.0/networks')
    assert r.status_code == 200
    networks = r.json()['networks']
    assert len(networks) == 1
    assert networks.pop()['name'] == 'ls0'
