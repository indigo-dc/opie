# opie: OpenStack Preemptible Instances Extensions

opie is the materialization of the [preemptible instances extension][1]
serving as a reference implementation. This package provides a set of
pluggable extensions for [OpenStack Compute (nova)](http://openstack.org)
making possible to execute premptible instances using a modified filter
scheduler.

[1]: https://blueprints.launchpad.net/openstack/?searchtext=preemptible-instances

opie is completely pluggable, with the exception of a modification in the
internal nova compute API that needs to be applied manually.

In the unfortunate event that bugs are discovered, they should be reported to
the following bug tracker:

   http://github.com/indigo-dc/opie/issues

Developers wishing to work on opie should always base their work on the latest
code, available from the master GIT repository at:

   http://github.com/indigo-dc/opie/

Any new code MUST follow the development guidelines detailed in the HACKING.rst
file, and pass all unit tests. Further developer focused documentation is
available at:

   http://docs.openstack.org/developer/nova/

For information on how to contribute to Nova, please see the contents of the
CONTRIBUTING.md file.
