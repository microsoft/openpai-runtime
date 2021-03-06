#!/usr/bin/python

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

# The error exit code range for this program is [10, 20)

import argparse
import logging
import os
import re
import sys
import socket

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.utils import init_logger  #pylint: disable=wrong-import-position

LOGGER = logging.getLogger(__name__)


def check_port(portno):
    """Check whether the port is in use.

    Exit with code 10 if the port is already in use.

    Args:
        portno: Port number to check.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ret = sock.connect_ex(('localhost', portno))
    sock.close()
    if ret == 0:
        print("Port {} has conflict.".format(portno))
        sys.exit(10)


def check_port_list_env(port_list_env):
    ports = {}
    for each in re.split(":|;|,", port_list_env):
        if each.isdigit():
            if each in ports:
                LOGGER.error("Port %s has conflict.", each)
                sys.exit(10)
            ports[each] = True
            check_port(int(each))


def main():
    """Main function.

    Check whether there's conflict in scheduled ports.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_env", help="runtime_env generated by parser")
    args = parser.parse_args()

    LOGGER.info("runtime env from %s", args.runtime_env)
    with open(args.runtime_env) as f:
        content = f.read()
        matches = re.search(r"PAI_CONTAINER_HOST_PORT_LIST='(.*)'", content)
        if matches and matches.group(1):
            check_port_list_env(matches.group(1))


if __name__ == "__main__":
    init_logger()
    main()
