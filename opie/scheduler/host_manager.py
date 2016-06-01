# Copyright (c) 2011 OpenStack Foundation
# Copyright (c) 2016 Spanish National Research Council (CSIC)
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
Manage hosts in the current zone taking into account spot instances.
"""

import iso8601
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils

from nova.i18n import _LI, _LW  # noqa
from nova import objects
from nova.scheduler import host_manager as nova_host_manager

CONF = cfg.CONF
CONF.import_opt('scheduler_tracks_instance_changes',
                'nova.scheduler.host_manager')
CONF.import_opt('scheduler_weight_classes', 'nova.scheduler.host_manager')
CONF.import_opt('scheduler_default_filters', 'nova.scheduler.host_manager')
CONF.import_opt('scheduler_available_filters', 'nova.scheduler.host_manager')

LOG = logging.getLogger(__name__)


class HostStatePartial(nova_host_manager.HostState):
    def __init__(self, *args, **kwargs):
        super(HostStatePartial, self).__init__(*args, **kwargs)
        self.normal_instances = {}
        self.spot_instances = {}
        self._instances = {}

    @property
    def instances(self):
        return self._instances

    @instances.setter
    def instances(self, instances):
        for instance in instances.values():
            if instance.uuid in self.instances:
                continue

            if instance.system_metadata.get("preemptible"):
                self.spot_instances[instance.uuid] = instance
                self._unconsume_from_instance(instance)
            else:
                self.normal_instances[instance.uuid] = instance

        self._instances = instances

    @nova_host_manager.set_update_time_on_success
    def _unconsume_from_instance(self, instance):
        """Incrementally update host state from an instance."""
        disk_mb = (instance['root_gb'] + instance['ephemeral_gb']) * 1024
        ram_mb = instance['memory_mb']
        vcpus = instance['vcpus']
        self.free_ram_mb += ram_mb
        self.free_disk_mb += disk_mb
        self.vcpus_used -= vcpus

        now = timeutils.utcnow()
        # NOTE(sbauza): Objects are UTC tz-aware by default
        self.updated = now.replace(tzinfo=iso8601.iso8601.Utc())

        # Track number of instances on host
        self.num_instances -= 1

    def __repr__(self):
        return ("(%s, %s) ram:%s disk:%s io_ops:%s instances:%s (spot:%s)" %
                (self.host, self.nodename, self.free_ram_mb, self.free_disk_mb,
                 self.num_io_ops, self.num_instances,
                 len(self.spot_instances)))


class HostManager(nova_host_manager.HostManager):
    def __init__(self):
        super(HostManager, self).__init__()
        self.host_state_map_partial = {}

    def get_all_host_states(self, context):
        """Returns a list of HostStates that represents all the hosts the
        HostManager knows about.
        """
        return self._get_all_host_states(context, partial=False)

    def get_all_host_partial_states(self, context):
        """Returns a list of HostStates that represents all the hosts the
        HostManager knows about, without taking into account spot instances.
        """
        return self._get_all_host_states(context, partial=True)

    def _get_all_host_states(self, context, partial=False):
        """Returns a list of HostStates that represents all the hosts
        the HostManager knows about. Also, each of the consumable resources
        in HostState are pre-populated and adjusted based on data in the db.

        :param partial: if partial is False (the default) it will take into
                        account all instances running in the host (i.e.
                        preemptible and normal instances). If partial is True,
                        preemptible instances will not be taken into account,
                        so their consumed resources will considered as free.
        """
        service_refs = {service.host: service
                        for service in objects.ServiceList.get_by_binary(
                            context, 'nova-compute')}
        # Get resource usage across the available compute nodes:
        compute_nodes = objects.ComputeNodeList.get_all(context)
        seen_nodes = set()
        for compute in compute_nodes:
            service = service_refs.get(compute.host)

            if not service:
                LOG.warning(_LW(
                    "No compute service record found for host %(host)s"),
                    {'host': compute.host})
                continue
            host = compute.host
            node = compute.hypervisor_hostname
            state_key = (host, node)
            host_state = self.host_state_map.get(state_key)
            host_state_partial = self.host_state_map_partial.get(state_key)
            if host_state and host_state_partial:
                host_state.update_from_compute_node(compute)
            else:
                host_state = self.host_state_cls(host, node, compute=compute)
                host_state_partial = HostStatePartial(host, node,
                                                      compute=compute)
                self.host_state_map[state_key] = host_state
                self.host_state_map_partial[state_key] = host_state_partial
            # We force to update the aggregates info each time a new request
            # comes in, because some changes on the aggregates could have been
            # happening after setting this field for the first time
            for aux in (host_state, host_state_partial):
                aux.aggregates = [self.aggs_by_id[agg_id] for agg_id in
                                  self.host_aggregates_map[
                                      aux.host]]
                aux.update_service(dict(service.iteritems()))
                self._add_instance_info(context, compute, aux)

            seen_nodes.add(state_key)

        # remove compute nodes from host_state_map if they are not active
        dead_nodes = set(self.host_state_map.keys()) - seen_nodes
        for state_key in dead_nodes:
            host, node = state_key
            LOG.info(_LI("Removing dead compute node %(host)s:%(node)s "
                         "from scheduler"), {'host': host, 'node': node})
            del self.host_state_map[state_key]
            del self.host_state_map_partial[state_key]

        if partial:
            return self.host_state_map_partial.itervalues()
        else:
            return self.host_state_map.itervalues()
