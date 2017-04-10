# Copyright 2015 Spanish National Research Council (CSIC)
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

"""Preemptible instances extension."""

from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova.policies import servers as server_policies

from opie.api.openstack.compute.schemas import preemptible_instances as \
                                                            schema_preemptible
import webob.exc

ALIAS = "os-preemptible-instances"
ATTRIBUTE_NAME = "preemptible"


class SpotController(object):
    def index(self, req):
        raise webob.exc.HTTPNotImplemented()


class Controller(wsgi.Controller):
    def _add_preemptible_info(self, req, servers):
        for server in servers:
            db_server = req.get_db_instance(server['id'])
            if db_server.system_metadata.get('preemptible'):
                is_preemptible = True
            else:
                is_preemptible = False
            server[ATTRIBUTE_NAME] = is_preemptible

    def _show(self, req, resp_obj):
        if 'server' in resp_obj.obj:
            server = resp_obj.obj['server']
            self._add_preemptible_info(req, [server])

    @wsgi.extends
    def show(self, req, resp_obj, id):
        context = req.environ['nova.context']
        context.can(server_policies.SERVERS % 'show')
        self._show(req, resp_obj)

    @wsgi.extends
    def detail(self, req, resp_obj):
        context = req.environ['nova.context']
        context.can(server_policies.SERVERS % 'detail')
        if 'servers' in resp_obj.obj:
            servers = resp_obj.obj['servers']
            self._add_preemptible_info(req, servers)


class Preemptible(extensions.V21APIExtensionBase):
    """Preemptible Instances Support."""

    name = "PreemptibleInstances"
    alias = ALIAS
    version = 1

    def get_resources(self):
        resources = [
            extensions.ResourceExtension(ALIAS, SpotController())
        ]

        return resources

    def get_controller_extensions(self):
        controller = Controller()
        extension = extensions.ControllerExtension(self, 'servers', controller)
        return [extension]

    # NOTE(gmann): This function is not supposed to use 'body_deprecated_param'
    # parameter as this is placed to handle scheduler_hint extension for V2.1.
    def server_create(self, server_dict, create_kwargs, body_deprecated_param):
        create_kwargs['preemptible'] = server_dict.get(ATTRIBUTE_NAME)

    def get_server_create_schema(self, version):
        return schema_preemptible.server_create
