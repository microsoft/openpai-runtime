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

import backoff
from git import Repo, GitCommandError

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
from plugins.plugin_utils import plugin_init, PluginHelper  #pylint: disable=wrong-import-position

LOGGER = logging.getLogger(__name__)

# backoff retry, max wait time set to 5 mins
@backoff.on_exception(backoff.expo, GitCommandError, max_tries=10, max_value=300)
def main():
    LOGGER.info("Preparing git runtime plugin")
    [plugin_config, pre_script, _] = plugin_init()
    plugin_helper = PluginHelper(plugin_config)

    repo_local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../code")
    parameters = plugin_config.get("parameters")
    if not parameters or "repo" not in parameters:
        LOGGER.error("Can not find repo in runtime plugin")
        sys.exit(1)
    if "options" in parameters:
        Repo.clone_from(parameters["repo"], repo_local_path, multi_options=parameters["options"])
    else:
        Repo.clone_from(parameters["repo"], repo_local_path)
    if "clone_dir" in parameters:
        plugin_helper.inject_commands(
            ["mkdir -p {}".format(parameters["clone_dir"]),
             "mv -f {}/* {}".format(repo_local_path, parameters["clone_dir"])], pre_script)


if __name__ == "__main__":
    main()
