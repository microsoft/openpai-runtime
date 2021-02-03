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

import logging
import os
import sys
import requests

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
from plugins.plugin_utils import plugin_init, PluginHelper, try_to_install_by_cache  #pylint: disable=wrong-import-position
#pylint: disable=wrong-import-position
from common.exceptions import UnknownError

LOGGER = logging.getLogger(__name__)


def get_user_public_keys(application_token, username):
    """
    get user public keys from rest-server

    Format of API `REST_SERVER_URI/api/v2/users/<username>` response:
    {
        "xxx": "xxx",
        "extensions": {
            "sshKeys": [
                {
                    "title": "title-of-the-public-key",
                    "value": "ssh-rsa xxxx"
                    "time": "xxx"
                }
            ]
        }
    }

    Returns:
    --------
    list
        a list of public keys
    """
    url = "{}/api/v2/users/{}".format(os.environ.get('REST_SERVER_URI'), username)
    headers={
        'Authorization': "Bearer {}".format(application_token),
    }

    response = requests.get(url, headers=headers, data={})
    response.raise_for_status()

    public_keys = [item["value"] for item in response.json()["extension"]["sshKeys"]]

    return public_keys


def main():
    LOGGER.info("Preparing ssh runtime plugin commands")
    [plugin_config, pre_script, _] = plugin_init()
    plugin_helper = PluginHelper(plugin_config)
    parameters = plugin_config.get("parameters")

    if not parameters:
        LOGGER.info("Ssh plugin parameters is empty, ignore this")
        return

    gang_allocation = os.environ.get("GANG_ALLOCATION", "true")
    if gang_allocation == "false":
        LOGGER.warning(
            "Job ssh is conflict with gang allocation, set job ssh to false")
        jobssh = "false"
    elif "jobssh" in parameters:
        jobssh = str(parameters["jobssh"]).lower()
    else:
        jobssh = "false"
    cmd_params = [jobssh]

    if "userssh" in parameters:
        # get user public keys from rest server
        application_token = plugin_config.get("application_token")
        username = os.environ.get("PAI_USER_NAME")
        public_keys = []
        if application_token:
            try:
                public_keys = get_user_public_keys(application_token, username)
            except Exception:  #pylint: disable=broad-except
                LOGGER.error("Failed to get user public keys", exc_info=True)
                raise UnknownError("Failed to get user public keys")

        if "value" in parameters["userssh"] and parameters["userssh"]["value"] != "":
            public_keys.append(parameters["userssh"]["value"])

        # append user public keys to cmd_params
        if "type" in parameters["userssh"] and public_keys:
            cmd_params.append(str(parameters["userssh"]["type"]))
            cmd_params.append("\'{}\'".format('\n'.join(public_keys)))

    # write call to real executable script
    command = []
    if len(cmd_params) == 1 and cmd_params[0] == "false":
        LOGGER.info("Skip sshd script since neither jobssh or userssh is set")
    else:
        command = [
            try_to_install_by_cache(
                "ssh",
                fallback_cmds=[
                    "apt-get update",
                    "apt-get install -y openssh-client openssh-server",
                ]), "{}/sshd.sh {}\n".format(
                    os.path.dirname(os.path.abspath(__file__)),
                    " ".join(cmd_params))
        ]

    # ssh barrier
    if jobssh == "true" and "sshbarrier" in parameters and str(
            parameters["sshbarrier"]).lower() == "true":
        if "sshbarrierTimeout" in parameters:
            barrier_params = str(parameters["sshbarrierTimeout"])
        else:
            barrier_params = ""
        command.append("{}/sshbarrier.sh {}\n".format(
            os.path.dirname(os.path.abspath(__file__)), barrier_params))

    plugin_helper.inject_commands(command, pre_script)
    LOGGER.info("Ssh runtime plugin perpared")


if __name__ == "__main__":
    main()
