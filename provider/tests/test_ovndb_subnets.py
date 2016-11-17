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
from ovndb.ndb_api import SubnetConfigError
from ovntestlib import OvnNetworkRow
from ovntestlib import OvnPortRow
from ovntestlib import OvnSubnetRow
from ovntestlib import OvnTable

OVN_REMOTE = 'tcp:127.0.0.1:6641'
ID01 = UUID(int=1)
ID02 = UUID(int=2)
ID03 = UUID(int=3)
ID07 = UUID(int=7)
ID10 = UUID(int=10)
ID11 = UUID(int=11)
ID19 = UUID(int=19)
ID21 = UUID(int=21)
ID22 = UUID(int=22)
ID27 = UUID(int=27)


@mock.patch('ovndb.ovsdb_api.ovs.db.idl', autospec=True)
class TestOvnDbSubnets():

    def setup_db(self, mock_idl):
        port_1 = OvnPortRow(ID01, options={PortMapper.NIC_NAME: 'port1'})
        port_2 = OvnPortRow(ID02, options={PortMapper.NIC_NAME: 'port1'})
        port_3 = OvnPortRow(ID03)
        ports = {
            ID01: port_1,
            ID02: port_2,
            ID03: port_3
        }
        networks = {
            ID10: OvnNetworkRow(ID10, ports=[port_1, port_2]),
            ID11: OvnNetworkRow(ID11)
        }
        subnets = {
            ID21: OvnSubnetRow(ID21, network_id=str(ID10)),
            ID22: OvnSubnetRow(ID22)
        }

        tables = {
            OvnNbDb.NETWORK_TABLE: OvnTable(networks),
            OvnNbDb.PORTS_TABLE: OvnTable(ports),
            OvnNbDb.DHCP_TABLE: OvnTable(subnets)
        }
        mock_idl.Idl.return_value.tables = tables

    def test_get_subnets(self, mock_idl):
        self.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        subnets = ovndb.get_subnets()

        assert len(subnets) == 1
        sorted(subnets, key=lambda row: row.uuid)
        assert subnets[0].uuid == ID21

    def test_get_subnet(self, mock_idl):
        self.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        subnet = ovndb.get_subnet(str(ID21))

        assert subnet.uuid == ID21

    def test_add_subnet(self, mock_idl):
        self.setup_db(mock_idl)
        mock_transaction = mock_idl.Transaction.return_value
        mock_transaction.insert.return_value = OvnSubnetRow(ID27)
        mock_transaction.get_insert_uuid.return_value = ID21

        ovndb = OvnNbDb(OVN_REMOTE)
        subnet = ovndb.update_subnet({
            'name': 'subnet_name',
            'cidr': '10.10.10.0/24',
            'server_mac': 'ma:ca:ad:dr:es',
            'gateway_ip': '10.10.10.255',
            'dns_nameservers': ['1.1.1.1'],
            'network_id': str(ID11),
        })

        assert subnet.uuid == ID21
        network = ovndb.get_network(str(ID11))
        assert network.other_config['subnet'] == '10.10.10.0/24'

    def test_modify_subnet(self, mock_idl):
        self.setup_db(mock_idl)

        ovndb = OvnNbDb(OVN_REMOTE)
        ovndb.update_subnet({
            'id': str(ID21),
            'name': 'subnet_name',
            'cidr': '10.10.10.0/24',
            'server_mac': 'ma:ca:ad:dr:es',
            'gateway_ip': '10.10.10.255',
            'dns_nameservers': ['1.1.1.1'],
            'network_id': str(ID11),
        })

        subnet = ovndb.get_subnet(str(ID21))
        assert subnet.uuid == ID21
        assert subnet.cidr == '10.10.10.0/24'

        options = subnet.options
        assert options['router'] == '10.10.10.255'
        assert options['dns_server'] == '1.1.1.1'

        assert subnet.external_ids['name'] == 'subnet_name'
        assert subnet.external_ids['network_id'] == str(ID11)

    def test_add_second_subnet_to_network_fails(self, mock_idl):
        self.setup_db(mock_idl)
        ovndb = OvnNbDb(OVN_REMOTE)
        with pytest.raises(SubnetConfigError,
                           message='Unable to create more than one subnet '
                           ' for network {}'.format(ID10)):
            ovndb.update_subnet({
                'name': 'subnet_name',
                'cidr': '10.10.10.0/24',
                'server_mac': 'ma:ca:ad:dr:es',
                'gateway_ip': '10.10.10.255',
                'dns_nameservers': ['1.1.1.1'],
                'network_id': str(ID10),
            })

    def test_add_subnet_to_non_existing_network_fails(self, mock_idl):
        self.setup_db(mock_idl)
        ovndb = OvnNbDb(OVN_REMOTE)

        with pytest.raises(SubnetConfigError,
                           message='Subnet can not be created, network {}'
                           ' does not exist'.format(ID19)):
            ovndb.update_subnet({
                'name': 'subnet_name',
                'cidr': '10.10.10.0/24',
                'server_mac': 'ma:ca:ad:dr:es',
                'gateway_ip': '10.10.10.255',
                'dns_nameservers': ['1.1.1.1'],
                'network_id': str(ID19),
            })

    def test_delete_unknown_subnet_fails(self, mock_idl):
        self.setup_db(mock_idl)

        with pytest.raises(DeletedRowDoesNotExistError):
            ovndb = OvnNbDb(OVN_REMOTE)
            ovndb.delete_subnet(str(ID10))
