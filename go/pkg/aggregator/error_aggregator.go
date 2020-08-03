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
	"errors"
	"io"
	"io/ioutil"
	"os"
	"reflect"
	"regexp"
	"strings"

	"github.com/microsoft/openpai-runtime/pkg/logger"
	"gopkg.in/yaml.v2"
)

type runtimeErrorSpec struct {
	ContainerExitCode int       `yaml:"containerExitCode"`
	Patterns          []pattern `yaml:"patterns"`
}

type pattern struct {
	ExitCode         *int     `yaml:"exitCode"`
	UserLogRegex     *string  `yaml:"userLogRegex"`
	PlatformLogRegex *string  `yaml:"platformLogRegex"`
	GpuInfo          *gpuInfo `yaml:"gpuInfo"`
	// Can add more patterns here
}

type gpuInfo struct {
	NvidiaDoubleEccError bool `yaml:"nvidiaDoubleEccError,omitempty"`
}

type errorLogs struct {
	User     *string `yaml:"user,omitempty"`
	Platform *string `yaml:"platform,omitempty"`
}

// RuntimeExitInfo the aggregated exit info
type RuntimeExitInfo struct {
	Exitcode                 int        `yaml:"exitCode"`
	Trigger                  *string    `yaml:"trigger,omitempty"`
	OriginUserExitCode       int        `yaml:"originUserExitCode"`
	MatchedUserLogString     *string    `yaml:"matchedUserLogString,omitempty"`
	MatchedPlatformLogString *string    `yaml:"matchedPlatformLogString,omitempty"`
	MatchedGpuInfo           *gpuInfo   `yaml:"matchedGpuInfo,omitempty"`
	CaughtException          *string    `yaml:"caughtException,omitempty"`
	ErrorLogs                *errorLogs `yaml:"errorLogs,omitempty"`
}

// LogFiles point the path for userLog and platLog
type LogFiles struct {
	UserLog         string
	RuntimeErrorLog string
}

type matchResult struct {
	matchedUserLog     *string
	matchedPlatformLog *string
	platLog            []string
	userLog            []string
	gpuInfo            *gpuInfo
}

// ErrorAggregator is used to generate the aggregate error message
type ErrorAggregator struct {
	errorSpecs          []*runtimeErrorSpec
	logFiles            *LogFiles
	logger              *logger.Logger
	gpuInfoCollector    gpuInfoCollector
	maxAggregateLogSize int
	maxMatchLogLen      int
	maxUserLogLines     int
	maxRuntimeLogLines  int
	defaultExitCode     int
	maxSearchLogSize    int64
	aggExitInfoBegin    string
	aggExitInfoEnd      string
}

func ptrString(o string) *string {
	return &o
}

func ptrInt(o int) *int {
	return &o
}

// LoadRuntimeErrorSpecs is used to load error spec from configured yaml file
func (a *ErrorAggregator) LoadRuntimeErrorSpecs(fileName string) error {
	failurePatterns, err := ioutil.ReadFile(fileName)
	if err != nil {
		a.logger.Error("failed to load runtime spec:", err)
		return err
	}

	err = yaml.Unmarshal(failurePatterns, &a.errorSpecs)
	if err != nil {
		a.logger.Error("failed to unmarshal:", err)
		return err
	}
	return nil
}

// GenerateExitInfo is used to generate the exit info
func (a *ErrorAggregator) GenerateExitInfo(userExitCode int) (*RuntimeExitInfo, error) {
	var exitInfo RuntimeExitInfo
	var result *matchResult
	var isMatch bool

	// no error occur
	if userExitCode == 0 {
		return nil, nil
	}

	userFile, err := os.Open(a.logFiles.UserLog)
	if err != nil {
		return nil, err
	}
	defer userFile.Close()

	runtimeFile, err := os.Open(a.logFiles.RuntimeErrorLog)
	if err != nil {
		return nil, err
	}
	defer runtimeFile.Close()

	userLog, err := a.getTailContentFromFile(userFile, a.maxSearchLogSize)
	if err != nil {
		a.logger.Error("some error occur when getting user log conent, may cause inaccurate result", err)
	}

	platformLog, err := a.getTailContentFromFile(runtimeFile, a.maxSearchLogSize)
	if err != nil {
		a.logger.Error("some error occur when getting runtime user log conent, may cause inaccurate result", err)
	}

	gi := a.collectGpuInfo()

	for _, spec := range a.errorSpecs {
		isMatch, result = a.matchSpecPatten(spec, userExitCode, userLog, platformLog, gi)
		if isMatch {
			exitInfo.Exitcode = spec.ContainerExitCode
			exitInfo.OriginUserExitCode = userExitCode
			exitInfo.MatchedUserLogString = result.matchedUserLog
			exitInfo.MatchedPlatformLogString = result.matchedPlatformLog
			exitInfo.CaughtException = nil
			exitInfo.MatchedGpuInfo = result.gpuInfo
			if result.platLog != nil || result.userLog != nil {
				exitInfo.ErrorLogs = new(errorLogs)
				exitInfo.ErrorLogs.Platform = ptrString(strings.Join(result.platLog, "\n"))
				exitInfo.ErrorLogs.User = ptrString(strings.Join(result.userLog, "\n"))
			}
			break
		}
	}

	if !isMatch {
		exitInfo.Exitcode = a.defaultExitCode
		exitInfo.OriginUserExitCode = userExitCode
		exitInfo.ErrorLogs = new(errorLogs)
		exitInfo.ErrorLogs.Platform = ptrString(strings.Join(a.extractNlinesTailLog(platformLog, a.maxRuntimeLogLines), "\n"))
		exitInfo.ErrorLogs.User = ptrString(strings.Join(a.extractNlinesTailLog(userLog, a.maxUserLogLines), "\n"))
	}

	return &exitInfo, nil
}

// DumpExitSummary dump the summarized exit info into file
func (a *ErrorAggregator) DumpExitSummary(exitInfo *RuntimeExitInfo, dumpFile io.Writer) error {
	var aggregateLog []string
	truncatedData, err := a.truncateExitSummary(exitInfo)
	if err != nil {
		a.logger.Error("failed to get truncate exit info, err:", err)
		return err
	}

	aggregateLog = append(aggregateLog, a.aggExitInfoBegin, string(truncatedData), a.aggExitInfoEnd)
	_, err = dumpFile.Write([]byte(strings.Join(aggregateLog, "\n")))
	if err != nil {
		a.logger.Error("failed to write runtime exit info into file:", err)
		return err
	}
	return nil
}

func (a *ErrorAggregator) getPatternLoc(regex string, content []byte) ([]int, error) {
	r, err := regexp.Compile(regex)
	if err != nil {
		return nil, err
	}
	loc := r.FindIndex(content)
	return loc, nil
}

func (a *ErrorAggregator) mergeLogs(lhs []string, rhs []string, match []string, content string, matchLoc []int) []string {
	var res []string
	res = append(res, lhs...)

	i, l := matchLoc[0], matchLoc[1]
	if lhs != nil && i > 0 && content[i-1] != '\n' {
		res[len(res)-1] = lhs[len(lhs)-1] + match[0]
		res = append(res, match[1:]...)
	} else {
		res = append(res, match...)
	}

	if e := i + l; rhs != nil && e < len(content) && content[e] != '\n' {
		res[len(res)-1] = res[len(res)-1] + rhs[0]
		res = append(res, rhs[1:]...)
	} else {
		res = append(res, rhs...)
	}
	return res
}

func (a *ErrorAggregator) extractNlinesTailLog(conent []byte, maxLogLines int) []string {
	var start int
	if logLen := len(conent); logLen > a.maxAggregateLogSize {
		start = logLen - a.maxAggregateLogSize
	}
	truncatedLog := string(conent[start:])
	truncatedLogLines := strings.Split(strings.ReplaceAll(truncatedLog, "\r\n", "\n"), "\n")
	length := len(truncatedLogLines)
	if length < maxLogLines {
		return truncatedLogLines
	}
	return truncatedLogLines[length-maxLogLines:]
}

func (a *ErrorAggregator) extractMatchLog(loc []int, content []byte, maxLogLines int) ([]string, error) {
	// use simple rules. will extract 2 lines above the match pattern and other lines below the match pattern
	if loc == nil {
		// fallback to extract tail logs
		return a.extractNlinesTailLog(content, maxLogLines), nil
	}

	if len(loc) < 2 {
		return nil, errors.New("loc is invalid")
	}

	startPos := loc[0] - a.maxAggregateLogSize
	endPos := loc[1] + a.maxAggregateLogSize

	if startPos < 0 {
		startPos = 0
	}

	if endPos >= len(content) {
		endPos = len(content)
	}

	matchString := string(content[loc[0]:loc[1]])
	curContent := string(content[startPos:endPos])
	curContent = strings.ReplaceAll(curContent, "\r\n", "\n")

	matchStartIndex := strings.Index(curContent, matchString)
	lhsLines := strings.Split(curContent[:matchStartIndex], "\n")
	rhsLines := strings.Split(curContent[matchStartIndex+len(matchString):], "\n")
	matchLines := strings.Split(matchString, "\n")

	if len(matchLines) >= maxLogLines {
		return matchLines[len(matchLines)-maxLogLines : len(matchLines)], nil
	}

	// if the logs behind match string only contains few lines, try to extract more logs before the match string
	lhsLineOffset := 3
	if lines, stagingLines := maxLogLines-lhsLineOffset, len(rhsLines)+len(matchLines); stagingLines < lines {
		lhsLineOffset = maxLogLines - stagingLines
	}

	var lhsStart, rhsEnd int
	if lhsStart = len(lhsLines) - lhsLineOffset; lhsStart < 0 {
		lhsStart = 0
	}

	lhsLineNumber := len(lhsLines) - lhsStart
	if rhsEnd = maxLogLines - lhsLineNumber - len(matchLines); rhsEnd < 0 {
		rhsEnd = 0
	}
	if rhsEnd > len(rhsLines) {
		rhsEnd = len(rhsLines)
	}
	logLines := a.mergeLogs(lhsLines[lhsStart:], rhsLines[:rhsEnd], matchLines, curContent,
		[]int{matchStartIndex, len(matchString)})

	if len(logLines) > maxLogLines {
		logLines = logLines[len(logLines)-maxLogLines:]
	}
	return logLines, nil
}

func (a *ErrorAggregator) getMatchedLogString(loc []int, log []byte) *string {
	if loc != nil && len(loc) == 2 {
		match := log[loc[0]:loc[1]]
		if len(match) > a.maxMatchLogLen {
			a.logger.Warning("The size of match log len is", len(match), "more than", a.maxMatchLogLen)
			match = match[:a.maxMatchLogLen]
		}
		return ptrString(string(match))
	}
	return nil
}

func (a *ErrorAggregator) matchSpecPatten(spec *runtimeErrorSpec, userExitCode int, userLog []byte,
	platformLog []byte, gpuInfo *gpuInfo) (bool, *matchResult) {
	var result = new(matchResult)
	var platPatternLoc, userPatternLoc []int
	var err error

	for _, p := range spec.Patterns {
		if p.ExitCode != nil && *p.ExitCode != userExitCode {
			continue
		}

		if p.PlatformLogRegex != nil {
			platPatternLoc, err = a.getPatternLoc(*p.PlatformLogRegex, platformLog)
			if err != nil {
				a.logger.Error("Regex pattern is invalid", err)
				continue
			}
			if platPatternLoc == nil {
				continue
			}
		}
		if p.UserLogRegex != nil {
			userPatternLoc, err = a.getPatternLoc(*p.UserLogRegex, userLog)
			if err != nil {
				a.logger.Error("regex pattern is invalid", err)
				continue
			}
			if userPatternLoc == nil {
				continue
			}
		}
		if p.GpuInfo != nil {
			if !reflect.DeepEqual(p.GpuInfo, gpuInfo) {
				continue
			}
		}

		// we can get matched pattern here
		var platLogLines, userLogLines []string
		platLogLines, err = a.extractMatchLog(platPatternLoc, platformLog, a.maxRuntimeLogLines)
		if err != nil {
			a.logger.Error("extract platLog error", err)
		}

		userLogLines, err = a.extractMatchLog(userPatternLoc, userLog, a.maxUserLogLines)
		if err != nil {
			a.logger.Error("extract userLog error", err)
		}

		result.matchedUserLog = a.getMatchedLogString(userPatternLoc, userLog)
		result.matchedPlatformLog = a.getMatchedLogString(platPatternLoc, platformLog)
		result.platLog = platLogLines
		result.userLog = userLogLines
		result.gpuInfo = p.GpuInfo
		return true, result
	}
	return false, nil
}

func (a *ErrorAggregator) getTailContentFromFile(f *os.File, maxTailSize int64) ([]byte, error) {
	stat, err := f.Stat()
	if err != nil {
		return nil, err
	}

	off := int64(0)
	fileSize := stat.Size()
	readSize := fileSize

	if fileSize == 0 {
		return nil, nil
	}

	if fileSize > maxTailSize {
		off = fileSize - maxTailSize
		readSize = maxTailSize
	}

	content := make([]byte, readSize)
	_, err = f.ReadAt(content, off)
	return content, err
}

func (a *ErrorAggregator) truncateLog(logConent *string, truncateSize int, matchString *string) (*string, int) {
	if logConent == nil {
		return nil, 0
	}

	logSize := len(*logConent)
	matchBeginPos := -1
	if matchString != nil {
		matchBeginPos = strings.Index(*logConent, *matchString)
	}

	if logSize > truncateSize {
		if matchString == nil || matchBeginPos == -1 || matchBeginPos > truncateSize {
			truncatedLog := (*logConent)[truncateSize:]
			return &truncatedLog, logSize - len(truncatedLog)
		}
		// try to keep the match string as much as possible
		truncatedLog := (*logConent)[matchBeginPos:]
		remainTruncateSize := truncateSize - matchBeginPos
		truncatedLog = truncatedLog[:len(truncatedLog)-remainTruncateSize]
		return &truncatedLog, logSize - len(truncatedLog)
	}
	return nil, logSize
}

func (a *ErrorAggregator) getMinimalExitSummary(r *RuntimeExitInfo) *RuntimeExitInfo {
	var ret RuntimeExitInfo
	ret.OriginUserExitCode = r.OriginUserExitCode
	ret.Exitcode = r.Exitcode
	ret.MatchedGpuInfo = r.MatchedGpuInfo
	return &ret
}

func (a *ErrorAggregator) recalculateRemainTruncateSize(r *RuntimeExitInfo, currentSize int, remainSize int) ([]byte, int, error) {
	data, err := yaml.Marshal(r)
	if err != nil {
		return nil, remainSize, err
	}
	return data, remainSize - (currentSize - len(data)), nil
}

// runtimeExitInfo will be modified in this function
func (a *ErrorAggregator) truncateExitSummary(runtimeExitInfo *RuntimeExitInfo) ([]byte, error) {
	data, err := yaml.Marshal(runtimeExitInfo)
	if err != nil {
		return nil, err
	}

	exitInfoSize := len(data)
	leftSize := a.maxAggregateLogSize
	if exitInfoSize <= leftSize {
		return data, nil
	}
	remainTruncateSize := exitInfoSize - leftSize

	if runtimeExitInfo.ErrorLogs != nil {
		// truncate runtime log first
		truncatedRuntimeLog, _ := a.truncateLog(runtimeExitInfo.ErrorLogs.Platform, remainTruncateSize, runtimeExitInfo.MatchedPlatformLogString)
		runtimeExitInfo.ErrorLogs.Platform = truncatedRuntimeLog
		// recalculate the length here since more space will be free after yaml formatted
		if data, remainTruncateSize, err = a.recalculateRemainTruncateSize(runtimeExitInfo, len(data), remainTruncateSize); err != nil {
			return nil, err
		}
		if remainTruncateSize <= 0 {
			return data, nil
		}

		// truncate the user log
		truncatedUserLog, _ := a.truncateLog(runtimeExitInfo.ErrorLogs.User, remainTruncateSize, runtimeExitInfo.MatchedUserLogString)
		runtimeExitInfo.ErrorLogs.User = truncatedUserLog
		if data, remainTruncateSize, err = a.recalculateRemainTruncateSize(runtimeExitInfo, len(data), remainTruncateSize); err != nil {
			return nil, err
		}
		if remainTruncateSize <= 0 {
			return data, nil
		}
	}

	if runtimeExitInfo.MatchedPlatformLogString != nil {
		// truncate the match log
		l := len(*runtimeExitInfo.MatchedPlatformLogString) - remainTruncateSize
		if l >= 0 {
			runtimeExitInfo.MatchedPlatformLogString = ptrString((*runtimeExitInfo.MatchedPlatformLogString)[:l])
			data, err := yaml.Marshal(runtimeExitInfo)
			return data, err
		}
		runtimeExitInfo.MatchedPlatformLogString = nil
		if data, remainTruncateSize, err = a.recalculateRemainTruncateSize(runtimeExitInfo, len(data), remainTruncateSize); err != nil {
			return nil, err
		}
	}

	if runtimeExitInfo.MatchedUserLogString != nil {
		l := len(*runtimeExitInfo.MatchedUserLogString) - remainTruncateSize
		if l >= 0 {
			runtimeExitInfo.MatchedUserLogString = ptrString((*runtimeExitInfo.MatchedUserLogString)[:l])
			data, err := yaml.Marshal(runtimeExitInfo)
			return data, err
		}
	}

	a.logger.Warning("Failed to truncate, use minmal exit info as return value")
	return yaml.Marshal(a.getMinimalExitSummary(runtimeExitInfo))
}

func (a *ErrorAggregator) collectGpuInfo() *gpuInfo {
	gi := gpuInfo{}
	gpuStatus, err := a.gpuInfoCollector.collectGpuStatus()
	if err != nil {
		a.logger.Warning("failed to collect gpu status, maybe in CPU env")
	} else {
		if gpuStatus.nvidaDoubleEccErrorCount > 0 {
			gi.NvidiaDoubleEccError = true
		}
	}
	return &gi
}

// SetMaxAggregateLogSize to set maxAggregateLogSize and used for test
func (a *ErrorAggregator) SetMaxAggregateLogSize(size int) {
	a.maxAggregateLogSize = size
}

// ExitInfoPrefix get aggregate log prefix
func (a *ErrorAggregator) ExitInfoPrefix() string {
	return a.aggExitInfoBegin
}

// ExitInfoSuffix get aggregate log suffix
func (a *ErrorAggregator) ExitInfoSuffix() string {
	return a.aggExitInfoEnd
}

// NewErrorAggregator create an error aggregator
func NewErrorAggregator(l *LogFiles, logger *logger.Logger) (*ErrorAggregator, error) {
	if len(l.UserLog) == 0 || len(l.RuntimeErrorLog) == 0 {
		return nil, errors.New("invalid log file")
	}

	if logger == nil {
		return nil, errors.New("logger not provide")
	}

	const exitInfoBeginTag = "[PAI_RUNTIME_ERROR_START]"
	const exitInfoEndTag = "[PAI_RUNTIME_ERROR_END]"

	a := ErrorAggregator{
		logFiles:            l,
		logger:              logger,
		gpuInfoCollector:    newGpuInfoCollector(logger),
		maxAggregateLogSize: 4096 - len(exitInfoBeginTag) - len(exitInfoEndTag),
		maxMatchLogLen:      2048,
		maxUserLogLines:     15,
		maxRuntimeLogLines:  10,
		defaultExitCode:     255,
		maxSearchLogSize:    10 * 1024 * 1024, // 10MB
		aggExitInfoBegin:    exitInfoBeginTag,
		aggExitInfoEnd:      exitInfoEndTag,
	}
	return &a, nil
}
