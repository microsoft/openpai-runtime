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

package aggregator

import (
	"bytes"
	"fmt"
	"testing"

	"github.com/microsoft/openpai-runtime/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

type mockGpuInfoCollector struct {
	mock.Mock
	l *logger.Logger
}

func (m *mockGpuInfoCollector) collectGpuStatus() (*gpuStatus, error) {
	args := m.Called()
	return args.Get(0).(*gpuStatus), args.Error(1)
}

func initAggregator(usrLog, runtimgLog string) (*ErrorAggregator, error) {
	log := logger.NewLogger()
	l := LogFiles{
		UserLog:         usrLog,
		RuntimeErrorLog: runtimgLog,
	}
	a, err := NewErrorAggregator(&l, log)
	if err != nil {
		return nil, err
	}

	err = a.LoadRuntimeErrorSpecs("../../example/config/failurePatterns.yml")
	if err != nil {
		return nil, err
	}
	return a, nil
}

func TestGenerateExitInfo(t *testing.T) {
	a, err := initAggregator("../../example/test/user.pai.all.t1", "../../example/test/runtime.pai.error.t1")
	assert.Nil(t, err)

	exitInfo, err := a.GenerateExitInfo(137)
	assert.Nil(t, err)

	assert.Equal(t, exitInfo.Exitcode, 137)
	assert.Equal(t, exitInfo.OriginUserExitCode, 137)
}

func TestGenerateExitInfoWithRegex(t *testing.T) {
	a, err := initAggregator("../../example/test/user.pai.all.t2", "../../example/test/runtime.pai.error.t1")
	assert.Nil(t, err)

	exitInfo, err := a.GenerateExitInfo(1)
	assert.Nil(t, err)

	assert.Equal(t, exitInfo.Exitcode, 10)
	assert.Equal(t, exitInfo.OriginUserExitCode, 1)
	assert.Equal(t, *exitInfo.MatchedUserLogString, "exec(compile(getattr(tokenize, 'open', open)(__file__)")
}

func TestGenerateExitInfoWithMultiPattern(t *testing.T) {
	a, err := initAggregator("../../example/test/user.pai.all.t3", "../../example/test/runtime.pai.error.t1")
	assert.Nil(t, err)

	exitInfo, err := a.GenerateExitInfo(1)
	assert.Nil(t, err)

	assert.Equal(t, exitInfo.Exitcode, 12)
	assert.Equal(t, exitInfo.OriginUserExitCode, 1)
	assert.Equal(t, *exitInfo.MatchedUserLogString, "failed with error code 1 in /tmp/pip")
}

func TestGenerateExitInfoWithTruncateLog(t *testing.T) {
	a, err := initAggregator("../../example/test/user.pai.all.t2", "../../example/test/runtime.pai.error.t1")
	assert.Nil(t, err)

	a.SetMaxAggregateLogSize(230)
	exitInfo, err := a.GenerateExitInfo(1)
	assert.Nil(t, err)

	obuf := bytes.NewBufferString("")
	a.DumpExitSummary(exitInfo, obuf)
	fmt.Println(obuf.Len())
	assert.True(t, obuf.Len()-len(a.ExitInfoSuffix())-len(a.ExitInfoSuffix()) <= 230)
}

func TestGenerateExitInfoWithUnkonwError(t *testing.T) {
	a, err := initAggregator("../../example/test/user.pai.all.t1", "../../example/test/runtime.pai.error.t1")
	assert.Nil(t, err)

	exitInfo, err := a.GenerateExitInfo(254)
	assert.Nil(t, err)

	assert.Equal(t, exitInfo.Exitcode, 255)
	assert.Equal(t, exitInfo.OriginUserExitCode, 254)
}

func TestGenerateExitInfoWithAndLogic(t *testing.T) {
	a, err := initAggregator("../../example/test/user.pai.all.t4", "../../example/test/runtime.pai.error.t1")
	assert.Nil(t, err)

	exitInfo, err := a.GenerateExitInfo(1)
	assert.Nil(t, err)

	assert.Equal(t, exitInfo.Exitcode, 15)
	assert.Equal(t, exitInfo.OriginUserExitCode, 1)
	assert.Equal(t, *exitInfo.MatchedPlatformLogString, "Failed to start tensorboard")
	assert.Equal(t, *exitInfo.MatchedUserLogString, "connect tensorboard failed")
}

func TestGenerateExitWithEnvInfo(t *testing.T) {
	mockGpuInfoCollector := new(mockGpuInfoCollector)
	mockGpuInfoCollector.On("collectGpuStatus").Return(&gpuStatus{2}, nil)
	a, _ := initAggregator("../../example/test/user.pai.all.t1", "../../example/test/runtime.pai.error.t1")
	a.gpuInfoCollector = mockGpuInfoCollector
	exitInfo, err := a.GenerateExitInfo(1)
	assert.Nil(t, err)

	expectedGpuInfo := &gpuInfo{NvidiaDoubleEccError: true}
	assert.Equal(t, exitInfo.Exitcode, 16)
	assert.Equal(t, exitInfo.MatchedGpuInfo, expectedGpuInfo)
}

func TestGenerateExitInfoWithTruncateFail(t *testing.T) {
	a, err := initAggregator("../../example/test/user.pai.all.t5", "../../example/test/runtime.pai.error.t1")
	assert.Nil(t, err)

	a.SetMaxAggregateLogSize(128)
	exitInfo, _ := a.GenerateExitInfo(1)
	obuf := bytes.NewBufferString("")
	a.DumpExitSummary(exitInfo, obuf)

	assert.Equal(t, exitInfo.Exitcode, 221)
	assert.Equal(t, exitInfo.OriginUserExitCode, 1)
}
