reset_scenario
=========

The reset_scenario role removes the ovn control plane entities created through
the network_points.

It can also remove all the dataplane elements - and does so, by default - using
a boolean variable.

Requirements
------------

openstacksdk

Role Variables
--------------

- list of network points
- controller_container_id
- cloud_name

Example Playbook
----------------

    - name: add containers to inventory ...
      hosts: servers
      tasks:
        - add_host:
            name: "{{ controller_container_id }}"
            ansible_connection: docker
            ansible_user: root

    - hosts: servers
      roles:
         - role: reset_scenario
           network_points:
             - name: lport1
               ip: 192.168.10.2
               mac: 00:00:00:11:11:11
               subnet_name: subnet1
               cidr: 192.168.10.0/24
               gateway_ip: 192.168.10.1
               network: net1
               ns: ns1
             - name: lport2
               ip: 192.168.10.3
               mac: 00:00:00:22:22:22
               subnet_name: subnet1
               cidr: 192.168.10.0/24
               gateway_ip: 192.168.10.1
               network: net1
               ns: ns2
           cloud_name: ovirt
           controller_container_id: 3f550c7173fb

License
-------

GPL 2

Author Information
------------------

Miguel Duarte Barroso <mdbarroso@redhat.com> | mbarroso in #ovirt
