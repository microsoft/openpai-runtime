#!/bin/bash

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

set -o errexit
set -o nounset
set -o pipefail

# This runtime script will be executed inside task container,
# all scripts under runtime.d will be executed in priority order.
# User's commands will start in the end, and whole runtime script
# will exit after user's commands exit.

RUNTIME_WORK_DIR=/usr/local/pai
RUNTIME_SCRIPT_DIR=${RUNTIME_WORK_DIR}/runtime.d
RUNTIME_LOG_DIR=${RUNTIME_WORK_DIR}/logs/${FC_POD_UID}
PATTERN_FILE=${RUNTIME_SCRIPT_DIR}/runtime-exit-spec.yaml

# Keep 256MB logs
LOCAL_LOG_MAX_SIZE=$(( 256*1024*1024 )) # 256MB
LOCAL_LOG_MAX_FILES=2

# please refer to rest-server/src/models/v2/job/k8s.js
TERMINATION_MESSAGE_PATH=/tmp/pai-termination-log

RUNTIME_LOG=${RUNTIME_LOG_DIR}/runtime.log
PROCESS_RUNTIME_LOG=${RUNTIME_WORK_DIR}/runtime.d/process_runtime_log.sh

USER_STDOUT_LOG_DIR=${RUNTIME_LOG_DIR}/user-stdout
USER_STDERR_LOG_DIR=${RUNTIME_LOG_DIR}/user-stderr
USER_ALL_LOG_DIR=${RUNTIME_LOG_DIR}/user-all

function log()
{
  echo "$1" | ${PROCESS_RUNTIME_LOG} ${RUNTIME_LOG}
}

function exit_handler()
{
  USER_EXIT_CODE=$?
  if [[ $USER_EXIT_CODE -eq 0 ]]; then
    exit 0
  fi

  if [[ ! -f ${RUNTIME_LOG} ]]; then
    touch ${RUNTIME_LOG}
  fi

  # Deal with log rotate case. Merge current log with rotated log
  # if current log size is too small
  local USER_LOG_FILE=${USER_ALL_LOG_DIR}/current
  local LOG_FILE_SIZE=$(wc -c ${USER_LOG_FILE} | awk '{print $1}')
  local MIN_LOG_SIZE=$(( 16*1024 )) # 16KB
  local ROTATED_LOG_FILE=$(find ${USER_ALL_LOG_DIR} -name @*.s -print -quit)

  if [ -f ${ROTATED_LOG_FILE} ] && (( LOG_FILE_SIZE < ${MIN_LOG_SIZE} )); then
    mkdir -p ${RUNTIME_WORK_DIR}/tmp
    tail -c 16K ${ROTATED_LOG_FILE} > ${RUNTIME_WORK_DIR}/tmp/user-log
    cat ${USER_LOG_FILE} >> ${RUNTIME_WORK_DIR}/tmp/user-log
    USER_LOG_FILE=${RUNTIME_WORK_DIR}/tmp/user-log
  fi

  set +o errexit
  # genergate aggregated exit info
  ${RUNTIME_SCRIPT_DIR}/exithandler ${USER_EXIT_CODE} \
                                    ${USER_LOG_FILE} \
                                    ${RUNTIME_LOG} \
                                    ${TERMINATION_MESSAGE_PATH} ${PATTERN_FILE} | \
                                    ${PROCESS_RUNTIME_LOG} ${RUNTIME_LOG}

  CONTAINER_EXIT_CODE=$?

  if [[ -f ${TERMINATION_MESSAGE_PATH} ]]; then
    cp ${TERMINATION_MESSAGE_PATH} ${RUNTIME_LOG_DIR}
  fi

  exit ${CONTAINER_EXIT_CODE}
}

trap exit_handler EXIT

# To run runtime scripts under runtime.d in task container,
# execute them here in priority order.
# Here're the steps to onboard a new runtime script,
# 1. put it under runtime.d
# 2. give it a priority in [0, 100] and insert below in order
# 3. add the following format block, all runtime script should output to stdout and stderr

# comment for the script purpose
# priority=value
# ${RUNTIME_SCRIPT_DIR}/runtime.sh

# export runtime env variables
# priority=0
source ${RUNTIME_SCRIPT_DIR}/runtime_env.sh

# mkdir dir accessiable for other services to retrive log
mkdir -p ${USER_STDOUT_LOG_DIR} ${USER_STDERR_LOG_DIR} ${USER_ALL_LOG_DIR}
chmod a+rx ${USER_STDOUT_LOG_DIR} ${USER_STDERR_LOG_DIR} ${USER_ALL_LOG_DIR}

# execute preCommands generated by plugin
log "[INFO] Starting to exec precommands"
${RUNTIME_SCRIPT_DIR}/precommands.sh | ${PROCESS_RUNTIME_LOG} ${RUNTIME_LOG}
log "[INFO] Precommands finished"

# Put verbose output to user.pai.all, stdout to user.pai.stdout, stderr to user.pai.stderr
# execute user commands
# priority=100
log "[INFO] USER COMMAND START"
LOG_PIPE=${RUNTIME_WORK_DIR}/runtime.d/log_pip
mkfifo ${LOG_PIPE}
${RUNTIME_SCRIPT_DIR}/user.sh \
  2> >(tee >(${RUNTIME_SCRIPT_DIR}/multilog s${LOCAL_LOG_MAX_SIZE} n${LOCAL_LOG_MAX_FILES} ${USER_STDERR_LOG_DIR}) | tee -a ${LOG_PIPE} >&2) \
  > >(tee >(${RUNTIME_SCRIPT_DIR}/multilog s${LOCAL_LOG_MAX_SIZE} n${LOCAL_LOG_MAX_FILES} ${USER_STDOUT_LOG_DIR}) | tee -a ${LOG_PIPE}) &
USER_PID=$!

${RUNTIME_SCRIPT_DIR}/multilog s${LOCAL_LOG_MAX_SIZE} n${LOCAL_LOG_MAX_FILES} ${USER_ALL_LOG_DIR} < ${LOG_PIPE} &
LOGGER_PID=$!

wait ${USER_PID}
wait ${LOGGER_PID}

# synchronize cached writes to disk
sync

log "[INFO] USER COMMAND END"

# execute postCommands generated by plugin
${RUNTIME_SCRIPT_DIR}/postcommands.sh | ${PROCESS_RUNTIME_LOG} ${RUNTIME_LOG}
