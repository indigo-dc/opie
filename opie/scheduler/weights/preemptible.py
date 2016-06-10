# Copyright 2015 Spanish National Research Council
# Copyright 2016 INDIGO-DataCloud
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
Preemptible instances weighers.
"""

from oslo_config import cfg
from oslo_utils import timeutils

from nova.scheduler import weights

preemptible_weight_opts = [
    cfg.FloatOpt('preemptible_count_weight_multiplier',
                 default=1000.0,
                 help='Multiplier used for weighing hosts based '
                 'on the number of its preemptible instances.'),
    cfg.FloatOpt('preemptible_duration_weight_multiplier',
                 default=1000.0,
                 help='Multiplier used for weighing hosts based '
                 'on the remainder of 1h periods of the running '
                 'time of its preemptible intsances.'),
]

CONF = cfg.CONF
CONF.register_opts(preemptible_weight_opts)


class PreemptibleCountWeigher(weights.BaseHostWeigher):
    maxval = 0

    def weight_multiplier(self):
        """Weight multiplier."""
        return CONF.preemptible_count_weight_multiplier

    def _weigh_object(self, host_state, weight_properties):
        """Higher weights win.

        We do not want a host with preemtible instances selected if there are
        hosts without them.
        """
        count = 0
        for instance in host_state.instances.values():
            if instance.system_metadata.get("preemptible"):
                count += 1
        return - count


class PreemptibleDurationWeigher(weights.BaseHostWeigher):
    maxval = 0

    def weight_multiplier(self):
        """Weight multiplier."""
        return CONF.preemptible_duration_weight_multiplier

    def _weigh_object(self, host_state, weight_properties):
        """Higher weights win.

        We do not want a host with preemtible instances selected if there are
        hosts without them.
        """
        remainder = 0
        for instance in host_state.instances.values():
            if instance.system_metadata.get("preemptible"):
                now = timeutils.utcnow()
                now = now.replace(tzinfo=None)
                ct = instance.created_at.replace(tzinfo=None)
                duration = (now - ct).total_seconds()
                remainder += duration % 3600

        return - remainder
