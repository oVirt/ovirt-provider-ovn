# Mapping security group / security group rule ids

## Motivation
The ovirt-provider-ovn project was lately refactored, adding transactional
behavior to security group/port group entities. The relevant patches can be
tracked
[here](https://gerrit.ovirt.org/#/q/topic:transactions+(status:open+OR+status:merged)).

### Security group id mapping update
You can optionally refer to the [annex section](#annex) to consult the data
model used both in the networking API, and in the OVN side.

A security group is a container of security group rules, and the association
between the security group rules and the security groups that contain them,
is done by storing the id of the security group, in a field of the security
group rule.

OVN's design has a particularity that impacted the security group
transactionality: until the transaction is committed, the uuid of the OVN entity
will not be known, and as such, when an OVN port group is created, we will not
know the port group id to set in the ACLs that are automatically added
(by ovirt-provider-ovn) to a newly created port group.

To workaround this issue, we've decided to generate an id in ovirt-provider-ovn,
store that as the 'name' of the port group, and later on, in the neutron api
mappers, return the name of the port group as the id of the security group.
This would be transparent to the user, while allowing us to bypass the issue
described above.

However, on this refactor, one detail was not accounted for, and irresponsible
code coverage let [bug 1744235](https://bugzilla.redhat.com/1744235) slip
through.

The root cause of that bug is that while OVN north accepts port group names
to be strings, OVN controller does not accept the port group names to be
UUID based - when the OVS pipeline is evaluated, the OVN lexer throws an error
indicating the port group names are not compliant with the existent scheme.

This limitation of the port group names is documented in the
[OVN northbound](http://www.openvswitch.org/support/dist-docs/ovn-nb.5.html)
document, in the Port_Group section. It says:
> Names are ASCII and must match [a-zA-Z_.][a-zA-Z_.0-9]*.

Unfortunately for us, this check is done only in the OVS pipeline, and not when
the OVN table is provisioned.

That led to yet another fix - [0] - that again, unfortunately, didn't comply
with all our  requirements. This time, it broke backwards compatibility.
Check section [backwards compatibility](#backwards-compatibility)
for more information. This prevented the release of ovirt-provider-ovn version
[1.2.26](https://github.com/oVirt/ovirt-provider-ovn/commit/f840972c337b23623fe231db78cb5b831e0bd424).

## Objectives
This document will propose an update to the mapping of the security
group/security group rule mapping that will allow for
[bug 1744235](https://bugzilla.redhat.com/1744235) to be fixed, while
preserving backwards compatibility with the latest released ovirt-provider-ovn
version, [1.2.22](https://github.com/oVirt/ovirt-provider-ovn/commit/38acbde6b4eb4654cda4da341bbe8dfc44a6593a).

## Backwards compatibility
Backwards compatibility in this context means the ability to show security
groups/rules created with the latest released version of ovirt-provider-ovn,
which is 1.2.22, after the mapping update proposed in the
[mapping update](#mapping-update) section.

To check that, the integration test environment on the ovirt-provider-ovn
project can be used. The following guidelines should be used:

1. Create the environment
```bash
# checkout the correct code - version 1.2.22
> git checkout 1.2.22
> automation/create_it_env.sh
...
# check the environment was successfully created
> docker ps --format '{{.Names}} {{.Image}} {{.Ports}}'
affectionate_pare maiqueb/ovirt_provider_ovn 0.0.0.0:9696->9696/tcp, 0.0.0.0:35357->35357/tcp
agitated_mclean tripleomaster/centos-binary-ovn-controller:current-tripleo-rdo
objective_chatelet tripleomaster/centos-binary-ovn-northd:current-tripleo-rdo

```

2. copy the following playbook into the repo's root

```

---
- vars:
    cloud: ovirt
    secgroup_name: secgroup_name
  import_playbook: provider/integration-tests/ansible/create_sec_group_api.yml

- name: Create scenario to be checked on upgrades
  hosts: localhost
  gather_facts: no
  vars:
    cloud: ovirt
    secgroup_name: secgroup_name
  tasks:
  - os_network:
      cloud: "{{ cloud }}"
      name: net10
      port_security_enabled: false
  - os_network:
      cloud: "{{ cloud }}"
      name: net11
      port_security_enabled: true
  - os_port:
      cloud: "{{ cloud }}"
      name: net11_port0
      network: net11
      # NOTE: this ports port security will be updated
      port_security_enabled: false
  - os_port:
      cloud: "{{ cloud }}"
      name: net11_port1
      network: net11
      port_security_enabled: true
      no_security_groups: true
  - os_port:
      cloud: "{{ cloud }}"
      name: net11_port2
      network: net11
      port_security_enabled: true
      security_groups:
        - "{{ secgroup_name }}"

```

3. execute the playbook above - notice the ','

```
> ansible-playbook --connection=local --inventory localhost, create_upgrade_check.yml
```

4. update the provider version

```
docker exec -it $PROVIDER_CONTAINER yum update <url_to_provider_rpm>
```

5. repeat step #3. Only the first port should be updated - this happens because
of https://gerrit.ovirt.org/#/c/103367/, which fixes a bug where it was
impossible to configure a port with port_security_enabled=False **if** the
network to which the port belongs to has port_security_enable=True.

## Mapping update
Information about the mapping between networking API entities, and OVN
entities can be found in the [security group feature page](https://www.ovirt.org/develop/release-management/features/network/networking-api-security-groups.html#mapping-networking-api-to-ovn-model-objects).

The association between port groups and ACLs - the 2 OVN entities where the
security groups and security group rules are encoded - remains the same, i.e.
by name, since when creating the port group, along with the auto-provisioned
ACLs, the port group uuid is not available.

What ** changes is the reporting** of the id of the security groups - we will
report the uuid of the OVN port group as id of the networking API security
group.

The following diagrams help understand the relationship:

### Creating a security group - security group encoded as a port group
```
                             neutron API   +   ovirt provider ovn logic    +    OVN DATABASE
                                           |                               |
                                           |                               |
                                           |                               |    +----------------------------------+
                                           |                               |    |   OVN port group object          |
                                           |                               |    +----------------------------------+
                                           |                               |    |                                  |
{                                          |                               |    |     uuid                         |
    "security_group": {                    |   ovirt_<generated_id> +---------------> name                         |
        "name": "new-group", +------------------------------------------------------> external_ids:name            |
        "description": "security group" +-------------------------------------------> external_ids:description     |
    }                                      |                               |    |                                  |
}                                          |                               |    +----------------------------------+
                                           |                               |
                                           |                               |
                                           +                               +

```

The port group name is generated in the ```ovirt_<generated_id>``` format - e.g.
ovirt_702cb151_323b_4836_8b05_44b57f5fa587.

accepted by the OVN controller, and as such, the OVS pipeline succeeds.

Once the port group/ACLs are created - within the scope of a transaction -
OVSDB generates the uuid for the respective OVN entities.

In order to enable the networking API to return the port group uuid as the
security group id, after creating all the OVN entities in the DB, the port group
is read - by name. This port group - featuring the OVSDB generated uuid - is
afterwards translated into a security group. Again, more information about
mapping the port group into a security group can be found in the
[security group feature page](https://www.ovirt.org/develop/release-management/features/network/networking-api-security-groups.html#mapping-networking-api-to-ovn-model-objects).

### GET security group(s) - port group to ACL association
As per the [networking API](https://docs.openstack.org/api-ref/network/v2/#security-groups-security-groups),
it's ```list``` and ```show``` API methods also list the respective security
group rules.

Take for instance the ```show``` security group method: it receives the
security group id as an input. It will then fetch the OVN port group, using the
the id of the security group as the uuid of the port group. Once the
port group is retrieved, we proceed to list all the OVN ACLs that have this
group's name in it's external_ids 'security_group_id' column, then convert
those ACLs into networking API security group rules. This association is
shown in the figure below.

```
OVN DATABASE

+----------------------------------+                  +-------------------------------------------+
|   OVN port group object          |                  |      OVN acl object                       |
+----------------------------------+                  +-------------------------------------------+
|                                  |                  |     id                                    |
|     id                           |                  |     name                                  |
|     name +----------------------------------------------> external_ids:security_group_id        |
|     external_ids:name            |                  |     ...                                   |
|     external_ids:description     |                  +-------------------------------------------+
|                                  |
+----------------------------------+

```

### GET security group rule(s)
When reading security group rule objects, we read the corresponding ACL
object by id - since we report the ACL uuid as the security group rule id when
an ACL is created.

As pictured above, OVN ACL's external_ids contain the security group name
(external_ids:security_group_id). Hence, this parameter needs to be mapped back
to the correct security group id. To do so, we read - by name - the OVN port
group whose name is stored in the ACL's external_ids, and use its uuid as
security group id.

This translation involves an extra step, since when we read a networking API
security group rule, we must read - by id - the OVN ACL it is represented by.
We read the OVN port group identified by the OVN port group name stored in its
external_ids map, from which we return the correct security group id - which is
the OVN port group's uuid.

When the rule features the remote_group_id parameter, it is extra-costly,
because of the corner case of the default security group - where the remote
group id refers to the group that holds the rule, and those are created within
the same transaction. This makes us also store the security group rule remote
group id as the name of the group, and again, cause an extra read of that port
group to extract the correct uuid.

### Required Mapper changes
To make this work, the ```SecurityGroupRule``` object is updated, in the
following way:

```python
class SecurityGroupRule(object):
    default_group_id = None

    def __init__(self, rule, security_group, default_security_group=None):
        self.__rule = rule
        self.__sec_group = security_group
        self._set_default_sec_group_id(default_security_group)

    @property
    def rule(self):
        return self.__rule

    @property
    def security_group(self):
        return self.__sec_group
...
```

The rule now holds a reference to the security group that holds it, so
that in all neutron_api_mappers operations it can substitute the security_group
id with the correct security group ID.

The security groups already had a list of references to
the ```SecurityGroupRule``` object, and as such, when listing security groups,
or getting a particular group, which are operations that will in turn list the
rules associated to the group, the same replacement technique is possible.

## Annex

### Networking API data model
Below you can find a JSON representation of a security group - having a
security group rule within it.

It shows the security group in json representation, and in section
[OVN data model](#ovn-entities-data-model) it also the OVN port group object it
is represented by. An example of an OVN ACL object can also be found.

Only the relevant attributes for this discussion are shown.

```
{
    "security_group": {
        "description": "a security group",
        "id": "85cc3048-abc3-43cc-89b3-377341426ac5",
        "name": "custom security group",
        "security_group_rules": [
            {
                "id": "be55ff6f-78d0-45a7-8a89-7aa7eabc4689",
                "remote_group_id": "85cc3048-abc3-43cc-89b3-377341426ac5",
                "security_group_id": "85cc3048-abc3-43cc-89b3-377341426ac5",
		...
            }
        ]
    }
}
```

### OVN entities data model
The OVN database for port groups/ACLs is defined in the following way:
```
   +----------------------------------+
   |     OVN Port Group               |
   +----------------------------------+
   |                                  |
   |     uuid                         |
   |     name                         |
   |     acls                         |
   |     ports                        |
   |     external_ids:name            |
   |     external_ids:description     |
   |                                  |
   +----------------------------------+

   +----------------------------------+
   |     OVN ACL                      |
   +----------------------------------+
   |                                  |
   |     uuid                         |
   |     name                         |
   |     external_ids:port_group_id   |
   |     external_ids:remote_group_id |
   |                                  |
   +----------------------------------+
```
#### OVN DB example - Port Group
Below you can see the port group table state when provisioned.

```
_uuid               : 85cc3048-abc3-43cc-89b3-377341426ac5
acls                : [2f0d193f-18d2-41bc-b059-cd813b34cb67, 9315596b-78ec-4ee3-92e2-585888d37341, ad0d3641-bda2-4513-8a7c-aaa5f6e550f6, b6a562c1-a49e-4ee3-b060-fc9a43954101, be55ff6f-78d0-45a7-8a89-7aa7eabc4689, c10dc6a7-a512-4787-9688-e226cbac2683, f83a8934-d35b-466a-bb6b-f1950bcd07d2]
external_ids        : {ovirt_created_at="2019-09-26T07:45:43.435332", ovirt_description="Created from Ansible playbook", ovirt_revision_number="6", ovirt_sec_group_name=secgroup_name, ovirt_updated_at="2019-09-26T07:45:43.435332"}
name                : "ovirt_702cb151_323b_4836_8b05_44b57f5fa587"
ports               : [7084fbd9-0f9a-4f74-a484-35760c8a7a3f]
```

#### OVN DB example - ACL
Below you can see the ACL table state when provisioned.

```
_uuid               : be55ff6f-78d0-45a7-8a89-7aa7eabc4689
action              : allow-related
direction           : to-lport
external_ids        : {ovirt_ethertype="IPv4", ovirt_ip_prefix="0.0.0.0/0", ovirt_max_port="80", ovirt_min_port="80", ovirt_port_group_id="ovirt_702cb151_323b_4836_8b05_44b57f5fa587", ovirt_protocol=tcp}
log                 : false
match               : "outport == @ovirt_702cb151_323b_4836_8b05_44b57f5fa587 && ip4 && ip4.src == 0.0.0.0/0 && tcp && tcp.dst == 80"
meter               : []
name                : "9cd8817f-c5cc-4e8f-a0d5-3c84c9d74b8c"
priority            : 1001
severity            : alert
```

[0] - https://gerrit.ovirt.org/#/c/102728/
