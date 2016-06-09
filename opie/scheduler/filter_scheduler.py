# Copyright (c) 2011 OpenStack Foundation
# Copyright (c) 2015 Spanish National Research Council (CSIC)
# Copyright 2015 INDIGO-DataCloud
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
The FilterScheduler taking into account preemptible instances.
"""

import random

from oslo_config import cfg
from oslo_log import log as logging

from nova import compute
from nova import exception
from nova.i18n import _, _LI
from nova import objects
from nova import rpc
from nova.scheduler import filter_scheduler as nova_filter_scheduler
from nova.scheduler import scheduler_options

CONF = cfg.CONF

opts = [
    cfg.ListOpt('weight_classes',
                default=['nova.scheduler.weights.all_preemptible_weighers'],
                help='Which weight class names to use for weighing the '
                    'selection of preemptible instances for termination'),
]

CONF.register_opts(opts, group="preemptible_instances_scheduler")

CONF.import_opt('cpu_allocation_ratio', 'nova.scheduler.filters.core_filter')
CONF.import_opt('ram_allocation_ratio', 'nova.scheduler.filters.ram_filter')
CONF.import_opt('disk_allocation_ratio', 'nova.scheduler.filters.disk_filter')

LOG = logging.getLogger(__name__)


class FilterScheduler(nova_filter_scheduler.FilterScheduler):
    """Scheduler that will take into account preemptible instances."""
    def __init__(self, *args, **kwargs):
        super(FilterScheduler, self).__init__(*args, **kwargs)
        self.options = scheduler_options.SchedulerOptions()
        self.notifier = rpc.get_notifier('scheduler')

        self.compute_api = compute.API()

#        self.weight_handler = weights.SpotWeightHandler()
#        weigher_classes = self.weight_handler.get_matching_classes(
#                CONF.preemptible.weight_classes)
#        self.weighers = [cls() for cls in weigher_classes]

    def select_destinations(self, context, request_spec, filter_properties):
        """Selects a filtered set of hosts and nodes."""
        self.notifier.info(context, 'scheduler.select_destinations.start',
                           dict(request_spec=request_spec))

        num_instances = request_spec['num_instances']
        selected_hosts = self._schedule(context, request_spec,
                                        filter_properties)

        # Couldn't fulfill the request_spec
        if len(selected_hosts) < num_instances:
            # NOTE(Rui Chen): If multiple creates failed, set the updated time
            # of selected HostState to None so that these HostStates are
            # refreshed according to database in next schedule, and release
            # the resource consumed by instance in the process of selecting
            # host.
            for host in selected_hosts:
                host.obj.updated = None

            # Log the details but don't put those into the reason since
            # we don't want to give away too much information about our
            # actual environment.
            LOG.debug('There are %(hosts)d hosts available but '
                      '%(num_instances)d instances requested to build.',
                      {'hosts': len(selected_hosts),
                       'num_instances': num_instances})

            reason = _('There are not enough hosts available.')
            raise exception.NoValidHost(reason=reason)

        # NOTE(aloga): Detect if we are overcomitting here. If so, we need to
        # delete some preemptible instances
        dests = []
        for host in selected_hosts:
            if (self.detect_overcommit(host.obj) and
                not self._is_preemptible_request(request_spec)):
                preemptibles = self.select_preemptibles_from_host(host.obj,
                                                                  request_spec)
                self.terminate_preemptible_instances(context, preemptibles)

            dests.append(dict(host=host.obj.host, nodename=host.obj.nodename,
                              limits=host.obj.limits))

        self.notifier.info(context, 'scheduler.select_destinations.end',
                           dict(request_spec=request_spec))
        return dests

    def terminate_preemptible_instances(self, context, instances):
        """Terminate the selected preemptible instances."""
        # NOTE(aloga): we should not delete them directly, but probably send
        # them a signal so that the user is able to save her work.
        elevated = context.elevated()
        for instance in instances:
            LOG.info(_LI("Deleting %(uuid)s") % {"uuid": instance["uuid"]})
            instance = self.compute_api.get(elevated,
                                            instance["uuid"],
                                            want_objects=True)
            self.compute_api.delete(elevated, instance)

    def select_preemptibles_from_host(self, host, request):
        """Select preemptible instances to be killed for the request."""
        preemptibles = [i for i in host.instances.values()
                 if i.system_metadata.get("preemptible")]
        # FIXME(aloga): This needs to be fixed, as we are assuming that killing
        # one instance will free enough resources
        return [preemptibles.pop()]

    def detect_overcommit(self, host):
        """Detect overcommit of resources, according to configured ratios."""
        ram_limit = host.total_usable_ram_mb * host.ram_allocation_ratio
        used_ram = host.total_usable_ram_mb - host.free_ram_mb
        if used_ram > ram_limit:
            return True

        disk_limit = host.total_usable_disk_gb * CONF.disk_allocation_ratio
        used_disk = host.total_usable_disk_gb - host.free_disk_mb / 1024.
        if used_disk > disk_limit:
            return True

        cpus_limit = host.vcpus_total * host.cpu_allocation_ratio
        if host.vcpus_used > cpus_limit:
            return True

        return False

    def _schedule(self, context, request_spec, filter_properties):
        """Returns a list of hosts that meet the required specs,
        ordered by their fitness.
        """
        elevated = context.elevated()
        instance_properties = request_spec['instance_properties']

        # NOTE(danms): Instance here is still a dict, which is converted from
        # an object. The pci_requests are a dict as well. Convert this when
        # we get an object all the way to this path.
        # TODO(sbauza): Will be fixed later by the RequestSpec object
        pci_requests = instance_properties.get('pci_requests')
        if pci_requests:
            pci_requests = (
                objects.InstancePCIRequests.from_request_spec_instance_props(
                    pci_requests))
            instance_properties['pci_requests'] = pci_requests

        instance_type = request_spec.get("instance_type", None)

        update_group_hosts = filter_properties.get('group_updated', False)

        config_options = self._get_configuration_options()

        filter_properties.update({'context': context,
                                  'request_spec': request_spec,
                                  'config_options': config_options,
                                  'instance_type': instance_type})

        # Find our local list of acceptable hosts by repeatedly
        # filtering and weighing our options. Each time we choose a
        # host, we virtually consume resources on it so subsequent
        # selections can adjust accordingly.

        # Note: remember, we are using an iterator here. So only
        # traverse this list once. This can bite you if the hosts
        # are being scanned in a filter or weighing function.

        # If the request is for a preemptible instace, take into account all
        # resources used on the host. However, if the request is for a normal
        # instance, do not take into account the preemptible instances. This
        # way we can schedule normal requests even when there is no room for
        # them without doing a retry cycle.

        if self._is_preemptible_request(request_spec):
            hosts = self._get_all_host_states(elevated, partial=False)
        else:
            hosts = self._get_all_host_states(elevated, partial=True)

        hosts_full_state = self._get_all_host_states(elevated, partial=False)

        selected_hosts = []
        num_instances = request_spec.get('num_instances', 1)
        for num in range(num_instances):
            # Filter local hosts based on requirements ...
            hosts = self.host_manager.get_filtered_hosts(hosts,
                    filter_properties, index=num)

            if not hosts:
                # Can't get any more locally.
                break

            LOG.debug("Filtered %(hosts)s", {'hosts': hosts})

            # Get the full host states for weighing. The filtered list of
            # hosts does not take into account preemptible instances, but we
            # need them for weighing

            hosts_full_state = list(hosts_full_state)

            filtered_hosts = {(h.host, h.nodename): h for h in hosts}
            hosts_aux = [h for h in hosts_full_state
                         if (h.host, h.nodename) in filtered_hosts]
            weighed_hosts = self.host_manager.get_weighed_hosts(hosts_aux,
                    filter_properties)

            LOG.debug("Weighed %(hosts)s", {'hosts': weighed_hosts})

            scheduler_host_subset_size = CONF.scheduler_host_subset_size
            if scheduler_host_subset_size > len(weighed_hosts):
                scheduler_host_subset_size = len(weighed_hosts)
            if scheduler_host_subset_size < 1:
                scheduler_host_subset_size = 1

            chosen_host = random.choice(
                weighed_hosts[0:scheduler_host_subset_size])
            LOG.debug("Selected host: %(host)s", {'host': chosen_host})
            selected_hosts.append(chosen_host)

            # Now consume the resources so the filter/weights
            # will change for the next instance.

            # First update the chosen host, that is from the full state list
            chosen_host.obj.consume_from_instance(instance_properties)

            # Now consume from the partial state list
            host = chosen_host.obj.host
            node = chosen_host.obj.nodename
            state_key = (host, node)
            filtered_hosts[state_key].consume_from_instance(
                instance_properties
            )

            # Now continue with the rest of the scheduling function
            if update_group_hosts is True:
                # NOTE(sbauza): Group details are serialized into a list now
                # that they are populated by the conductor, we need to
                # deserialize them
                if isinstance(filter_properties['group_hosts'], list):
                    filter_properties['group_hosts'] = set(
                        filter_properties['group_hosts'])
                filter_properties['group_hosts'].add(chosen_host.obj.host)
        return selected_hosts

    def _get_all_host_states(self, context, partial=False):
        """Template method, so a subclass can implement caching."""
        if partial:
            return self.host_manager.get_all_host_partial_states(context)
        return self.host_manager.get_all_host_states(context)

    def _is_preemptible_request(self, request_spec):
        # NOTE(aloga): this should be removed from here. We should get it from
        # the instance, so that we could change how a preemptible instance is
        # identified.
        instance_properties = request_spec['instance_properties']
        if instance_properties['system_metadata'].get('preemptible'):
            return True
        return False
