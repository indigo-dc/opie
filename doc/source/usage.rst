Usage
======

In order to request a preemptible instance, users should add the following
parameter to the JSON POST request for a server creation::

    "preemptible": true

Instead of doing so, you can use the packages relased by the INDIGO-Datacloud
project, installing the ``python-openstackclient`` and ``python-novaclient``
packages instead of your distribution ones. Once you have installed these
packages, you just need to pass the argument ``--preemptible`` to the OpenStack
server creation command::

    openstack server create --preemptible (...)
