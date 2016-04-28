# Copyright 2015 Spanish National Research Council - CSIC
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

from nova.api.openstack.compute import servers
from nova.api.openstack import extensions
from nova.api.openstack import wsgi


authorize = extensions.extension_authorizer('compute', 'preemptible-instances')
soft_authorize = extensions.soft_extension_authorizer('compute', 'preemptible-instances')


class SpotController(object):
    def index(self, req):
        return {"preemptible": []}


class Controller(servers.Controller):
    def _add_preemptible_info(self, req, servers):
        for server in servers:
            db_server = req.get_db_instance(server['id'])
            server['preemptible'] = db_server.system_metadata.get('preemptible', False)

    def _show(self, req, resp_obj):
        if 'server' in resp_obj.obj:
            server = resp_obj.obj['server']
            self._add_preemptible_info(req, [server])

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['nova.context']
        if soft_authorize(context):
            self._show(req, resp_obj)

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['nova.context']
        if 'servers' in resp_obj.obj and soft_authorize(context):
            servers = resp_obj.obj['servers']
            self._add_preemptible_info(req, servers)



class Preemptible(extensions.ExtensionDescriptor):
    """PreemptibleInstances Support."""

    name = "PreemptibleInstances"
    alias = "os-spot-instances"
    namespace = "http://docs.openstack.org/compute/ext/preemptible/api/v1.0"
    updated = "2015-06-10T00:00:00Z"

    def get_resources(self):
        resources = []

        res = extensions.ResourceExtension(
                'os-preemptible-instances',
                SpotController())
        resources.append(res)
        return resources

    def get_controller_extensions(self):
        controller = Controller(self.ext_mgr)
        extension = extensions.ControllerExtension(self, 'servers', controller)
        return [extension]
