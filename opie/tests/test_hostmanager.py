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

from opie.scheduler import host_manager

import mock
from nova.compute import task_states
from nova.compute import vm_states
import nova.objects
from nova.objects import base as obj_base
from nova.scheduler import host_manager as nova_host_manager
from nova import test as nova_test
from nova.tests import fixtures
from nova.tests.unit import fake_instance
from nova.tests.unit import matchers
from nova.tests.unit.scheduler import fakes
from nova.tests.unit.scheduler import test_host_manager \
        as nova_test_host_manager
from nova.tests import uuidsentinel as uuids


class OpieHostManagerTestCase(nova_test_host_manager.HostManagerTestCase):
    """Test case for opie HostManager class."""

    @mock.patch.object(host_manager.HostManager, '_init_instance_info')
    @mock.patch.object(host_manager.HostManager, '_init_aggregates')
    def setUp(self, mock_init_agg, mock_init_inst):
        super(OpieHostManagerTestCase, self).setUp()
        self.host_manager = host_manager.HostManager()

        self.fake_hosts = [nova_host_manager.HostState('fake_host%s' % x,
                'fake-node') for x in range(1, 5)]
        self.fake_hosts += [nova_host_manager.HostState('fake_multihost',
                'fake-node%s' % x) for x in range(1, 5)]

        self.useFixture(fixtures.SpawnIsSynchronousFixture())

    @mock.patch('opie.scheduler.host_manager.LOG')
    @mock.patch('nova.objects.ServiceList.get_by_binary')
    @mock.patch('nova.objects.ComputeNodeList.get_all')
    @mock.patch.object(nova.objects.InstanceList, 'get_by_host')
    def test_get_all_host_partial_states(self, mock_get_by_host, mock_get_all,
                                         mock_get_by_binary, mock_log):
        mock_get_by_host.return_value = nova.objects.InstanceList()
        mock_get_all.return_value = fakes.COMPUTE_NODES
        mock_get_by_binary.return_value = fakes.SERVICES
        context = 'fake_context'

        self.host_manager.get_all_host_partial_states(context)
        host_states_map = self.host_manager.host_state_map
        self.assertEqual(len(host_states_map), 4)

        calls = [
            mock.call(
                "No compute service record found for host %(host)s",
                {'host': 'fake'}
            )
        ]
        self.assertEqual(calls, mock_log.warning.call_args_list)

        # Check that .service is set properly
        for i in range(4):
            compute_node = fakes.COMPUTE_NODES[i]
            host = compute_node.host
            node = compute_node.hypervisor_hostname
            state_key = (host, node)
            self.assertEqual(host_states_map[state_key].service,
                    obj_base.obj_to_primitive(fakes.get_service_by_host(host)))
        self.assertEqual(host_states_map[('host1', 'node1')].free_ram_mb,
                         512)
        # 511GB
        self.assertEqual(host_states_map[('host1', 'node1')].free_disk_mb,
                         524288)
        self.assertEqual(host_states_map[('host2', 'node2')].free_ram_mb,
                         1024)
        # 1023GB
        self.assertEqual(host_states_map[('host2', 'node2')].free_disk_mb,
                         1048576)
        self.assertEqual(host_states_map[('host3', 'node3')].free_ram_mb,
                         3072)
        # 3071GB
        self.assertEqual(host_states_map[('host3', 'node3')].free_disk_mb,
                         3145728)
        self.assertThat(
                nova.objects.NUMATopology.obj_from_db_obj(
                        host_states_map[('host3', 'node3')].numa_topology
                    )._to_dict(),
                matchers.DictMatches(fakes.NUMA_TOPOLOGY._to_dict()))
        self.assertEqual(host_states_map[('host4', 'node4')].free_ram_mb,
                         8192)
        # 8191GB
        self.assertEqual(host_states_map[('host4', 'node4')].free_disk_mb,
                         8388608)

    @mock.patch('opie.scheduler.host_manager.LOG')
    @mock.patch('nova.objects.ServiceList.get_by_binary')
    @mock.patch('nova.objects.ComputeNodeList.get_all')
    @mock.patch('nova.objects.InstanceList.get_by_host')
    def test_get_all_host_states(self, mock_get_by_host, mock_get_all,
                                 mock_get_by_binary, mock_log):
        mock_get_by_host.return_value = nova.objects.InstanceList()
        mock_get_all.return_value = fakes.COMPUTE_NODES
        mock_get_by_binary.return_value = fakes.SERVICES
        context = 'fake_context'

        self.host_manager.get_all_host_states(context)
        host_states_map = self.host_manager.host_state_map
        self.assertEqual(len(host_states_map), 4)

        calls = [
#            mock.call(
#                "Host %(hostname)s has more disk space than database "
#                "expected (%(physical)s GB > %(database)s GB)",
#                {'physical': 3333, 'database': 3072, 'hostname': 'node3'}
#            ),
            mock.call(
                "No compute service record found for host %(host)s",
                {'host': 'fake'}
            )
        ]
        self.assertEqual(calls, mock_log.warning.call_args_list)

        # Check that .service is set properly
        for i in range(4):
            compute_node = fakes.COMPUTE_NODES[i]
            host = compute_node.host
            node = compute_node.hypervisor_hostname
            state_key = (host, node)
            self.assertEqual(host_states_map[state_key].service,
                    obj_base.obj_to_primitive(fakes.get_service_by_host(host)))

        self.assertEqual(host_states_map[('host1', 'node1')].free_ram_mb,
                         512)
        # 511GB
        self.assertEqual(host_states_map[('host1', 'node1')].free_disk_mb,
                         524288)
        self.assertEqual(host_states_map[('host2', 'node2')].free_ram_mb,
                         1024)
        # 1023GB
        self.assertEqual(host_states_map[('host2', 'node2')].free_disk_mb,
                         1048576)
        self.assertEqual(host_states_map[('host3', 'node3')].free_ram_mb,
                         3072)
        # 3071GB
        self.assertEqual(host_states_map[('host3', 'node3')].free_disk_mb,
                         3145728)
        self.assertThat(
                nova.objects.NUMATopology.obj_from_db_obj(
                        host_states_map[('host3', 'node3')].numa_topology
                    )._to_dict(),
                matchers.DictMatches(fakes.NUMA_TOPOLOGY._to_dict()))
        self.assertEqual(host_states_map[('host4', 'node4')].free_ram_mb,
                         8192)
        # 8191GB
        self.assertEqual(host_states_map[('host4', 'node4')].free_disk_mb,
                         8388608)


class OpieHostManagerChangedNodesTestCase(nova_test_host_manager.
                                            HostManagerChangedNodesTestCase):
    """Test case for opie HostManager class."""

    @mock.patch.object(host_manager.HostManager, '_init_instance_info')
    @mock.patch.object(host_manager.HostManager, '_init_aggregates')
    def setUp(self, mock_init_agg, mock_init_inst):
        super(OpieHostManagerChangedNodesTestCase, self).setUp()
        self.host_manager = host_manager.HostManager()
        self.fake_hosts = [
              nova_host_manager.HostState('host1', 'node1'),
              nova_host_manager.HostState('host2', 'node2'),
              nova_host_manager.HostState('host3', 'node3'),
              nova_host_manager.HostState('host4', 'node4')
            ]

    @mock.patch('nova.objects.ServiceList.get_by_binary')
    @mock.patch('nova.objects.ComputeNodeList.get_all')
    @mock.patch('nova.objects.InstanceList.get_by_host')
    def test_get_all_host_partial_states(self, mock_get_by_host, mock_get_all,
                                         mock_get_by_binary):
        mock_get_by_host.return_value = nova.objects.InstanceList()
        mock_get_all.return_value = fakes.COMPUTE_NODES
        mock_get_by_binary.return_value = fakes.SERVICES
        context = 'fake_context'

        self.host_manager.get_all_host_partial_states(context)
        host_states_map = self.host_manager.host_state_map
        self.assertEqual(len(host_states_map), 4)

    @mock.patch('nova.objects.ServiceList.get_by_binary')
    @mock.patch('nova.objects.ComputeNodeList.get_all')
    @mock.patch('nova.objects.InstanceList.get_by_host')
    def test_get_all_host_states_after_delete_one(self, mock_get_by_host,
                                                  mock_get_all,
                                                  mock_get_by_binary):
        getter = (lambda n: n.hypervisor_hostname
                  if 'hypervisor_hostname' in n else None)
        running_nodes = [n for n in fakes.COMPUTE_NODES
                         if getter(n) != 'node4']

        mock_get_by_host.return_value = nova.objects.InstanceList()
        mock_get_all.side_effect = [fakes.COMPUTE_NODES, running_nodes]
        mock_get_by_binary.side_effect = [fakes.SERVICES, fakes.SERVICES]
        context = 'fake_context'

        # first call: all nodes
        self.host_manager.get_all_host_partial_states(context)
        host_states_map = self.host_manager.host_state_map
        self.assertEqual(len(host_states_map), 4)

        # second call: just running nodes
        self.host_manager.get_all_host_partial_states(context)
        host_states_map = self.host_manager.host_state_map
        self.assertEqual(len(host_states_map), 3)

    @mock.patch('nova.objects.ServiceList.get_by_binary')
    @mock.patch('nova.objects.ComputeNodeList.get_all')
    @mock.patch('nova.objects.InstanceList.get_by_host')
    def test_get_all_host_partial_states_after_delete_all(self,
                                                          mock_get_by_host,
                                                          mock_get_all,
                                                          mock_get_by_binary):
        mock_get_by_host.return_value = nova.objects.InstanceList()
        mock_get_all.side_effect = [fakes.COMPUTE_NODES, []]
        mock_get_by_binary.side_effect = [fakes.SERVICES, fakes.SERVICES]
        context = 'fake_context'

        # first call: all nodes
        self.host_manager.get_all_host_partial_states(context)
        host_states_map = self.host_manager.host_state_map
        self.assertEqual(len(host_states_map), 4)

        # second call: no nodes
        self.host_manager.get_all_host_partial_states(context)
        host_states_map = self.host_manager.host_state_map
        self.assertEqual(len(host_states_map), 0)


class OpieHostStateTestCase(nova_test.NoDBTestCase):
    """Test case for Opie HostStatePartial class."""

    # update_from_compute_node() and consume_from_request() are tested
    # in HostManagerTestCase.test_get_all_host_states()

    @mock.patch('nova.utils.synchronized',
                side_effect=lambda a: lambda f: lambda *args: f(*args))
    @mock.patch('nova.virt.hardware.get_host_numa_usage_from_instance')
    @mock.patch('nova.objects.Instance')
    @mock.patch('nova.virt.hardware.numa_fit_instance_to_host')
    @mock.patch('nova.virt.hardware.host_topology_and_format_from_host')
    def test_stat_consumption_from_instance(self, host_topo_mock,
                                            numa_fit_mock,
                                            instance_init_mock,
                                            numa_usage_mock,
                                            sync_mock):
        fake_numa_topology = nova.objects.InstanceNUMATopology(
            cells=[nova.objects.InstanceNUMACell()])
        fake_host_numa_topology = mock.Mock()
        fake_instance = nova.objects.Instance(numa_topology=fake_numa_topology)
        host_topo_mock.return_value = (fake_host_numa_topology, True)
        numa_usage_mock.return_value = fake_host_numa_topology
        numa_fit_mock.return_value = fake_numa_topology
        instance_init_mock.return_value = fake_instance
        spec_obj = nova.objects.RequestSpec(
            instance_uuid=uuids.instance,
            flavor=nova.objects.Flavor(root_gb=0, ephemeral_gb=0, memory_mb=0,
                                  vcpus=0),
            numa_topology=fake_numa_topology,
            pci_requests=nova.objects.InstancePCIRequests(requests=[]))
        host = host_manager.HostStatePartial("fakehost", "fakenode")

        self.assertIsNone(host.updated)
        host.consume_from_request(spec_obj)
        numa_fit_mock.assert_called_once_with(fake_host_numa_topology,
                                              fake_numa_topology,
                                              limits=None, pci_requests=None,
                                              pci_stats=None)
        numa_usage_mock.assert_called_once_with(host, fake_instance)
        sync_mock.assert_called_once_with(("fakehost", "fakenode"))
        self.assertEqual(fake_host_numa_topology, host.numa_topology)
        self.assertIsNotNone(host.updated)

        second_numa_topology = nova.objects.InstanceNUMATopology(
            cells=[nova.objects.InstanceNUMACell()])
        spec_obj = nova.objects.RequestSpec(
            instance_uuid=uuids.instance,
            flavor=nova.objects.Flavor(root_gb=0, ephemeral_gb=0, memory_mb=0,
                                  vcpus=0),
            numa_topology=second_numa_topology,
            pci_requests=nova.objects.InstancePCIRequests(requests=[]))
        second_host_numa_topology = mock.Mock()
        numa_usage_mock.return_value = second_host_numa_topology
        numa_fit_mock.return_value = second_numa_topology

        host.consume_from_request(spec_obj)
        self.assertEqual(2, host.num_instances)
        self.assertEqual(2, host.num_io_ops)
        self.assertEqual(2, numa_usage_mock.call_count)
        self.assertEqual(((host, fake_instance),), numa_usage_mock.call_args)
        self.assertEqual(second_host_numa_topology, host.numa_topology)
        self.assertIsNotNone(host.updated)

    @mock.patch('nova.utils.synchronized',
                side_effect=lambda a: lambda f: lambda *args: f(*args))
    @mock.patch('nova.virt.hardware.get_host_numa_usage_from_instance')
    @mock.patch('nova.objects.Instance')
    @mock.patch('nova.virt.hardware.numa_fit_instance_to_host')
    @mock.patch('nova.virt.hardware.host_topology_and_format_from_host')
    def test_stat_unconsumption_from_instance(self, host_topo_mock,
                                            numa_fit_mock,
                                            instance_init_mock,
                                            numa_usage_mock,
                                            sync_mock):
        fake_numa_topology = nova.objects.InstanceNUMATopology(
            cells=[nova.objects.InstanceNUMACell()])
        fake_host_numa_topology = mock.Mock()
        fake_instance = nova.objects.Instance(numa_topology=fake_numa_topology)
        host_topo_mock.return_value = (fake_host_numa_topology, True)
        numa_usage_mock.return_value = fake_host_numa_topology
        numa_fit_mock.return_value = fake_numa_topology
        instance_init_mock.return_value = fake_instance
        spec_obj = nova.objects.RequestSpec(
            instance_uuid=uuids.instance,
            flavor=nova.objects.Flavor(root_gb=0, ephemeral_gb=0, memory_mb=0,
                                  vcpus=0),
            numa_topology=fake_numa_topology,
            pci_requests=nova.objects.InstancePCIRequests(requests=[]))
        host = host_manager.HostStatePartial("fakehost", "fakenode")

        self.assertIsNone(host.updated)
        host.consume_from_request(spec_obj)
        self.assertIsNotNone(host.updated)
        self.assertEqual(1, host.num_instances)

        second_numa_topology = nova.objects.InstanceNUMATopology(
            cells=[nova.objects.InstanceNUMACell()])
        spec_obj = nova.objects.RequestSpec(
            instance_uuid=uuids.instance,
            flavor=nova.objects.Flavor(root_gb=1, ephemeral_gb=1, memory_mb=3,
                                  vcpus=4),
            numa_topology=second_numa_topology,
            pci_requests=nova.objects.InstancePCIRequests(requests=[]))
        second_host_numa_topology = mock.Mock()
        numa_usage_mock.return_value = second_host_numa_topology
        numa_fit_mock.return_value = second_numa_topology

        host.consume_from_request(spec_obj)
        self.assertEqual(2, host.num_instances)
        self.assertEqual(2, host.num_io_ops)

        host._unconsume_from_request(spec_obj)
        self.assertEqual(1, host.num_instances)
        self.assertEqual(2, host.num_io_ops)
        self.assertEqual(0, host.free_disk_mb)
        self.assertEqual(0, host.free_ram_mb)
        self.assertEqual(0, host.vcpus_used)
        self.assertIsNotNone(host.updated)

    def test_stat_unconsumption_from_instance_list(self):

        instances = {}
        inst = fake_instance.fake_instance_obj(
            "fake context", root_gb=0, ephemeral_gb=0, memory_mb=0, vcpus=0,
            project_id='12345', vm_state=vm_states.BUILDING,
            task_state=task_states.SCHEDULING, os_type='Linux',
            uuid='fake-uuid-normal'
        )
        # Set this attribute here instead of doing a mock with the DB object
        inst.system_metadata = {}
        instances[inst.uuid] = inst

        inst = fake_instance.fake_instance_obj(
            "fake context", root_gb=1, ephemeral_gb=1, memory_mb=3, vcpus=4,
            project_id='12345', vm_state=vm_states.ACTIVE,
            task_state=task_states.RESIZE_PREP, os_type='Linux',
            uuid='fake-uuid-preemptible'
        )
        inst.system_metadata = {"preemptible": True}
        instances[inst.uuid] = inst

        host = host_manager.HostStatePartial("fakehost", "fakenode")

        self.assertIsNone(host.updated)
        # Instances consume resources in the scheduling loop
        for instance in instances.values():
            host.consume_from_request(instance)

        host.instances = instances
        self.assertEqual(1, host.num_instances)
        self.assertEqual(0, host.num_io_ops)
        self.assertEqual(0, host.free_disk_mb)
        self.assertEqual(0, host.free_ram_mb)
        self.assertEqual(0, host.vcpus_used)
        self.assertIsNotNone(host.updated)
        self.assertIn('fake-uuid-normal', host.normal_instances)
        self.assertIn('fake-uuid-normal', host.instances)
        self.assertIn('fake-uuid-preemptible', host.preemptible_instances)
        self.assertIn('fake-uuid-preemptible', host.instances)

        # Setting the instances a second time should leave the resources as
        # they were
        host.instances = instances
        self.assertEqual(1, host.num_instances)
