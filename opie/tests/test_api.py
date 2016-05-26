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

from opie.api.openstack.compute import preemptible_instances as preempt_api
from opie.tests import base

import webob.exc


class TestOpieAPI(base.TestCase):
    def setUp(self):
        super(TestOpieAPI, self).setUp()
        self.controller = preempt_api.SpotController()

        self.req = None

    def test_index(self):
        self.assertRaises(webob.exc.HTTPNotImplemented,
                          self.controller.index,
                          self.req)
