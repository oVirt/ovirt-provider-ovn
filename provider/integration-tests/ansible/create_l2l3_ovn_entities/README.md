create_l2l3_ovn_entities
=========

This role can be used to create simple L2 / L3 network scenarios through
OpenStack's networking API.

It creates Networks, Subnets, and Ports, through the ovirt-provider-ovn
docker container.

Requirements
------------

This role uses the OpenStack ansible modules, so it has the following
dependencies:

- openstacksdk

Role Variables
--------------

This role relies on two core abstractions: the 'network_point', and the 'router'.
A network point represents a logical port, but it features all L2 and L3
information for the port's dependencies to be created (its network, and
subnet).

A router, represents an OVN logical router, and information about which subnets
it connects.

An example of the expected 'network_points', and 'router' inputs can be found
below:
```python
{
    'network_points': [
        {
            'name': 'lport1',
            'ip': '192.168.10.2',
            'mac': '00:00:00:11:11:11',
            'subnet_name': 'subnet1',
            'cidr': '192.168.10.0/24',
            'gateway_ip': '192.168.10.1',
            'network': 'net1',
            'ns': 'ns1',
            'ipv6_address_mode': 'dhcpv6_stateless'
        },
        {
            'name': 'lport2',
            'ip': '192.168.10.3',
            'mac': '00:00:00:22:22:22',
            'subnet_name': 'subnet1',
            'cidr': '192.168.10.0/24',
            'gateway_ip': '192.168.10.1',
            'network': 'net1',
            'ns': 'ns2',
            'ipv6_address_mode': 'dhcpv6_stateless'
        }
    ],
    'routers': [
        {
            'name': 'router0',
            'interfaces': [
                'subnet1'
            ]
        }
    ]
}
```

This role also requires the following variables:
  - cloud_name: the cloud name as defined in the clouds.yml file

It is important to assure the **gateway_ip** / **cidr** / **ip** /
**ipv6_address_mode** values of the network point are the same in all
network_points, unless the user wants to update the subnet.

The list of routers is an **optional** attribute.

Example Playbook
----------------

    - hosts: servers
      roles:
         - role: create_l2l3_ovn_entities
           network_points:
             - name: lport1
               ip: 192.168.10.2
               mac: 00:00:00:11:11:11
               subnet_name: subnet1
               cidr: 192.168.10.0/24
               gateway_ip: 192.168.10.1
               network: net1
               ns: ns1
               ipv6_address_mode: dhcpv6_stateless
             - name: lport2
               ip: 192.168.10.3
               mac': 00:00:00:22:22:22
               subnet_name: subnet1
               cidr: 192.168.10.0/24
               gateway_ip: 192.168.10.1
               network: net1
               ns: ns2
               ipv6_address_mode: dhcpv6_stateless
           routers:
             - name: router0
               interfaces:
                 - subnet1
           cloud_name: ovirt

License
-------

GPL 2

Author Information
------------------

Miguel Duarte Barroso <mdbarroso@redhat.com> | mbarroso in #ovirt
