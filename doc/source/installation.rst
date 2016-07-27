Installation
============

opie depends on the OpenStack Compute (nova) version that you are using.
Currently it is only tested with OpenStack Compute Liberty (version 12.0.X), so
you need to ensure that you are running that specific version.

Installation via Ubuntu/Debian packages
---------------------------------------

Add the opie PPA to your system manually, by copying the linbes below and
adding them to your system's software sources::

    deb http://ppa.launchpad.net/aloga/opie/ubuntu trusty main
    deb-src http://ppa.launchpad.net/aloga/opie/ubuntu trusty main

Then, you can install it via apt-get::

    apt-get update
    apt-get install opie

Installation via pip
--------------------

At the command line you can install::

    $ pip install opie

Paching nova compute API
------------------------

Unfortunately, even if opie is desinged to exploit nova's modularity, there is
a manual patch that needs to be applied. Execute the following command to save
the patch::

    cat > /tmp/nova-compute-api.patch << EOF

    EOF

And apply the patch as follows:

* Ubuntu/Debian::

    cd /usr/lib/python2.7/dist-packages/nova
    patch -p1 < /tmp/nova-compute-api.patch

* RedHat/CentOS::

    cd /usr/lib/python2.7/site-packages/nova
    patch -p1 < /tmp/nova-compute-api.patch

Once this is done, ensure that you restart your ``nova-api`` service::

    service nova-api restart
