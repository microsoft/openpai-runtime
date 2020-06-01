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
        test_file = "framework.json"
        expect_lines = [
            "export PAI_PORT_LIST_taskrole_0_tcp='29877,22353,29076'",
            "export PAI_CONTAINER_HOST_PORT_LIST='tcp:29877,22353,29076;udp:31903,33486,35953;ssh:39080;http:30643;'",
            "export PAI_taskrole1_0_mpi_PORT='20966,21891'",
            "export PAI_CONTAINER_HOST_http_PORT_LIST='30643'",
            "export PAI_PORT_LIST_taskrole_0_udp='31903,33486,35953'",
            "export PAI_CONTAINER_SSH_PORT='39080'"
        ]
        with open(test_file, "r") as f:
            framework = json.load(f)

        sys.stdout = temp_stdout = StringIO()

        generate_runtime_env(framework)
        runtime_env = temp_stdout.getvalue().splitlines()

        sys.stdout = sys.__stdout__

        for expect in expect_lines:
            self.assertIn(expect, runtime_env)

        del os.environ["FC_TASK_INDEX"]
        del os.environ["FC_TASKROLE_NAME"]


if __name__ == '__main__':
    unittest.main()
