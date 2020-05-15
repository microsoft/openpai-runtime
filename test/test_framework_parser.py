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

import json
from io import StringIO
import os
import sys
import unittest

# pylint: disable=wrong-import-position
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../src"))
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../src/init.d"))
from framework_parser import generate_runtime_env
from common.utils import init_logger
# pylint: enable=wrong-import-position

PACKAGE_DIRECTORY_COM = os.path.dirname(os.path.abspath(__file__))
init_logger()


class TestParser(unittest.TestCase):
    def setUp(self):
        try:
            os.chdir(PACKAGE_DIRECTORY_COM)
        except Exception:  #pylint: disable=broad-except
            pass

    def test_generate_runtime_env(self):
        os.environ["FC_TASK_INDEX"] = "0"
        os.environ["FC_TASKROLE_NAME"] = "taskrole"
        test_files = [
            "framework.json",
            "framework_multi_instances.json",
        ]
        expect_lines = [
            [
                "export PAI_CONTAINER_HOST_PORT_LIST='tcp:23652,22505;ssh:31055;http:25895;'",
                "export PAI_CONTAINER_HOST_tcp_PORT_LIST='23652,22505'",
                "export PAI_CONTAINER_HOST_ssh_PORT_LIST='31055'",
                "export PAI_PORT_LIST_taskrole_0_tcp='23652,22505'",
                "export PAI_taskrole1_0_udp_PORT='37633,27232'",
                "export PAI_taskrole1_0_mpi_PORT='27760'",
                "export PAI_CONTAINER_HOST_PORT='25895'",
                "export PAI_CONTAINER_SSH_PORT='31055'"
            ],
            [
                "export PAI_PORT_LIST_taskrole_0_tpc='37594,23725,27746,33765,36824,31446,25354,22922,25183,23174'",
                ("export PAI_CONTAINER_HOST_PORT_LIST='tpc:37594,23725,27746,33765,36824,31446,25354,22922,25183,23174;"
                 "udp:32700,37444,26550,35841,33489,28822,25998,34164,21585,26715;ssh:32859;http:37991;'"
                 ),
                "export PAI_taskrole_1_tpc_PORT='27769,31957,23668,28129,38436,38270,28092,33059,38318,29327'",
                "export PAI_PORT_LIST_taskrole_0_http='37991'",
                "export PAI_taskrole_0_udp_PORT='32700,37444,26550,35841,33489,28822,25998,34164,21585,26715'",
                "export PAI_CONTAINER_SSH_PORT='32859'"
            ]
        ]
        for index, file_name in enumerate(test_files):
            with open(file_name, "r") as f:
                framework = json.load(f)

            sys.stdout = temp_stdout = StringIO()

            generate_runtime_env(framework)
            runtime_env = temp_stdout.getvalue().splitlines()

            sys.stdout = sys.__stdout__

            for expect in expect_lines[index]:
                self.assertIn(expect, runtime_env)

        del os.environ["FC_TASK_INDEX"]
        del os.environ["FC_TASKROLE_NAME"]


if __name__ == '__main__':
    unittest.main()
