// MIT License
//
// Copyright (c) Microsoft Corporation. All rights reserved.
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE

package main

import (
	"os"
	"strconv"
	"time"

	"github.com/microsoft/openpai-runtime/pkg/aggregator"
	"github.com/microsoft/openpai-runtime/pkg/logger"
)

var log *logger.Logger

const abnormalExitCode = 1

func init() {
	log = logger.NewLogger()
}

// This function will extract error summary to the specific file and print the exit code
func main() {
	defer func() {
		if r := recover(); r != nil {
			log.Error("runtime failed to handle exit info", r)
			os.Exit(abnormalExitCode)
		}
	}()

	argsWithoutProg := os.Args[1:]
	if len(argsWithoutProg) < 5 {
		panic("args is not valid")
	}

	userExitCode, err := strconv.Atoi(argsWithoutProg[0])
	if err != nil {
		panic("user exit code is not an int value: " + err.Error())
	}

	userLog := argsWithoutProg[1]
	runtimeErrorLog := argsWithoutProg[2]
	aggFilePath := argsWithoutProg[3]
	patternPath := argsWithoutProg[4]

	logFiles := aggregator.LogFiles{}
	logFiles.UserLog = userLog
	logFiles.RuntimeErrorLog = runtimeErrorLog

	exitInfo := &aggregator.RuntimeExitInfo{
		Exitcode:           abnormalExitCode,
		OriginUserExitCode: userExitCode,
	}

	log.Info("start to generate the exit summary")
	start := time.Now()
	a, err := aggregator.NewErrorAggregator(&logFiles, log)
	if err != nil {
		panic("fatal: create log aggregator: " + err.Error())
	}

	err = a.LoadRuntimeErrorSpecs(patternPath)
	if err != nil {
		panic("fatal: loading runtime error spec: " + err.Error())
	}
	exitInfo, err = a.GenerateExitInfo(int(userExitCode))
	if err != nil {
		panic("fatal: failed to generate the exitInfo" + err.Error())
	}

	aggFile, err := os.Create(aggFilePath)
	if err != nil {
		panic("fatal: create aggregate file: " + err.Error())
	}
	defer aggFile.Close()

	err = a.DumpExitSummary(exitInfo, aggFile)
	if err != nil {
		panic("fatal: dumping summary info: " + err.Error())
	}
	elapsed := time.Since(start)
	log.Info("finish generating the exit summary, time consumed:", elapsed)

	os.Exit(exitInfo.Exitcode)
}
