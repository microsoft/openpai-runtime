package aggregator

import (
	"bytes"
	"fmt"
	"testing"

	"github.com/microsoft/openpai-runtime/pkg/logger"
	"github.com/stretchr/testify/assert"
)

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
