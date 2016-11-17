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

from uuid import UUID
import mock
import pytest

from ovndb.ovn_rest2db_mappers import PortMapper
from ovndb.ndb_api import DeletedRowDoesNotExistError
from ovndb.ndb_api import OvnNbDb

from ovntestlib import OvnNetworkRow
from ovntestlib import OvnPortRow
from ovntestlib import OvnTable


OVN_REMOTE = 'tcp:127.0.0.1:6641'
MAC_ADDRESS = '01:00:00:00:00:11'
DEVICE_ID = 'device-id-123456'
NIC_NAME = 'port_name'
NETWORK_NAME = 'test_net'

ID01 = UUID(int=1)
ID02 = UUID(int=2)
ID03 = UUID(int=3)
ID07 = UUID(int=7)
ID10 = UUID(int=10)
ID11 = UUID(int=11)


@mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
class TestOvnNbDb(object):

    @staticmethod
    def setup_db(mock_idl):
        port_1 = OvnPortRow(ID01, options={PortMapper.NIC_NAME: 'port1'})
        port_2 = OvnPortRow(ID02, options={PortMapper.NIC_NAME: 'port2'})
        port_3 = OvnPortRow(ID03)
        ports = {
            1: port_1,
            2: port_2,
            3: port_3
        }
        networks = {
            10: OvnNetworkRow(ID10, ports=[port_1, port_2]),
            11: OvnNetworkRow(ID11)
        }
        tables = {
            OvnNbDb.NETWORK_TABLE: OvnTable(networks),
            OvnNbDb.PORTS_TABLE: OvnTable(ports),
            OvnNbDb.DHCP_TABLE: OvnTable({})
        }
        mock_idl.Idl.return_value.tables = tables

    def test_get_multiple_networks(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        networks = ovndb.networks

        assert len(networks) == 2
        networks = sorted(networks, key=lambda row: row.uuid)
        assert networks[0].uuid == ID10
        assert networks[1].uuid == ID11

    def test_get_multiple_ports(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        netports = ovndb.ports

        assert len(netports) == 2
        netports = sorted(netports, key=lambda netport: netport.port.uuid)

        self._assert_netport(netports[0], ID01, ID10)
        self._assert_netport(netports[1], ID02, ID10)

    def test_get_single_network(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        network = ovndb.get_network(str(ID10))

        assert network.uuid == ID10

    def test_get_single_port(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        netport = ovndb.get_port(str(ID01))

        self._assert_netport(netport, ID01, ID10)

    def test_modify_network(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)
        mock_idl.Transaction.return_value.get_insert_uuid.return_value = None

        ovndb = OvnNbDb(OVN_REMOTE)
        updated_network = ovndb.update_network({
            'id': str(ID11),
            'name': NETWORK_NAME
        })

        networks = ovndb.networks

        assert updated_network.uuid == ID11
        assert len(networks) == 2
        networks = sorted(networks, key=lambda row: row.uuid)
        assert networks[0].uuid == ID10
        assert networks[1].uuid == ID11
        assert networks[1].name == NETWORK_NAME

    def test_add_network(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        transaction = mock_idl.Transaction.return_value
        temp_row = OvnNetworkRow(ID07)
        transaction.insert.return_value = temp_row
        transaction.get_insert_uuid.return_value = ID10

        ovndb = OvnNbDb(OVN_REMOTE)
        new_network = ovndb.update_network({'name': NETWORK_NAME})

        assert new_network.uuid == ID10

        # This is implementation dependent
        transaction.get_insert_uuid.assert_called_with(ID07)

    def test_modify_port(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)
        mock_idl.Transaction.return_value.get_insert_uuid.return_value = None

        port_rest_data = {
            'id': str(ID02),
            'name': NIC_NAME,
            'device_id': DEVICE_ID,
            'mac_address': MAC_ADDRESS,
            'network_id': str(ID11)
        }

        ovndb = OvnNbDb(OVN_REMOTE)
        ovndb.update_port(port_rest_data)
        netport = ovndb.get_port(str(ID02))
        networks = ovndb.networks

        port = netport.port
        assert port.uuid == ID02
        assert port.name == str(ID02)
        assert port.addresses == [MAC_ADDRESS]
        assert port.options[PortMapper.DEVICE_ID] == DEVICE_ID
        assert port.options[PortMapper.NIC_NAME] == NIC_NAME

        assert netport.network.uuid == ID11

        networks = sorted(networks, key=lambda row: row.uuid)
        assert networks[0].uuid == ID10
        assert len(networks[0].ports) == 1
        assert networks[0].ports[0].uuid == ID01

        assert networks[1].uuid == ID11
        assert len(networks[1].ports) == 1
        assert networks[1].ports[0].uuid == ID02

    def test_add_port(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        transaction = mock_idl.Transaction.return_value
        temp_row = OvnNetworkRow(ID07)
        transaction.insert.return_value = temp_row
        transaction.get_insert_uuid.return_value = ID03

        port_rest_data = {
            'name': NIC_NAME,
            'device_id': DEVICE_ID,
            'mac_address': MAC_ADDRESS,
            'network_id': str(ID11)
        }

        ovndb = OvnNbDb(OVN_REMOTE)
        new_port = ovndb.update_port(port_rest_data)

        assert new_port.port.uuid == ID03
        assert new_port.network.uuid == ID11

        transaction.get_insert_uuid.assert_called_with(ID07)

    def test_delete_unknown_network_fails(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        with pytest.raises(DeletedRowDoesNotExistError):
            ovndb = OvnNbDb(OVN_REMOTE)
            ovndb.delete_network(str(ID01))

    def test_delete_unknown_port_fails(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        with pytest.raises(DeletedRowDoesNotExistError):
            ovndb = OvnNbDb(OVN_REMOTE)
            ovndb.delete_port(str(ID10))

    def _assert_netport(self, netport,  expected_port_id,
                        expected_network_id):
        assert netport.port.uuid == expected_port_id
        assert netport.network.uuid == expected_network_id
