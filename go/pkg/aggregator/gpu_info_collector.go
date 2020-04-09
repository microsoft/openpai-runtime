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
	"context"
	"encoding/xml"
	"errors"
	"os/exec"
	"strconv"
	"time"

	"github.com/microsoft/openpai-runtime/pkg/logger"
)

type gpuStatus struct {
	nvidaDoubleEccErrorCount uint64
}

type gpuInfoCollector interface {
	collectGpuStatus() (*gpuStatus, error)
}

type nvidiaGpuInfoCollector struct {
	logger *logger.Logger
}

type nvidiaSmi struct {
	XMLName xml.Name    `xml:"nvidia_smi_log"`
	Gpus    []nvidiaGpu `xml:"gpu"`
}

type nvidiaGpu struct {
	EccErrors nvidiaEccErrors `xml:"ecc_errors"`
}

type nvidiaEccErrors struct {
	Volatile volatileError `xml:"volatile"`
}

type volatileError struct {
	DoubleBitTotal string `xml:"double_bit>total"`
}

func (g *nvidiaGpuInfoCollector) collectGpuStatus() (*gpuStatus, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, "nvidia-smi", "-q", "-x")

	out, err := cmd.Output()
	if err != nil {
		g.logger.Warning("failed to exec nvidia-smi")
		return nil, err
	}

	return g.parseNvidiaSmiOuput(out)
}

func (g *nvidiaGpuInfoCollector) parseNvidiaSmiOuput(nvidiaSmiOutput []byte) (*gpuStatus, error) {
	var nvidiaSmi nvidiaSmi
	err := xml.Unmarshal(nvidiaSmiOutput, &nvidiaSmi)
	if err != nil {
		g.logger.Warning("failed to parse nvidia-smi output")
		return nil, errors.New("nvidia-smi output is broken")
	}

	var doubleEccErrorCount uint64
	for _, gpu := range nvidiaSmi.Gpus {
		count, err := strconv.ParseUint(gpu.EccErrors.Volatile.DoubleBitTotal, 10, 64)
		if err != nil {
			// The value can be N/A if none ecc error
			continue
		}
		doubleEccErrorCount += count
	}
	return &gpuStatus{doubleEccErrorCount}, nil
}

func newGpuInfoCollector(logger *logger.Logger) gpuInfoCollector {
	// Currently, only support nvida gpu
	return &nvidiaGpuInfoCollector{logger}
}
