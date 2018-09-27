
# Specification for ovirt-provider-ovn integration testing

## Motivation

There currently is a huge gap in the testability of the ovirt-provider-ovn; the
project has unit tests, which test individual functional modules within in, and
there is another ovirt project - [oVirt system tests][https://github.com/oVirt/ovirt-system-tests] -
that tests the whole end to end oVirt flows.

This means that there is no way for a developer to get short feedback from the
code, focusing only on the provider.

## Objectives

Deliver a solution that enables integration tests for the provider.
The solution should check the objects returned by the API **and**, and also
check that the supplied configurations are working - for example, if ping works
when security groups are configured accordingly.

The same framework should be also leveraged for ovirt-provider-ovn demos, and
manual testing.

## User flows

The user intervention is supposed to be minimal, and in order to allow multiple
use cases, creating the test environment, and executing the tests are two
different stages.

1. create integration tests environment

   The environment, along with all the required dependencies should be
   created, and configured.

   The intended way of interacting with the environment is through the
   REST API - or ansible.


2. the user can interact with the integration tests environment

   There are two types of users taken into account, each with different
   expectations and requirements:
    - integration tests
      * Each test should cleanup after itself.
      * Tests are idempotent.
    - physical user - aka a human user.

## Technical section

### Techonologies / tools to be leveraged

- docker
- ansible
- tox

The steps on the tests would be:
  - create environment: docker will be used to create the components of the
integration test environment. The components are:
    * **ovn-controller**

      Up to N ovn-controller containers will be used, depending
      on the use case.

      The most common scenario will feature a single controller
      container.
    * **ovn-central**

      One single container running ovn-central - ovn-north + ovn-south - and their      respective daemons and ovsdb instances. The aforementioned ovn-controllers
      will register themselves as chassis in the ovn-sb ovsdb database.
    * **ovirt-provider-ovn**

      The hypervisor host running the containers will create the ovirt-provider-ovn rpms, and inject them - as volumes - into the provider container.

      The provider container will, at runtime, install the provider rpms, configure its connection to ovn-central container, and finally, start the provider service.

      The ovirt-provider-ovn container exposes ports 9696 & 35357 - which means that requests sent to `localhost:9696` (or port 35357) will be forwarded to the ovirt-provider-ovn container.

  - The packaging step will be done outside of tox. It will use the project's Makefile to generate the provider's SRPM, which will be mounted in the ovirt-provider-ovn container.

    During the integration script test run, the container will build the RPMs using the mounted SRPM as input, and afterwards install those - along with its dependencies. Afterwards, the provider service is
configured, and started.

  - configure the provider: ansible is the tool used to configure the
environment, and the provider.

  - tox scripts: this step will configure the provider accordingly, and execute
the commands to assert the correct behavior of the provider - be it ping, curl,
etc. Ansible could be also used to create complex scenarios, depending on the
use case. Doing that allows the tests to become user side documentation on how
to trigger certain scenarios.

### Code structure
```
+ automation/
  * containers/			# dockerfiles for the images
    - ovirt-provider-ovn/
    - ovn-controller/
    - ovn-central/
  * create_it_env.sh		# create a disposable integration test env
+ provider/
  * it-tests/
    - ansible/			# ansible playbooks & roles used in tests
    - pytest/			# all the tests will be here
      + lib/			# integration test related libraries
      + test_security_groups.py
      + ...py
```
