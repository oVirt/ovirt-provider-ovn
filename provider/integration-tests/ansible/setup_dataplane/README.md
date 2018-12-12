setup_dataplane
=========

This role sets up the data-plane configuration of a sequence of logical ports.

For every network_point it receives, it creates an IP namespace, and an ovs
port, linking it to the corresponding OVN logical switch port. The ovs ports
are made available to the IP namespaces.

The mac & ip addresses of the interfaces (ovs ports) are statically configured
in the guests (IP namespaces) based on the addresses reported by ovn.

The playbook importing this role *needs to* add the ovn controller docker
container to the inventory, by calling the
[add_host](https://docs.ansible.com/ansible/latest/modules/add_host_module.html) module.

Requirements
------------

- openstacksdk

Role Variables
--------------

- list of network points
- controller_container_id
- cloud_name

Example Playbook
----------------

    - name: add controller container to inventory
      hosts: servers
      tasks:
        - add_host:
            name: "{{ controller_container_id }}"
            ansible_connection: docker
            ansible_user: root

    - hosts: servers
      roles:
         - role: setup_dataplane
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
