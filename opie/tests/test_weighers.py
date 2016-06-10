# Copyright 2016 Spanish National Research Council - CSIC
# Copyright 2016 INDIGO-DataCloud
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from opie.scheduler.weights import preemptible

from nova.scheduler import weights
from nova import test as nova_test
from nova.tests.unit import fake_instance
from nova.tests.unit.scheduler import fakes
from oslo_utils import timeutils


class PreemptibleCountWeigherTestCase(nova_test.NoDBTestCase):
    def setUp(self):
        super(PreemptibleCountWeigherTestCase, self).setUp()
        self.weight_handler = weights.HostWeightHandler()
        self.weighers = [preemptible.PreemptibleCountWeigher()]

    def _get_weighed_hosts(self, hosts, weight_properties=None):
        if weight_properties is None:
            weight_properties = {}
        return self.weight_handler.get_weighed_objects(self.weighers,
                hosts, weight_properties)

    def _get_all_hosts(self):
        host_states = [
            fakes.FakeHostState('host1', 'node1', {}),
            fakes.FakeHostState('host2', 'node2', {}),
            fakes.FakeHostState('host3', 'node3', {}),
            fakes.FakeHostState('host4', 'node4', {})
        ]
        for idx, host in enumerate(host_states):
            instances = {
                "normal instance": fake_instance.fake_instance_obj(
                    "fake context", uuid="normal instance")
            }
            instances["normal instance"].system_metadata = {}

            for i in range(idx):
                uuid = 'uuid-%s-%d' % (host.host, i)
                instances[uuid] = fake_instance.fake_instance_obj(
                    "fake context", uuid=uuid)
                instances[uuid].system_metadata = {"preemptible": True}

            host.instances = instances
        return host_states

    def test_default(self):
        hostinfo_list = self._get_all_hosts()

        # host1: 0 preemptible
        # host2: 1 preemptible
        # host3: 2 preemptible
        # host4: 3 preemptible

        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        # so host1 should win:
        self.assertEqual(1000.0, weighed_hosts[0].weight)
        self.assertEqual('host1', weighed_hosts[0].obj.host)

        self.assertEqual('host2', weighed_hosts[1].obj.host)
        self.assertEqual('host3', weighed_hosts[2].obj.host)

        # and host4 lose
        self.assertEqual(0.0, weighed_hosts[3].weight)
        self.assertEqual('host4', weighed_hosts[3].obj.host)

    def test_negative_multiplier(self):
        self.flags(preemptible_count_weight_multiplier=-1.0)
        hostinfo_list = self._get_all_hosts()

        # host1: 0 preemptible
        # host2: 1 preemptible
        # host3: 2 preemptible
        # host4: 3 preemptible

        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        # order is reversed, so host4 should win
        self.assertEqual(0.0, weighed_hosts[0].weight)
        self.assertEqual('host4', weighed_hosts[0].obj.host)

        self.assertEqual('host3', weighed_hosts[1].obj.host)
        self.assertEqual('host2', weighed_hosts[2].obj.host)

        # and host1 lose
        self.assertEqual(-1.0, weighed_hosts[3].weight)
        self.assertEqual('host1', weighed_hosts[3].obj.host)

    def test_multiplier(self):
        self.flags(preemptible_count_weight_multiplier=2.0)
        hostinfo_list = self._get_all_hosts()

        # host1: 0 preemptible
        # host2: 1 preemptible
        # host3: 2 preemptible
        # host4: 3 preemptible

        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        # so host1 should win:
        self.assertEqual(2.0, weighed_hosts[0].weight)
        self.assertEqual('host1', weighed_hosts[0].obj.host)

        self.assertEqual('host2', weighed_hosts[1].obj.host)
        self.assertEqual('host3', weighed_hosts[2].obj.host)

        # and host4 lose
        self.assertEqual(0.0, weighed_hosts[3].weight)
        self.assertEqual('host4', weighed_hosts[3].obj.host)

    def test_multiplier_zero(self):
        self.flags(preemptible_count_weight_multiplier=0)
        hostinfo_list = self._get_all_hosts()

        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        for host in weighed_hosts:
            self.assertEqual(0.0, host.weight)


class PreemptibleDurationWeigherTestCase(nova_test.NoDBTestCase):
    def setUp(self):
        super(PreemptibleDurationWeigherTestCase, self).setUp()
        self.weight_handler = weights.HostWeightHandler()
        self.weighers = [preemptible.PreemptibleDurationWeigher()]

    def _get_weighed_hosts(self, hosts, weight_properties=None):
        if weight_properties is None:
            weight_properties = {}
        return self.weight_handler.get_weighed_objects(self.weighers,
                hosts, weight_properties)

    def _get_all_hosts(self):
        host_states = [
            fakes.FakeHostState('host1', 'node1', {}),
            fakes.FakeHostState('host2', 'node2', {}),
            fakes.FakeHostState('host3', 'node3', {}),
            fakes.FakeHostState('host4', 'node4', {})
        ]
        for idx, host in enumerate(host_states):
            instances = {
                "normal": fake_instance.fake_instance_obj(
                    "fake context", uuid="normal"),
                "preemptible": fake_instance.fake_instance_obj(
                    "fake context", uuid="preemptible"),
            }
            instances["normal"].system_metadata = {}
            instances["preemptible"].system_metadata = {"preemptible": True}
            instances["preemptible"].created_at = datetime.datetime(
                2015, 11, 5, 10, idx)

            host.instances = instances
        return host_states

    def test_default(self):
        hostinfo_list = self._get_all_hosts()

        # host1: 0, running time 01:00
        # host2: 1, running time 00:59
        # host3: 2, running time 00:58
        # host4: 3, running time 00:57

        # So the ordering should be host1, host4, host3, host2
        now = datetime.datetime(2015, 11, 5, 11, 00)
        timeutils.set_time_override(now)
        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        # so host1 should win:
        self.assertEqual(1000.0, weighed_hosts[0].weight)
        self.assertEqual('host1', weighed_hosts[0].obj.host)

        self.assertEqual('host4', weighed_hosts[1].obj.host)
        self.assertEqual('host3', weighed_hosts[2].obj.host)

        # and host2 lose
        self.assertEqual(0.0, weighed_hosts[3].weight)
        self.assertEqual('host2', weighed_hosts[3].obj.host)

    def test_negative_multiplier(self):
        self.flags(preemptible_duration_weight_multiplier=-1.0)
        hostinfo_list = self._get_all_hosts()

        # host1: 0, running time 01:00
        # host2: 1, running time 00:59
        # host3: 2, running time 00:58
        # host4: 3, running time 00:57

        # So the ordering should be host1, host4, host3, host2 but
        # order is reversed, so host2 should win

        now = datetime.datetime(2015, 11, 5, 11, 00)
        timeutils.set_time_override(now)
        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        self.assertEqual(0.0, weighed_hosts[0].weight)
        self.assertEqual('host2', weighed_hosts[0].obj.host)

        self.assertEqual('host3', weighed_hosts[1].obj.host)
        self.assertEqual('host4', weighed_hosts[2].obj.host)

        # and host1 lose
        self.assertEqual(-1.0, weighed_hosts[3].weight)
        self.assertEqual('host1', weighed_hosts[3].obj.host)

    def test_multiplier(self):
        self.flags(preemptible_duration_weight_multiplier=2.0)
        hostinfo_list = self._get_all_hosts()

        # host1: 0, running time 01:00
        # host2: 1, running time 00:59
        # host3: 2, running time 00:58
        # host4: 3, running time 00:57

        # So the ordering should be host1, host4, host3, host2
        now = datetime.datetime(2015, 11, 5, 11, 00)
        timeutils.set_time_override(now)
        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        # so host1 should win:
        self.assertEqual(2.0, weighed_hosts[0].weight)
        self.assertEqual('host1', weighed_hosts[0].obj.host)

        self.assertEqual('host4', weighed_hosts[1].obj.host)
        self.assertEqual('host3', weighed_hosts[2].obj.host)

        # and host2 lose
        self.assertEqual(0.0, weighed_hosts[3].weight)
        self.assertEqual('host2', weighed_hosts[3].obj.host)

    def test_multiplier_zero(self):
        self.flags(preemptible_duration_weight_multiplier=0)
        hostinfo_list = self._get_all_hosts()

        # We don't mock as we don't care about the duration, all will be
        # equaled to 0
        weighed_hosts = self._get_weighed_hosts(hostinfo_list)

        for host in weighed_hosts:
            self.assertEqual(0.0, host.weight)
