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
from ovndb.ovn_rest2db_mappers import NetworkIdRequiredForPortDataError
from ovndb.ovn_rest2db_mappers import PortDeviceIdRequiredDataError

from ovntestlib import OvnNetworkRow
from ovntestlib import OvnPortRow
from ovntestlib import OvnSubnetRow
from ovntestlib import OvnTable


OVN_REMOTE = 'tcp:127.0.0.1:6641'
MAC_ADDRESS = '01:00:00:00:00:11'
DEVICE_ID = 'device-id-123456'
NIC_NAME = 'port_name'
NETWORK_NAME = 'test_net'

PORT_ID01 = UUID(int=1)
PORT_ID02 = UUID(int=2)
PORT_ID03 = UUID(int=3)
PORT_ID04 = UUID(int=4)

NEW_PORT_ID07 = UUID(int=7)
NETWORK_ID10 = UUID(int=10)
NETWORK_ID11 = UUID(int=11)
NETWORK_ID12 = UUID(int=12)
NETWORK_ID13 = UUID(int=13)
NETWORK_ID14 = UUID(int=14)
NEW_NETWORK_ID17 = UUID(int=17)

SUBNET_ID20 = UUID(int=20)
SUBNET_ID21 = UUID(int=21)
SUBNET_ID22 = UUID(int=22)


@mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
class TestOvnNbDb(object):

    @staticmethod
    def setup_db(mock_idl):
        port_1 = OvnPortRow(PORT_ID01, addresses=MAC_ADDRESS,
                            external_ids={PortMapper.NIC_NAME: 'port1'})
        port_2 = OvnPortRow(PORT_ID02, addresses=MAC_ADDRESS,
                            external_ids={PortMapper.NIC_NAME: 'port2'})
        port_3 = OvnPortRow(PORT_ID03)
        port_4_with_subnet = OvnPortRow(PORT_ID04, addresses=MAC_ADDRESS)
        ports = {
            1: port_1,
            2: port_2,
            3: port_3,
            4: port_4_with_subnet
        }
        networks = {
            10: OvnNetworkRow(NETWORK_ID10, ports=[port_1, port_2]),
            11: OvnNetworkRow(NETWORK_ID11),
            12: OvnNetworkRow(NETWORK_ID12, ports=[port_4_with_subnet])

        }
        subnets = {
            20: OvnSubnetRow(SUBNET_ID20, network_id=str(NETWORK_ID13)),
            21: OvnSubnetRow(SUBNET_ID21, network_id=str(NETWORK_ID12)),
            22: OvnSubnetRow(SUBNET_ID22, network_id=str(NETWORK_ID14))
        }
        tables = {
            OvnNbDb.NETWORK_TABLE: OvnTable(networks),
            OvnNbDb.PORTS_TABLE: OvnTable(ports),
            OvnNbDb.DHCP_TABLE: OvnTable(subnets)
        }
        mock_idl.Idl.return_value.tables = tables

    def test_get_multiple_networks(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        networks = ovndb.networks

        assert len(networks) == 3
        networks = sorted(networks, key=lambda row: row.uuid)
        assert networks[0].uuid == NETWORK_ID10
        assert networks[1].uuid == NETWORK_ID11
        assert networks[2].uuid == NETWORK_ID12

    def test_get_multiple_ports(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        netports = ovndb.ports

        assert len(netports) == 2
        netports = sorted(netports, key=lambda netport: netport.port.uuid)

        self._assert_netport(netports[0], PORT_ID01, NETWORK_ID10)
        self._assert_netport(netports[1], PORT_ID02, NETWORK_ID10)

    def test_get_single_network(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        network = ovndb.get_network(str(NETWORK_ID10))

        assert network.uuid == NETWORK_ID10

    def test_get_single_port(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        netport = ovndb.get_port(str(PORT_ID01))

        self._assert_netport(netport, PORT_ID01, NETWORK_ID10)

    def test_modify_network(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)
        mock_idl.Transaction.return_value.get_insert_uuid.return_value = None

        ovndb = OvnNbDb(OVN_REMOTE)
        updated_network = ovndb.update_network({
            'id': str(NETWORK_ID11),
            'name': NETWORK_NAME
        })

        networks = ovndb.networks

        assert updated_network.uuid == NETWORK_ID11
        assert len(networks) == 3
        networks = sorted(networks, key=lambda row: row.uuid)
        assert networks[0].uuid == NETWORK_ID10
        assert networks[1].uuid == NETWORK_ID11
        assert networks[1].name == NETWORK_NAME

    def test_add_network(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        transaction = mock_idl.Transaction.return_value
        temp_row = OvnNetworkRow(NEW_NETWORK_ID17)
        transaction.insert.return_value = temp_row
        transaction.get_insert_uuid.return_value = NETWORK_ID10

        ovndb = OvnNbDb(OVN_REMOTE)
        new_network = ovndb.update_network({'name': NETWORK_NAME})

        assert new_network.uuid == NETWORK_ID10

        # This is implementation dependent
        transaction.get_insert_uuid.assert_called_with(NEW_NETWORK_ID17)

    def test_modify_port(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)
        mock_idl.Transaction.return_value.get_insert_uuid.return_value = None

        port_rest_data = {
            'id': str(PORT_ID02),
            'name': NIC_NAME,
            'device_id': DEVICE_ID,
            'mac_address': MAC_ADDRESS,
            'network_id': str(NETWORK_ID11)
        }

        ovndb = OvnNbDb(OVN_REMOTE)
        ovndb.update_port(port_rest_data)
        netport = ovndb.get_port(str(PORT_ID02))
        networks = ovndb.networks

        port = netport.port
        assert port.uuid == PORT_ID02
        assert port.name == str(PORT_ID02)
        assert port.addresses == [MAC_ADDRESS]
        assert port.external_ids[PortMapper.DEVICE_ID] == DEVICE_ID
        assert port.external_ids[PortMapper.NIC_NAME] == NIC_NAME

        assert netport.network.uuid == NETWORK_ID11

        networks = sorted(networks, key=lambda row: row.uuid)
        assert networks[0].uuid == NETWORK_ID10
        assert len(networks[0].ports) == 1
        assert networks[0].ports[0].uuid == PORT_ID01

        assert networks[1].uuid == NETWORK_ID11
        assert len(networks[1].ports) == 1
        assert networks[1].ports[0].uuid == PORT_ID02

    def test_add_port(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        transaction = mock_idl.Transaction.return_value
        temp_row = OvnNetworkRow(NEW_PORT_ID07)
        transaction.insert.return_value = temp_row
        transaction.get_insert_uuid.return_value = PORT_ID03

        port_rest_data = {
            'name': NIC_NAME,
            'device_id': DEVICE_ID,
            'mac_address': MAC_ADDRESS,
            'network_id': str(NETWORK_ID11)
        }

        ovndb = OvnNbDb(OVN_REMOTE)
        new_port = ovndb.update_port(port_rest_data)

        assert new_port.port.uuid == PORT_ID03
        assert new_port.network.uuid == NETWORK_ID11

        transaction.get_insert_uuid.assert_called_with(NEW_PORT_ID07)

    def test_add_port_fails_due_to_no_device_id(self, mock_idl):
        port_rest_data = {
            'name': NIC_NAME,
            'network_id': str(NETWORK_ID11)
        }
        self._update_port_fails(mock_idl, port_rest_data,
                                PortDeviceIdRequiredDataError)

    def test_add_port_fails_due_to_empty_device_id(self, mock_idl):
        port_rest_data = {
            'name': NIC_NAME,
            'network_id': str(NETWORK_ID11),
            'device_id': ''
        }
        self._update_port_fails(mock_idl, port_rest_data,
                                PortDeviceIdRequiredDataError)

    def test_add_port_fails_due_to_no_network_id(self, mock_idl):
        port_rest_data = {
            'name': NIC_NAME,
            'device_id': DEVICE_ID
        }
        self._update_port_fails(mock_idl, port_rest_data,
                                NetworkIdRequiredForPortDataError)

    def test_add_port_fails_due_to_empty_network_id(self, mock_idl):
        port_rest_data = {
            'name': NIC_NAME,
            'network_id': '',
            'device_id': DEVICE_ID
        }
        self._update_port_fails(mock_idl, port_rest_data,
                                NetworkIdRequiredForPortDataError)

    def _update_port_fails(self, mock_idl, port_rest_data, e):
        TestOvnNbDb.setup_db(mock_idl)
        with pytest.raises(e):
            ovndb = OvnNbDb(OVN_REMOTE)
            ovndb.update_port(port_rest_data)

    def test_delete_unknown_network_fails(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        with pytest.raises(DeletedRowDoesNotExistError):
            ovndb = OvnNbDb(OVN_REMOTE)
            ovndb.delete_network(str(PORT_ID01))

    def test_delete_unknown_port_fails(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        with pytest.raises(DeletedRowDoesNotExistError):
            ovndb = OvnNbDb(OVN_REMOTE)
            ovndb.delete_port(str(NETWORK_ID10))

    def test_delete_network(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        ovndb.delete_network(str(NETWORK_ID12))

        assert ovndb.get_network(str(NETWORK_ID12)).deleted
        assert ovndb.get_subnet(str(SUBNET_ID21)).deleted

        assert not hasattr(ovndb.get_subnet(str(SUBNET_ID20)), 'deleted')
        assert not hasattr(ovndb.get_subnet(str(SUBNET_ID22)), 'deleted')

    def test_modify_port_macaddress(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)
        MODIFIED_MAC = '00:00:00:00:00:76'

        ovndb = OvnNbDb(OVN_REMOTE)
        ovndb.update_port_mac(str(PORT_ID02), MODIFIED_MAC)

        port, network = ovndb.get_port(str(PORT_ID02))
        assert port.addresses[0] == MODIFIED_MAC

    def test_modify_port_macaddress_when_subnet_present(self, mock_idl):
        TestOvnNbDb.setup_db(mock_idl)
        MODIFIED_MAC = '00:00:00:00:00:76'

        ovndb = OvnNbDb(OVN_REMOTE)
        ovndb.update_port_mac(str(PORT_ID04), MODIFIED_MAC)

        port, network = ovndb.get_port(str(PORT_ID04))
        assert port.addresses[0] == MODIFIED_MAC + ' dynamic'

    def _assert_netport(self, netport,  expected_port_id,
                        expected_network_id):
        assert netport.port.uuid == expected_port_id
        assert netport.network.uuid == expected_network_id
