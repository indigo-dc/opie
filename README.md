# opie: OpenStack Preemptible Instances Extensions

opie is the materialization of the [preemptible instances extension][1]
serving as a reference implementation.

Preemptible instances only differ from regular ones in that they are subject
to be terminated by a incoming request for provision of a normal instance. If
bidding is in place, this special type of instance could also be stopped by
a higher priority preemptible instance (higher bid). Not all the applications
are suitable for preemptible executions, only fault-tolerant ones can withstand
this type of execution. On the other side they are highly affordable VMs that
allow providers to optimize the usage of their available computing resources
(i.e. backfilling).

This package provides a set of pluggable extensions for
[OpenStack Compute (nova)](http://openstack.org)
making possible to execute premptible instances using a modified filter
scheduler.

In the current implementation a bidding mechanism is not supported, so only
regular instances can terminate preemptible VMs. Note that no suspension is
allowed, preempted machines will no longer be available so that they cannot be
resumed.

[1]: https://blueprints.launchpad.net/openstack/?searchtext=preemptible-instances

opie is completely pluggable, with the exception of a modification in the
internal nova compute API that needs to be applied manually.

In the unfortunate event that bugs are discovered, they should be reported to
the following bug tracker:

   http://github.com/indigo-dc/opie/issues

Developers wishing to work on opie should always base their work on the latest
code, available from the master GIT repository at:

   http://github.com/indigo-dc/opie/

Any new code MUST follow the development guidelines detailed in the HACKING.md
file, and pass all unit tests. Further developer focused documentation is
available at:

   http://docs.openstack.org/developer/nova/

For information on how to contribute to opie, please see the contents of the
CONTRIBUTING.md file.
