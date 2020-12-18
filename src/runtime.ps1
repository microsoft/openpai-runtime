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

$RUNTIME_WORK_DIR = "/usr/local/pai"
$RUNTIME_SCRIPT_DIR = "${RUNTIME_WORK_DIR}/runtime.d"
$RUNTIME_LOG_DIR = "${RUNTIME_WORK_DIR}/logs/${FC_POD_UID}"

$RUNTIME_LOG_DIR = "${RUNTIME_WORK_DIR}/logs/${FC_POD_UID}"
$PATTERN_FILE = "${RUNTIME_SCRIPT_DIR}/runtime-exit-spec.yaml"

$user_exit_code = 0
trap {
    Start-Process ${RUNTIME_SCRIPT_DIR}\exithandler.exe -Wait \
                -ArgumentList @("${USER_EXIT_CODE}",
                                "${USER_LOG_FILE}",
                                ${RUNTIME_LOG}
                                ${TERMINATION_MESSAGE_PATH} ${PATTERN_FILE} | \
                                ${PROCESS_RUNTIME_LOG} ${RUNTIME_LOG}

}

$job_id = Start-Job -FilePath "${RUNTIME_SCRIPT_DIR}/user.ps1"
$job_id | Wait-Job

$user_exit_code = $?
if ($user_exit_code -eq $false) {
    throw "user command faield"
}