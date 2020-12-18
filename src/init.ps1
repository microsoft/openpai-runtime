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

$PAI_WORK_DIR = "C:\Program Files\pai"
$PAI_CONFIG_DIR = "C:\Program Files\pai-config"
$PAI_INIT_DIR = "${PAI_WORK_DIR}\init.d"
$PAI_RUNTIME_DIR = "${PAI_WORK_DIR}\runtime.d"

$PAI_SECRET_DIR = "${PAI_WORK_DIR}\secrets"

Move-Item -Path .\* -Destination ${PAI_WORK_DIR}
Set-Location ${PAI_WORK_DIR}

# To run init scripts under init.d in init container,
# execute them here in priority order.s
# Here're the steps to onboard a new init script,
# 1. put it under init.d
# 2. give it a priority in [0, 100] and insert below in order
# 3. add the following format block

# comment for the script purpose
# priority=value
# CHILD_PROCESS="NAME_FOR_THE_INITIALIZER"
# ${PAI_INIT_DIR}/init.ps1

# error spec
# priority=1
CHILD_PROCESS="ERROR_SPEC"
Copy-Item ${PAI_CONFIG_DIR}\runtime-exit-spec.yaml ${PAI_RUNTIME_DIR}


# write user commands to user.sh
# priority=100
CHILD_PROCESS="RENDER_USER_COMMAND"
Start-Process python -Wait -ArgumentList @("${PAI_INIT_DIR}/user_command_renderer.py", "${PAI_SECRET_DIR}/secrets.yaml", "${PAI_RUNTIME_DIR}/user.ps1")