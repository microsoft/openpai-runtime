#!/usr/bin/env python
# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
import base64
import hashlib
import logging
import gzip
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.utils import init_logger  #pylint: disable=wrong-import-position

LOGGER = logging.getLogger(__name__)

# The port range is [20000, 40000) by default.
# TODO: Change to using config file or ENV in future
PORT_RANGE = {"begin_offset": 20000, "count": 20000}


def export(k, v):
    print("export {}='{}'".format(k, v))


def decompress_field(field):
    if not field:
        return None
    data = gzip.decompress(base64.b64decode(field))
    obj = json.loads(data)
    return obj


def generate_port_num(pod_uid, port_name, port_index):
    raw_str = pod_uid + port_name + str(port_index)
    return PORT_RANGE["begin_offset"] + int(
        hashlib.md5(raw_str.encode("utf8")).hexdigest(), 16) % PORT_RANGE["count"]


def generate_runtime_env(framework):  #pylint: disable=too-many-locals
    """Generate runtime env variables for tasks.

    # current
    PAI_HOST_IP_$taskRole_$taskIndex
    PAI_PORT_LIST_$taskRole_$taskIndex_$portType

    # backward compatibility
    PAI_CURRENT_CONTAINER_IP
    PAI_CURRENT_CONTAINER_PORT
    PAI_CONTAINER_HOST_IP
    PAI_CONTAINER_HOST_PORT
    PAI_CONTAINER_SSH_PORT
    PAI_CONTAINER_HOST_PORT_LIST
    PAI_CONTAINER_HOST_$portType_PORT_LIST
    PAI_TASK_ROLE_$taskRole_HOST_LIST
    PAI_$taskRole_$taskIndex_$portType_PORT

    # task role instances
    PAI_TASK_ROLE_INSTANCES

    Args:
        framework: Framework object generated by frameworkbarrier.
    """
    current_task_index = os.environ.get("FC_TASK_INDEX")
    current_taskrole_name = os.environ.get("FC_TASKROLE_NAME")

    taskroles = {}
    for taskrole in framework["spec"]["taskRoles"]:
        taskroles[taskrole["name"]] = {
            "number": taskrole["taskNumber"],
        }
    LOGGER.info("task roles: %s", taskroles)

    # decompress taskRoleStatuses for the large framework
    taskrole_instances = []
    if not framework["status"]["attemptStatus"]["taskRoleStatuses"]:
        framework["status"]["attemptStatus"][
            "taskRoleStatuses"] = decompress_field(
                framework["status"]["attemptStatus"]
                ["taskRoleStatusesCompressed"])

    for taskrole in framework["status"]["attemptStatus"]["taskRoleStatuses"]:
        name = taskrole["name"]
        ports = taskroles[name]["ports"]

        host_list = []
        for task in taskrole["taskStatuses"]:
            index = task["index"]
            current_ip = task["attemptStatus"]["podHostIP"]
            pod_uuid = task["attempStatus"]["podUID"]

            taskrole_instances.append("{}:{}".format(name, index))

            # export ip/port for task role, current ip maybe None for non-gang-allocation
            if current_ip:
                export("PAI_HOST_IP_{}_{}".format(name, index), current_ip)
                host_list.append("{}:{}".format(
                    current_ip,
                    generate_port_num(pod_uuid, "http", 0)))

            for port in ports.keys():
                count = int(ports[port]["count"])
                current_port_str = ",".join(
                    generate_port_num(pod_uuid, port, x) for x in range(count))
                export("PAI_PORT_LIST_{}_{}_{}".format(name, index, port),
                       current_port_str)
                export("PAI_{}_{}_{}_PORT".format(name, index, port),
                       current_port_str)

            # export ip/port for current container
            if (current_taskrole_name == name
                    and current_task_index == str(index)):
                export("PAI_CURRENT_CONTAINER_IP", current_ip)
                export("PAI_CURRENT_CONTAINER_PORT", generate_port_num(pod_uuid, "http", 0))
                export("PAI_CONTAINER_HOST_IP", current_ip)
                export("PAI_CONTAINER_HOST_PORT", generate_port_num(pod_uuid, "http", 0))
                export("PAI_CONTAINER_SSH_PORT", generate_port_num(pod_uuid, "ssh", 0))
                port_str = ""
                for port in ports.keys():
                    count = int(ports[port]["count"])
                    current_port_str = ",".join(
                        generate_port_num(pod_uuid, port, x) for x in range(count) for x in range(count))
                    export("PAI_CONTAINER_HOST_{}_PORT_LIST".format(port),
                           current_port_str)
                    port_str += "{}:{};".format(port, current_port_str)
                export("PAI_CONTAINER_HOST_PORT_LIST", port_str)

        export("PAI_TASK_ROLE_{}_HOST_LIST".format(name), ",".join(host_list))
    export("PAI_TASK_ROLE_INSTANCES", ",".join(taskrole_instances))


def generate_jobconfig(framework):
    """Generate jobconfig from framework.

    Args:
        framework: Framework object generated by frameworkbarrier.
    """
    print(framework["metadata"]["annotations"]["config"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("function",
                        choices=["genenv", "genconf"],
                        help="parse function, could be genenv|genconf")
    parser.add_argument("framework_json",
                        help="framework.json generated by frameworkbarrier")
    args = parser.parse_args()

    LOGGER.info("loading json from %s", args.framework_json)
    with open(args.framework_json) as f:
        framework = json.load(f)

    if args.function == "genenv":
        generate_runtime_env(framework)
    elif args.function == 'genconf':
        generate_jobconfig(framework)


if __name__ == "__main__":
    init_logger()
    main()
