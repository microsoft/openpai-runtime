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
from pathlib import Path
import sys

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
from plugins.plugin_utils import plugin_init, PluginHelper, try_to_install_by_cache  #pylint: disable=wrong-import-position

LOGGER = logging.getLogger(__name__)


def get_user_public_keys(user_extension):
    """
    get user public keys from user extension

    Format of user extension:
    {
        "sshKeys": [
            {
                "title": "title-of-the-public-key",
                "value": "ssh-rsa xxxx"
                "time": "xxx"
            }
        ]
    }

    Returns:
    --------
    list
        a list of public keys
    """
    public_keys = [item["value"] for item in user_extension["sshKeys"]]

    return public_keys


def prepare_job_ssh_key_pair(user_extension):
    """
    prepare job ssh key pair from user extension

    Format of user extension:
    {
        "jobSSH":
            {
                "key": "-----BEGIN RSA PRIVATE KEY----- xxxx",
                "pubKey": "ssh-rsa xxxx"
            }
    }
    """
    if "jobSSH" in user_extension:
        secret_root = './ssh-secret'
        Path(secret_root).mkdir(exist_ok=True)
        with open("./ssh-secret/ssh-publickey", "w") as publickey:
            publickey.write(user_extension["jobSSH"]["pubKey"])
        with open("./ssh-secret/ssh-privatekey", "w") as privatekey:
            privatekey.write(user_extension["jobSSH"]["key"])


def main():
    LOGGER.info("Preparing ssh runtime plugin commands")
    [plugin_config, pre_script, _] = plugin_init()
    plugin_helper = PluginHelper(plugin_config)
    parameters = plugin_config.get("parameters")
    user_extension = plugin_config.get("user_extension")

    prepare_job_ssh_key_pair(user_extension)

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
        # get user public keys from user extension secret
        public_keys = []
        if user_extension and "sshKeys" in user_extension:
            public_keys = get_user_public_keys(user_extension)

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
