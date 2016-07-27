Configuration
=============

Once opie is installed you should enable it in your ``nova.conf`` configuration
file.

opie implements a different host manager and scheduler, compatible with the
original FilterScheduler, so ensure that your configuration file contains the
following in the ``[DEFAULT]`` section::

    [DEFAULT]
    scheduler_driver = opie.scheduler.filter_scheduler.FilterScheduler
    scheduler_host_manager = opie.scheduler.host_manager.HostManager

Moreover, in order to do a proper scheduling, opie implements two additional
weighers:

* ``PreemptibleDurationWeigher``: This weigher assumes that you are charging
  your users on 1h periods, therefire it will assign weights based on 1h-period
  consumptions. This way, the machines with the largest remainder (that is,
  time above 1h-periods) will get the lowest weight. For instance, if machine A
  has 1h 59min it will get a weight lower than a machine with 1h 01min running
  time.

* ``PreemptibleCountWeigher``: This will assign weights based on the number of
  preemptible instances that are running on a host.

You can enable both weighers and its multipliers by adding the following
configuration options to the ``[DEFAULT]`` section::

    scheduler_weight_classes = (...), opie.scheduler.weights.preemptible.PreemptibleDurationWeigher, opie.scheduler.weights.preemptible.PreemptibleCountWeigher
    preemptible_count_weight_multiplier = 1000.0
    preemptible_duration_weight_multiplier = 1000.0

Once the scheduler is configured, ensure that you restart your
``nova-scheduler`` service::

    service nova-scheduler restart
