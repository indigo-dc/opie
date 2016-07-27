.. opie documentation master file, created by
   sphinx-quickstart on Tue Jul  9 22:26:36 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to opie's documentation!
================================

opie is the materialization of the `preemptible instances extension
<https://blueprints.launchpad.net/openstack/?searchtext=preemptible-instances>`_
serving as a reference implementation. This package provides a set of pluggable
extensions for `OpenStack Compute (nova) <http://openstack.org>`_ making
possible to execute premptible instances using a modified filter scheduler.

opie is completely pluggable, with the exception of a modification in the
internal nova compute API that needs to be applied manually.

Contents:

.. toctree::
   :maxdepth: 2

   installation
   configuration

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

