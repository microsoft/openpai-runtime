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

import os
import sys

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
from plugins.plugin_utils import plugin_init, PluginHelper  #pylint: disable=wrong-import-position


def main():
    [plugin_config, pre_script, post_script] = plugin_init()

    plugin_helper = PluginHelper(plugin_config)
    parameters = plugin_config.get("parameters")
    if parameters:
        if "callbacks" in parameters:
            assert "preCommands" not in parameters
            assert "postCommands" not in parameters
            pre_commands = []
            post_commands = []
            for callback in parameters['callbacks']:
                if callback['event'] == 'taskStarts':
                    pre_commands.extend(callback['commands'])
                elif callback['event'] == 'taskSucceeds':
                    post_commands.extend(callback['commands'])
            if len(pre_commands) > 0:
                plugin_helper.inject_commands(pre_commands, pre_script)
            if len(post_commands) > 0:
                plugin_helper.inject_commands(post_commands, post_script)
        else:
            if "preCommands" in parameters:
                plugin_helper.inject_commands(parameters["preCommands"],
                                              pre_script)
            if "postCommands" in parameters:
                plugin_helper.inject_commands(parameters["postCommands"],
                                              post_script)


if __name__ == "__main__":
    main()
