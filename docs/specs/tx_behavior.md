
# Specification for Transactional behavior in ovirt-provider-ovn

## Motivation
The ovirt-provider-ovn project is currently a single-threaded RESTful interface
that implements a subset of the
[networking API](https://developer.openstack.org/api-ref/network/v2/)
against an OVN backend - where it stores all the required information.

Provisioning some new data elements - e.g. a subnet, on top of a network - leads
to an update of the network, and a creation of the subnet object, each in a new
isolated transaction.

Most complex operations - e.g. updating security groups on a port - will lead
to a sequence of many different transactions which can leave the system in an
inconsistent state, if one of the transactions fail to commit.

By having each API facing operation start a transaction object, and run every
create/update on that same transaction, we improve the resiliency of the system
and also its determinism.

## Objectives
* have a single user facing transaction for each API request
* all or nothing transactional behavior in ovsdb
* enable bulk provisioning of ports / networks / subnets / ...

## Intended use / desired API
As referrenced on the [motivation](#motivation) section, the main goal is to
open a transaction for each API method, and commit that before returning to
the client. A contextmanager is a perfect match for that.

An OvnTransactionManager class would be required:
```python
class OvnTransactionManager(OvnNbApiIdlImpl):
    def __init__(self, connection):
        super(OvnTransactionManager, self).__init__(connection)
        self._tx = None

    def create_transaction(self, check_error=False, log_errors=True, **kwargs):
        tx = Transaction(
            self, self.ovsdb_connection, self.ovsdb_connection.timeout,
            check_error, log_errors
        )
        self._tx = tx
        return tx

    @contextlib.contextmanager
    def transaction(self, check_error=False, log_errors=True, **kwargs):
        if not self._tx:
            self._tx = self.create_transaction(check_error, log_errors)
        try:
            yield self._tx
        finally:
            self._tx = None

```

Then, the client would use it as shown below (example to create a network):
```python
@NetworkMapper.validate_add
@NetworkMapper.map_from_rest
@NetworkMapper.map_to_rest
def add_network(
    self, name, localnet=None, vlan=None, mtu=None,
    port_security_enabled=None
):
    ovn_network_name = self.generate_ovn_name(name)
    with self.tx_manager.transaction() as tx:
        if localnet:
	    self._add_localnet_network(
	        ovn_network_name, localnet, vlan, mtu,
                port_security_enabled, transaction=tx
	    )
        else:
	    self._create_network(
	        ovn_network_name, mtu, port_security_enabled,
	        transaction=tx
	    )
    return self._get_network(self.ovn_north.get_ls(ls_id=ovn_network_name))
```

## Technical section

### OVN logical port to ovs port binding
Binding an OVN logical switch port to an OVS port is done by setting the
ovs port external IDs *iface-id* key to the OVN logical port name. Hence, the
OVN logical port names have to be unique.

Currently, in the oVirt solution, the OVN logical port is created, OVSDB
generates an UUID for it, and then the provider updates the logical port name,
ensuring the ovsdb generated UUID is set as the port's name.

oVirt engine then generates a libvirt XML interface definition that features
the OVN logical port ID in it. A couple of VDSM hooks are executed as response
to the *before_device_create*/*before_nic_hotplug* events that read that
libvirt XML interface definition, and create an OVS port having as interface
ID the OVN logical port name. This **only** works **because the OVN logical
port ID and name are equal**.

Since the goal of this specification is to use transactions in the provider,
updating the OVN logical port name to feature its ID is **no longer** a
possibility, and two alternatives to address this issue are found in the next
section.

#### Alternative 1
This alternative would involve an update to core OVN.

Ovn north processes the northbound logical_switch_port and logical_router_port
tables and puts each record into a corresponding port_binding record in the
southbound database. The port_binding has a column called "logical_port" which
is set to the name of the logical_switch_port or logical_router_port.

Each OVN controller then checks its corresponding portion of the port_binding
table, and maps that to the OVS ports it has.

By adding a configuration to the OVN nb_global table - a simple boolean,
possibly called *port_binding_by_uuid*, defaulting to **false** - and ways to
perform the comparison in the SB database per UUID instead of per name, the
changes would be limited just to OVN central.

This alternative would fix
[this bug](https://bugzilla.redhat.com/show_bug.cgi?id=1377963), which was
closed because there was an available work-around (update the ovn port name
with the ovn port id).
As previously [discussed](#ovn-logical-port-to-ovs-port-binding), that
work-around is no longer possible.

#### Alternative 2
This alternative would require changes to ovirt-engine, ovirt-provider-ovn, and
ovirt-provider-ovn-driver.

Our current implementation features information that could be used to make this
work. Check this extract of the **vm_interface** table in the engine DB:
```
engine=# select id, vm_guid, mac_addr, name from vm_interface;
                  id                  |               vm_guid                |     mac_addr      | name
--------------------------------------+--------------------------------------+-------------------+------
 655fedc3-a514-4f8f-869f-d105904719d9 | 4e226ac6-82e0-4cb7-b41b-4307c65a0ffd | 56:6f:37:a8:00:00 | nic1
 729c1d96-37d0-4d7e-a297-e3b1e43cf75a | 7a87d4a7-41de-4756-b910-a5e7a353ed63 | 56:6f:37:a8:00:03 | nic1
 a307f1ff-4657-426a-9d2b-d669fa2bd2ac | 9ed22318-bed8-4b27-a52d-974456d390e3 | 56:6f:37:a8:00:04 | nic1
 9d066d54-e41f-458d-93a9-ff698a6c1651 | c4fd86b9-8e24-43bc-9202-af9dc8986813 | 56:6f:37:a8:00:02 | nic1
 5794558a-68b0-4d40-8854-2dd22af6223f | c4fd86b9-8e24-43bc-9202-af9dc8986813 | 56:6f:37:a8:00:05 | nic2
(5 rows)
```

Now check the OVN logical port data:
```
[vagrant@engine-test ~]$ sudo ovn-nbctl list logical_switch_port
_uuid               : e97d9fe9-005c-4106-8eda-20424353ded3
addresses           : ["56:6f:37:a8:00:04 dynamic"]
dhcpv4_options      : 68ca97ea-aac5-4e16-bf77-4fbf2357f37e
dhcpv6_options      : []
dynamic_addresses   : "56:6f:37:a8:00:04 172.20.50.3"
enabled             : true
external_ids        : {ovirt_device_id="a307f1ff-4657-426a-9d2b-d669fa2bd2ac", ovirt_device_owner=oVirt, ovirt_nic_name="e97d9fe9-005c-4106-8eda-20424353ded3", ovirt_security_groups="8a3471e3-ac53-4d57-9990-83056b683acd"}
name                : "e97d9fe9-005c-4106-8eda-20424353ded3"
options             : {}
parent_name         : []
port_security       : ["56:6f:37:a8:00:04"]
tag                 : []
tag_request         : []
type                : ""
up                  : true

_uuid               : 81eb4c11-0f49-4156-80fa-c70925732fc4
addresses           : ["56:6f:37:a8:00:00 dynamic"]
dhcpv4_options      : 68ca97ea-aac5-4e16-bf77-4fbf2357f37e
dhcpv6_options      : []
dynamic_addresses   : "56:6f:37:a8:00:00 172.20.50.4"
enabled             : true
external_ids        : {ovirt_device_id="655fedc3-a514-4f8f-869f-d105904719d9", ovirt_device_owner=oVirt, ovirt_nic_name="81eb4c11-0f49-4156-80fa-c70925732fc4", ovirt_security_groups="8a3471e3-ac53-4d57-9990-83056b683acd"}
name                : "81eb4c11-0f49-4156-80fa-c70925732fc4"
options             : {}
parent_name         : []
port_security       : ["56:6f:37:a8:00:00"]
tag                 : []
tag_request         : []
type                : ""
up                  : true

_uuid               : 8c9a5ce6-707b-4221-b8d1-67921ad0bd31
addresses           : ["56:6f:37:a8:00:03 dynamic"]
dhcpv4_options      : 68ca97ea-aac5-4e16-bf77-4fbf2357f37e
dhcpv6_options      : []
dynamic_addresses   : "56:6f:37:a8:00:03 172.20.50.2"
enabled             : true
external_ids        : {ovirt_device_id="729c1d96-37d0-4d7e-a297-e3b1e43cf75a", ovirt_device_owner=oVirt, ovirt_nic_name="8c9a5ce6-707b-4221-b8d1-67921ad0bd31", ovirt_security_groups="8a3471e3-ac53-4d57-9990-83056b683acd"}
name                : "8c9a5ce6-707b-4221-b8d1-67921ad0bd31"
options             : {}
parent_name         : []
port_security       : ["56:6f:37:a8:00:03"]
tag                 : []
tag_request         : []
type                : ""
up                  : true

_uuid               : 686f9183-094a-4835-a602-71603856330c
addresses           : ["56:6f:37:a8:00:02 dynamic"]
dhcpv4_options      : 68ca97ea-aac5-4e16-bf77-4fbf2357f37e
dhcpv6_options      : []
dynamic_addresses   : "56:6f:37:a8:00:02 172.20.50.5"
enabled             : true
external_ids        : {ovirt_device_id="9d066d54-e41f-458d-93a9-ff698a6c1651", ovirt_device_owner=oVirt, ovirt_nic_name="nic1", ovirt_security_groups="8a3471e3-ac53-4d57-9990-83056b683acd"}
name                : "686f9183-094a-4835-a602-71603856330c"
options             : {}
parent_name         : []
port_security       : ["56:6f:37:a8:00:02"]
tag                 : []
tag_request         : []
type                : ""
up                  : true

```

As can be seen, the **id** of the vm_interfaces matches the ovirt_device_id
of the OVN logical switch ports.

Making this work without any OVS changes would require changing both the
provider and driver (on the ovirt-provider-ovn project), and the ovirt-engine
project.

This proposal requires the **device_id** port attribute to be unique, which
clashes with the networking API v2 specification - it defines the device_id
as a string, without indicating it must be unique.

The changes would be:
* provider: when a port is created, set as it's name the value of the
  'device_id'. Since the device ID parameter is optional, when it is not
  present, generate a UUID, and use that instead.
* ovirt-engine: the port object - which results from the OVN logical port
  creation - will feature the 'device_id' parameter. Set that as a new
  'runtime property' in ovirt-engine - e.g. add a new parameter to the
  [property map](https://github.com/oVirt/ovirt-engine/blob/ovirt-engine-4.3.3.6/backend/manager/modules/bll/src/main/java/org/ovirt/engine/core/bll/provider/network/openstack/BaseNetworkProviderProxy.java#L314).
* driver: update the before_device_create/before_nic_hotplug hooks to use this
  new property instead of the 'vnic_id' property.
* upgrade script: despite the fact that the ovs ports are already bound to the
  OVN logical ports, and thus the data-plane connectivity will not be affected,
  the logical port's state is inconsistent for the ports predating this change.
  To reconcile the system, a simple upgrade script is proposed, in which all
  ports whose creation predates this change have their names updated to the
  *device_id* parameter received via REST.

#### Alternative 3
This alternative is an adaptation of [Alternative #2](#alternative-2), and
would only require changes to ovirt-provider-ovn.

This alternative differs from [Alternative #2](#alternative-2) in that the
**device_id** attribute is not used as port name; instead, a UUID is generated
in the provider, and that is set as the port name - making it unique.

When the created port is reported back to the provider client, the JSON
response would feature the newly create UUID as the port ID.
To make it work, querying a specific port in the database would have to be done
by the name parameter rather than by ID.

No expected performance impacts with this change, since the logical switch port
table is [indexed by name](https://github.com/openvswitch/ovs/blob/master/ovn/ovn-nb.ovsschema#L114).

### Alternative analysis
Alternative two is discarded since it implies changing 2 different projects,
and implies a unique device ID, which is not specified in the networking API.

[Alternative #1](#alternative-1) has the advantage of not requiring any RHV
development, at the expense of plenty of politicizing to be done - this fight
was lost in the past as can be observed in
[bug 1377963](https://bugzilla.redhat.com/show_bug.cgi?id=1377963).
Never the less, the initial contact with the OVN core team was promissing, and
they were receptive to us opening up an RFE for this.

[Alternative #3](#alternative-3) has the advantage of requiring a single simple
provider change, without any known drawbacks.

The chosen alternative is [Alternative #3](#alternative-3), given how simple
it is, and the fact that is doesn't require the attention of any other team,
while preserving the current API.

### Approach
The first step to enable transactional support, is to merge all the
operations that involve a single entity into a single one - e.g. when creating
a port, create the port with all the correct data, instead of creating the port
with the least possible data, then update it with extra stuff (create port;
update address; update port security; update port security groups).

The step above should be done for each entity type and method, and is a step
into getting the code base in place for adding transactional support.

The next step, is actually using transactions to update multiple entities at
once - when adding a subnet, also update the network object to which the subnet
is applied to.
This last step should also be done per entity API method.

### Design plan
The design plan involves an API driven study, focusing on the most complex
parts first. The recommended study order is:
- add_router_interface
- remove_router_interface
- add_port (security group impact)
- update_port (security group impact)
- remove_port
- add_subnet
- update_subnet
- remove_subnet
- add_network
- update_network
- remove_network
- add/remove security group rules
- add/remove security groups
- add/remove static routes
- add/remove routers
...

### API update order
The order of this list might change, depending on the output of the
[Design study](#design).

1. create port
2. create network
3. create physnet (requires creating a network + port)
4. handle security groups
5. create subnet
6. handle routing

