# Copyright 2016 Spanish National Research Council - CSIC
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

from opie.scheduler import filter_scheduler

import mock
from nova.compute import task_states
from nova.compute import vm_states
from nova import exception
from nova.scheduler import weights
from nova.tests.unit import fake_instance
from nova.tests.unit.scheduler import fakes
from nova.tests.unit.scheduler import test_filter_scheduler \
        as nova_test_filter_scheduler
from nova.tests.unit.scheduler import test_scheduler


class FilterSchedulerTestCase(nova_test_filter_scheduler.
                              FilterSchedulerTestCase):

    driver_cls = filter_scheduler.FilterScheduler

    def setUp(self):
        self.flags(
            scheduler_host_manager='opie.scheduler.host_manager.HostManager'
        )

        super(FilterSchedulerTestCase, self).setUp()

    @mock.patch.object(filter_scheduler.FilterScheduler, 'detect_overcommit')
    @mock.patch.object(filter_scheduler.FilterScheduler, '_schedule')
    def test_select_destinations_notifications(self, mock_schedule,
                                               mock_detect):
        mock_schedule.return_value = [mock.Mock()]
        mock_detect.return_value = False

        with mock.patch.object(self.driver.notifier, 'info') as mock_info:
            request_spec = {'num_instances': 1}

            self.driver.select_destinations(self.context, request_spec, {})

            expected = [
                mock.call(self.context, 'scheduler.select_destinations.start',
                 dict(request_spec=request_spec)),
                mock.call(self.context, 'scheduler.select_destinations.end',
                 dict(request_spec=request_spec))]
            self.assertEqual(expected, mock_info.call_args_list)


class OpieFilterSchedulerTestCase(test_scheduler.SchedulerTestCase):
    driver_cls = filter_scheduler.FilterScheduler

    def setUp(self):
        self.flags(
            scheduler_host_manager='opie.scheduler.host_manager.HostManager'
        )

        super(OpieFilterSchedulerTestCase, self).setUp()

    def test_detect_preemptible(self):
        # FIXME(aloga): Right now this is almost useless. We should get the
        # request spect from the compute API, so that if we modify it there we
        # are able to detect it here...
        request_spec = {
            'instance_properties': {
                'system_metadata': {
                    'preemptible': True,
                }
            }
        }

        self.assertTrue(self.driver._is_preemptible_request(request_spec))

    def test_detect_preemptible_false(self):
        # FIXME(aloga): Right now this is almost useless. We should get the
        # request spect from the compute API, so that if we modify it there we
        # are able to detect it here...
        request_spec = {
            'instance_properties': {
                'system_metadata': {
                    'preemptible': False,
                }
            }
        }

        self.assertFalse(self.driver._is_preemptible_request(request_spec))

    def test_detect_preemptible_empty(self):
        # FIXME(aloga): Right now this is almost useless. We should get the
        # request spect from the compute API, so that if we modify it there we
        # are able to detect it here...
        request_spec = {}

        self.assertFalse(self.driver._is_preemptible_request(request_spec))

    def test_detect_overcommit_ram(self):
        obj = fakes.FakeHostState("host", "node",
                                  {"free_ram_mb": -1000,
                                   "total_usable_ram_mb": 1000,
                                   "ram_allocation_ratio": 1.5})
        self.assertTrue(self.driver.detect_overcommit(obj))

    def test_detect_overcommit_cpu(self):
        obj = fakes.FakeHostState("host", "node",
                                  {"total_usable_ram_mb": 1000,
                                   "ram_allocation_ratio": 1,
                                   "vcpus_used": 201,
                                   "vcpus_total": 20,
                                   "cpu_allocation_ratio": 10})
        self.assertTrue(self.driver.detect_overcommit(obj))

    def test_detect_overcommit_disk(self):
        self.flags(disk_allocation_ratio=0.8)
        obj = fakes.FakeHostState("host", "node",
                                  {"total_usable_ram_mb": 1000,
                                   "ram_allocation_ratio": 1,
                                   "free_disk_mb": 10 * 1024,
                                   "total_usable_disk_gb": 100,
                                   })
        self.assertTrue(self.driver.detect_overcommit(obj))

    def test_detect_not_overcommit(self):
        obj = fakes.FakeHostState("host", "node",
                                  {"free_ram_mb": 0,
                                   "total_usable_ram_mb": 1024,
                                   "free_disk_mb": 100,
                                   "vcpus_used": 10,
                                   "vcpus_total": 10,
                                   "cpu_allocation_ratio": 1,
                                   "ram_allocation_ratio": 1.5})
        self.assertFalse(self.driver.detect_overcommit(obj))

    def test_terminate_preemptible_instances(self):
        ctxt = mock.Mock()
        ctxt.elevated.return_value = "elevated"
        instances = [{"uuid": 1}, {"uuid": 2}]
        calls_get = [mock.call("elevated", i["uuid"], want_objects=True)
                     for i in instances]
        calls_delete = [mock.call("elevated", i) for i in instances]

        with mock.patch.object(self.driver.compute_api,
                               "get") as mock_get:
            with mock.patch.object(self.driver.compute_api,
                                   "delete") as mock_delete:
                mock_get.side_effect = instances
                self.driver.terminate_preemptible_instances(ctxt, instances)
                self.assertEqual(calls_get, mock_get.call_args_list)
                self.assertEqual(calls_delete, mock_delete.call_args_list)

    @mock.patch('nova.objects.ServiceList.get_by_binary',
                return_value=fakes.SERVICES)
    @mock.patch('nova.objects.InstanceList.get_by_host')
    @mock.patch('nova.objects.ComputeNodeList.get_all',
                return_value=fakes.COMPUTE_NODES)
    @mock.patch('nova.db.instance_extra_get_by_instance_uuid',
                return_value={'numa_topology': None,
                              'pci_requests': None})
    def test_select_destinations(self, mock_get_extra, mock_get_all,
                                            mock_by_host, mock_get_by_binary):
        """select_destinations is basically a wrapper around _schedule().

        Similar to the _schedule tests, this just does a happy path test to
        ensure there is nothing glaringly wrong.
        """

        self.next_weight = 1.0

        selected_hosts = []
        selected_nodes = []

        def _fake_weigh_objects(_self, functions, hosts, options):
            self.next_weight += 2.0
            host_state = hosts[0]
            selected_hosts.append(host_state.host)
            selected_nodes.append(host_state.nodename)
            return [weights.WeighedHost(host_state, self.next_weight)]

        self.stubs.Set(self.driver.host_manager, 'get_filtered_hosts',
            nova_test_filter_scheduler.fake_get_filtered_hosts)
        self.stubs.Set(weights.HostWeightHandler,
            'get_weighed_objects', _fake_weigh_objects)

        request_spec = {'instance_type': {'memory_mb': 512, 'root_gb': 512,
                                          'ephemeral_gb': 0,
                                          'vcpus': 1},
                        'instance_properties': {'project_id': 1,
                                                'root_gb': 512,
                                                'memory_mb': 512,
                                                'ephemeral_gb': 0,
                                                'vcpus': 1,
                                                'os_type': 'Linux',
                                                'uuid': 'fake-uuid'},
                        'num_instances': 1}
        self.mox.ReplayAll()
        dests = self.driver.select_destinations(self.context, request_spec, {})
        (host, node) = (dests[0]['host'], dests[0]['nodename'])
        self.assertEqual(host, selected_hosts[0])
        self.assertEqual(node, selected_nodes[0])

    @mock.patch('nova.objects.ServiceList.get_by_binary',
                return_value=fakes.SERVICES)
    @mock.patch('nova.objects.InstanceList.get_by_host')
    @mock.patch('nova.objects.ComputeNodeList.get_all',
                return_value=fakes.COMPUTE_NODES)
    @mock.patch('nova.db.instance_extra_get_by_instance_uuid',
                return_value={'numa_topology': None,
                              'pci_requests': None})
    def test_select_destinations_premptible(self, mock_get_extra, mock_get_all,
                                            mock_by_host, mock_get_by_binary):
        """select_destinations is basically a wrapper around _schedule().

        Similar to the _schedule tests, this just does a happy path test to
        ensure there is nothing glaringly wrong.
        """

        self.next_weight = 1.0

        selected_hosts = []
        selected_nodes = []

        def _fake_weigh_objects(_self, functions, hosts, options):
            self.next_weight += 2.0
            host_state = hosts[0]
            selected_hosts.append(host_state.host)
            selected_nodes.append(host_state.nodename)
            return [weights.WeighedHost(host_state, self.next_weight)]

        self.stubs.Set(self.driver.host_manager, 'get_filtered_hosts',
            nova_test_filter_scheduler.fake_get_filtered_hosts)
        self.stubs.Set(weights.HostWeightHandler,
            'get_weighed_objects', _fake_weigh_objects)

        request_spec = {'instance_type': {'memory_mb': 512, 'root_gb': 512,
                                          'ephemeral_gb': 0,
                                          'vcpus': 1},
                        'instance_properties': {'project_id': 1,
                                                'root_gb': 512,
                                                'memory_mb': 512,
                                                'ephemeral_gb': 0,
                                                'vcpus': 1,
                                                'os_type': 'Linux',
                                                'uuid': 'fake-uuid',
                                                'system_metadata': {
                                                    'preemptible': True
                                                }},
                        'num_instances': 1}
        self.mox.ReplayAll()
        dests = self.driver.select_destinations(self.context, request_spec, {})
        (host, node) = (dests[0]['host'], dests[0]['nodename'])
        self.assertEqual(host, selected_hosts[0])
        self.assertEqual(node, selected_nodes[0])

    @mock.patch('nova.scheduler.weights.HostWeightHandler.get_weighed_objects')
    @mock.patch('opie.scheduler.host_manager.HostManager.get_filtered_hosts',
                side_effect=nova_test_filter_scheduler.fake_get_filtered_hosts)
    @mock.patch('nova.objects.ServiceList.get_by_binary',
                return_value=fakes.SERVICES)
    @mock.patch('nova.objects.InstanceList.get_by_host')
    @mock.patch('nova.objects.ComputeNodeList.get_all',
                return_value=fakes.COMPUTE_NODES)
    @mock.patch('nova.db.instance_extra_get_by_instance_uuid',
                return_value={'numa_topology': None,
                              'pci_requests': None})
    def test_schedule_happy_day(self, mock_get_extra, mock_get_all,
                                mock_by_host, mock_get_by_binary,
                                mock_get_filtered_hosts,
                                mock_get_weighed_objects):
        """Make sure there's nothing glaringly wrong with _schedule()
        by doing a happy day pass through. We ensure that we are getting and
        using the correct states (i.e. partial or not) with regards the
        request being preemptible or not.
        """

        self.next_weight = 1.0

        def _fake_weigh_objects(functions, hosts, options):
            self.next_weight += 2.0
            host_state = hosts[0]
            return [weights.WeighedHost(host_state, self.next_weight)]

        mock_get_weighed_objects.side_effect = _fake_weigh_objects

        request_spec = {'num_instances': 10,
                        'instance_type': {'memory_mb': 512, 'root_gb': 512,
                                          'ephemeral_gb': 0,
                                          'vcpus': 1},
                        'instance_properties': {'project_id': 1,
                                                'root_gb': 512,
                                                'memory_mb': 512,
                                                'ephemeral_gb': 0,
                                                'vcpus': 1,
                                                'os_type': 'Linux',
                                                'uuid': 'fake-uuid'}}
        partial_states = list(self.driver._get_all_host_states(self.context,
                                                               partial=True))
        all_states = list(self.driver._get_all_host_states(self.context,
                                                           partial=False))
        weighed_hosts = self.driver._schedule(self.context, request_spec, {})

        # the HostState and HostStatePartial are the same objects
        mock_get_filtered_hosts.assert_called_with(partial_states,
                                                   mock.ANY,
                                                   index=mock.ANY)
        mock_get_weighed_objects.assert_called_with(mock.ANY,
                                                    all_states,
                                                    mock.ANY)

        self.assertEqual(len(weighed_hosts), 10)
        for weighed_host in weighed_hosts:
            self.assertIsNotNone(weighed_host.obj)

    @mock.patch('nova.scheduler.weights.HostWeightHandler.get_weighed_objects')
    @mock.patch('opie.scheduler.host_manager.HostManager.get_filtered_hosts',
                side_effect=nova_test_filter_scheduler.fake_get_filtered_hosts)
    @mock.patch('nova.objects.ServiceList.get_by_binary',
                return_value=fakes.SERVICES)
    @mock.patch('nova.objects.InstanceList.get_by_host')
    @mock.patch('nova.objects.ComputeNodeList.get_all',
                return_value=fakes.COMPUTE_NODES)
    @mock.patch('nova.db.instance_extra_get_by_instance_uuid',
                return_value={'numa_topology': None,
                              'pci_requests': None})
    def test_schedule_happy_day_preemptible(self, mock_get_extra, mock_get_all,
                                            mock_by_host, mock_get_by_binary,
                                            mock_get_filtered_hosts,
                                            mock_get_weighed_objects):
        """Make sure there's nothing glaringly wrong with _schedule()
        by doing a happy day pass through. We ensure that we are getting and
        using the correct states (i.e. partial or not) with regards the
        request being preemptible or not.
        """

        self.next_weight = 1.0

        def _fake_weigh_objects(functions, hosts, options):
            self.next_weight += 2.0
            host_state = hosts[0]
            return [weights.WeighedHost(host_state, self.next_weight)]

        mock_get_weighed_objects.side_effect = _fake_weigh_objects

        request_spec = {'num_instances': 10,
                        'instance_type': {'memory_mb': 512, 'root_gb': 512,
                                          'ephemeral_gb': 0,
                                          'vcpus': 1},
                        'instance_properties': {'project_id': 1,
                                                'root_gb': 512,
                                                'memory_mb': 512,
                                                'ephemeral_gb': 0,
                                                'vcpus': 1,
                                                'os_type': 'Linux',
                                                'uuid': 'fake-uuid',
                                                'system_metadata': {
                                                    'preemptible': True
                                                }}}
        all_states = list(self.driver._get_all_host_states(self.context,
                                                           partial=False))
        weighed_hosts = self.driver._schedule(self.context, request_spec, {})

        # the HostState and HostStatePartial are the same objects
        mock_get_filtered_hosts.assert_called_with(all_states,
                                                   mock.ANY,
                                                   index=mock.ANY)
        mock_get_weighed_objects.assert_called_with(mock.ANY,
                                                    all_states,
                                                    mock.ANY)

        self.assertEqual(len(weighed_hosts), 10)
        for weighed_host in weighed_hosts:
            self.assertIsNotNone(weighed_host.obj)

    @mock.patch('opie.scheduler.filter_scheduler.FilterScheduler._schedule')
    def test_select_destinations_kill_preemptible_empty(self, mock_schedule):
        host = fakes.FakeHostState("host", "node",
                                   {"free_ram_mb": -1000,
                                    "total_usable_ram_mb": 1000,
                                    "ram_allocation_ratio": 1.5})
        mock_schedule.return_value = [weights.WeighedHost(host, 1)]
        request_spec = {'num_instances': 1,
                        'instance_type': {'memory_mb': 512, 'root_gb': 512,
                                          'ephemeral_gb': 0,
                                          'vcpus': 1},
                        'instance_properties': {'project_id': 1,
                                                'root_gb': 512,
                                                'memory_mb': 512,
                                                'ephemeral_gb': 0,
                                                'vcpus': 1,
                                                'os_type': 'Linux',
                                                'uuid': 'fake-uuid',
                                                'system_metadata': {
                                                    'preemptible': False
                                                }}}
        self.assertRaises(exception.NoValidHost,
                          self.driver.select_destinations,
                          self.context,
                          request_spec,
                          {})

    @mock.patch('opie.scheduler.filter_scheduler.FilterScheduler.'
                'terminate_preemptible_instances')
    @mock.patch('opie.scheduler.filter_scheduler.FilterScheduler._schedule')
    def test_select_destinations_kill_preemptible(self, mock_schedule,
                                                  mock_terminate):
        host = fakes.FakeHostState("host", "node",
                                   {"free_ram_mb": -1000,
                                    "total_usable_ram_mb": 1000,
                                    "ram_allocation_ratio": 1.5})
        instances = {
            'uuid-preemptible': fake_instance.fake_instance_obj(
                "fake context", root_gb=1, ephemeral_gb=1, memory_mb=3,
                vcpus=4, project_id='12345', vm_state=vm_states.ACTIVE,
                task_state=task_states.RESIZE_PREP, os_type='Linux',
                uuid='uuid-preemptible'),
            'uuid-normal': fake_instance.fake_instance_obj(
                "fake context", root_gb=1, ephemeral_gb=1, memory_mb=3,
                vcpus=4, project_id='12345', vm_state=vm_states.ACTIVE,
                task_state=task_states.RESIZE_PREP, os_type='Linux',
                uuid='uuid-preemptible')
        }
        instances['uuid-normal'].system_metadata = {"preemptible": False}
        instances['uuid-preemptible'].system_metadata = {"preemptible": True}
        host.instances = instances

        mock_schedule.return_value = [weights.WeighedHost(host, 1)]
        mock_terminate.return_value = None

        request_spec = {'num_instances': 1,
                        'instance_type': {'memory_mb': 512, 'root_gb': 512,
                                          'ephemeral_gb': 0,
                                          'vcpus': 1},
                        'instance_properties': {'project_id': 1,
                                                'root_gb': 512,
                                                'memory_mb': 512,
                                                'ephemeral_gb': 0,
                                                'vcpus': 1,
                                                'os_type': 'Linux',
                                                'uuid': 'fake-uuid',
                                                'system_metadata': {
                                                    'preemptible': False
                                                }}}

        dests = self.driver.select_destinations(self.context, request_spec, {})
        self.assertEqual(host.host, dests[0]["host"])
        self.assertEqual(host.nodename, dests[0]["nodename"])
