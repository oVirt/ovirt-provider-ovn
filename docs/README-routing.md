# Routing - Implementation of OpenStack Networking API's routers using OVN

oVirt external network provider for OVN provides the ability to manage
OVN's L3 logical routers via a subset of the OpenStack Networking API.

## Connecting a network to a router

To route any traffic from a subnet to another, the subnet must be
connected to a router.
There are two ways in which a subnet can be connected to a router:
 - by subnet id
 - by port id

### Connecting to router by subnet id

When a subnet is connected to a router by subnet id, the gateway IP address
for the subnet is used as an IP address of the created router interface
(https://developer.openstack.org/api-ref/network/v2/index.html#add-interface-to-router).
The subnet propagates the default gateway information via DHCP to the nodes of the subnet.


                    ██████████████████████
                    █   ROUTER router0   █
                    ██████████████████████
                               |
                               | 10.10.0.1 (gw)
                               |
                               |
                      ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
     ┌───────────┐    ▒    net10     ▒       ┌────────────┐
     │ 10.10.0.8 │----▒   subnet10   ▒-------│ 10.10.0.66 │
     └───────────┘    ▒ 10.10.0.0/24 ▒       └────────────┘
                      ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
                              |
                              |
                              |
                        ┌────────────┐
                        │ 10.10.0.99 │
                        └────────────┘

A network can be connected to a router by subnet using the following
request:

```
PUT: http://<host>:9696/v2.0/routers/<router0.id>/add_router_interface
{
    "subnet_id": "<subnet id>"
}
```

oVirt Provider for OVN implements adding a subnet to a router interface by:
- a new LRP (logical router port) is created
- the LRP IP address is set to the default gateway of the subnet
- a new LSP (logical switch port) of type router is created
- LSP's options:router-port is set to the name of the LRP, which connects
  the two ports within OVN

Note that since the IP address of the LRP is set to the IP address of the
subnet's default gateway, a network can be connected only to a single router
because oVirt Provider for OVN supports only a single subnet per network.

### Connecting to router by port

When a network is connected to a router by port, the network port which
will be plugged into the router will be just one of many ordinary port
on that network. Any outgoing network traffic going to that port would
have to be directed to it by appropriate static routes on the nic sending
it (sending traffic to the router port is possible, but not really useful).

A network can be connected to a router by port using the following
request:

 ```
 PUT: http://<host>:9696/v2.0/routers/<router0.id>/add_router_interface
 {
     "port_id": "<port id>"
 }
```

 To add a network to a router by port, the port has to already exist in the
 system. The created router port will assume the ip address used by the port
 added to the router.
 A network can be added by port to as many routers as one only desires (and
 the size of the subnet allows).

## Basic routing

A router will automatically route all traffic between subnets
connected to the same router.
In the network topology below, the networks net10 and net11 are
connected to the router router0, hence router0 needs no additional
configuration to move traffic between these networks.


               ██████████████████████
               █   ROUTER router0   █
               ██████████████████████
                    /           \
    10.10.0.1 (gw) /             \  10.11.0.1 (gw)
                  /               \
                 /                 \
       ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒        ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
       ▒    net10     ▒        ▒    net11      ▒
       ▒   subnet10   ▒        ▒   subnet11    ▒
       ▒ 10.10.0.0/24 ▒        ▒ 10.11.0.0/24  ▒
       ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒        ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
              |                       |
              |                       |
              |                       |
              ▼                       ▼
           net10_port1             net11_port1
        ┌────────────┐            ┌────────────┐
        │ 10.10.0.2  │            │ 10.11.0.2  │
        └────────────┘            └────────────┘



## External gateways

To allow our system to reach the outer world the L3 external gateway mode
extension (ext-gw-mode) can be used.
The external world can be the endless vastness of the internet,  another
network in our datacenter outside the OVN environment, or simply
just another part of the OVN network.
The connection to an external gateway can be configured by specifying the
'provider:physical_network' property of a network. This specifies the
physical network to which our virtual network should be bridged.
We will assume that in our topology net12 is exactly such a network: a
virtual network bridged to a physical network.

The network outside our system would of course also know how to route the
traffic back to our system.
To allow networks net10 and net11 to reach the outer world, router0 has
to be configured to use network12 as it's external gateway.
This can be achieved by updating their router with the following data:

```
PUT: http://<host>:9696/v2.0/routers/<router0.id>
{
    "router": {
        "external_gateway_info": {
            "network_id": "<net12.id>",
            "enable_snat": false,
            "external_fixed_ips": [
                {
                    "ip_address": "10.12.0.100",
                    "subnet_id": "<net12.subnet.id>"
                }
            ]
        },
    }
}
```

This update will trigger the following actions:
- net12 will be connected to router0 (by port)
- the port will be assigned the ip  10.12.0.100 (specified by in "ip_address"
  in the request)
- a default static route will be added to router0, with the nexthop
  being set to the default gateway of net12

                       THE WORLD 🌐
                          ▲
                          | 10.12.0.1  (gw)
                          |
                          |
                     ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒          net12_port1
                     ▒    net12     ▒         ┌────────────┐
                     ▒  subnet12    ▒ ------▶ │ 10.12.0.2  │
                     ▒ 10.12.0.0/24 ▒         └────────────┘
                     ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
                          |
                          |
                          | 10.12.0.100
                          |
                 ██████████████████████
                 █   ROUTER router0   █
                 ██████████████████████
                      /           \
      10.10.0.1 (gw) /             \  10.11.0.1 (gw)
                    /               \
                   /                 \
         ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒        ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
         ▒    net10     ▒        ▒    net11      ▒
         ▒  subnet10    ▒        ▒   subnet11    ▒
         ▒ 10.10.0.0/24 ▒        ▒ 10.11.0.0/24  ▒
         ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒        ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
                |                       |
                |                       |
                |                       |
                ▼                       ▼
             net10_port1             net11_port1
          ┌────────────┐           ┌────────────┐
          │ 10.10.0.2  │           │ 10.11.0.2  │
          └────────────┘           └────────────┘


Note that opposed to net10 and net11, the net12 port connected to
router0 is not its default gateway, but merely one of many ordinary
ports connected to the network.

If we were now to try and ping your favourite website from network net10,
the ping will go to router0 (throught the default gateway 10.10.0.1),
and once inside router0, the default gateway will send it to
10.12.0.1, from where the packet will sail into the fateful world to
reach its destiny.


## Static routes

It might happen that instead of needing to access the internet, we shall
be possesed by a more modest desire to simply access another part of
our OVN based networking topology (even if accessing resources of the
world is almost always much more exciting than accesing items typically
found in OVN based networks).

The network topology below adds another router (router1) and a new network
(net14) to our system. These represent the above-mentioned other part of
the OVN network.
net12 and net14 will be connected directly to router1 by subnet, so traffic
between the two networks will be routed out of the box. If we however want
to access net10 or net11 from network net14, the traffic will enter router1
via 10.14.0.1 (default gateway), but router1 will not know what to do with
these.
This problem can be solved by introducing static routes.

These can be added using the following request:

```
PUT: http://<host>:9696/v2.0/routers/<router1.id>
{
    "router":
        {
            "routes": [
                {
                    "destination": "10.10.0.0/24",
                    "nexthop": "10.12.0.100"
                },
                {
                    "destination": "10.11.0.0/24",
                    "nexthop": "10.12.0.100"
                }
            ]
        }
}
```

Note that we do not require to repeat this for router0, as it was already
updated to include an external gateway.



                  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒             net14_port1
                  ▒      net14      ▒            ┌────────────┐
                  ▒    subnet14     ▒   ------▶  │ 10.14.0.1  │
                  ▒  10.14.0.0/24   ▒            └────────────┘
                  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
                        |
                        |
                        | 10.14.0.1 (gw)
                        |
                ██████████████████████
                █   ROUTER router1   █
                ██████████████████████
                        |
                        | 10.12.0.1  (gw)
                        |
                        |
                   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒           net12_port1
                   ▒    net12     ▒         ┌────────────┐
                   ▒  subnet12    ▒ ------▶ │ 10.12.0.2  │
                   ▒ 10.12.0.0/24 ▒         └────────────┘
                   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
                        |
                        |
                        | 10.12.0.100
                        ▼
               ██████████████████████
               █   ROUTER router0   █
               ██████████████████████
                    /           \
    10.10.0.1 (gw) /             \  10.11.0.1 (gw)
                  /               \
                 ▼                 ▼
       ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒        ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
       ▒    net10     ▒        ▒    net11      ▒
       ▒   subnet10   ▒        ▒   subnet11    ▒
       ▒ 10.10.0.0/24 ▒        ▒ 10.11.0.0/24  ▒
       ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒        ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
              |                       |
              |                       |
              |                       |
              ▼                       ▼
          net10_port1            net11_port1
        ┌────────────┐          ┌────────────┐
        │ 10.10.0.1  │          │ 10.11.0.1  │
        └────────────┘          └────────────┘


If we feel wicked, or just have a bad day and want to upset people
celebrating the newly established connectivity between net10 and net14,
we can clear the static routes using the following query:

```
PUT: http://<host>:9696/v2.0/routers/<router1.id>
{
    "router":
        {
            "routes": []
        }
}
```
which will clear the static routes on router1.
Note that care should be taken when doing this on a router with
the external gateway set, as this might also clear the default static
route required for the external gateway.

