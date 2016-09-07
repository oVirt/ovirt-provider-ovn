#!/usr/bin/env python
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

from xml.dom import minidom
import os
import sys

from mock import Mock
import mock

hooking_mock = Mock(name='hooking')
hooking_mock.__name__ = 'hooking'
sys.modules['hooking'] = hooking_mock
from ovirt_provider_ovn_hook import VNIC_ID_KEY
import ovirt_provider_ovn_hook


INPUT_XML = """<?xml version="1.0" encoding="utf-8"?>
<interface type="bridge">
  <model type="virtio"/>
  <source bridge="net1"/>
</interface>"""
EXPECTED_XML = """<?xml version="1.0" encoding="utf-8"?>
<interface type="bridge">
<model type="virtio"/>
<source bridge="br-int"/>
<virtualport type="openvswitch">
<parameters interfaceid="7"/>
</virtualport>
</interface>"""


class TestOvirtProviderOvnHook(object):

    @mock.patch.object(os, 'environ', {VNIC_ID_KEY: '7'})
    def test_ovs_device(self):
        domxml = minidom.parseString(INPUT_XML)
        ovirt_provider_ovn_hook.ovs_device(domxml)

        output_xml = domxml.toprettyxml(encoding='utf-8')
        output_xml = ('\n'.join(line.strip() for line in output_xml.split('\n')
                                if line.strip()))

        assert output_xml == EXPECTED_XML
