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
	"github.com/NVIDIA/gpu-monitoring-tools/bindings/go/nvml"
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

func (g *nvidiaGpuInfoCollector) collectGpuStatus() (*gpuStatus, error) {
	err := nvml.Init()
	if err != nil {
		return nil, err
	}

	count, err := nvml.GetDeviceCount()
	if err != nil {
		return nil, err
	}
	var doubleEccErrorCount uint64 = 0
	for i := uint(0); i < count; i++ {
		device, err := nvml.NewDevice(i)
		if err != nil {
			g.logger.Warning("failed to get device:", err)
		}
		status, err := device.Status()
		if err != nil {
			g.logger.Warning("failed to get device status", err)
		}
		if status.Memory.ECCErrors.Device != nil {
			doubleEccErrorCount += *status.Memory.ECCErrors.Device
		}
		if status.Memory.ECCErrors.L1Cache != nil {
			doubleEccErrorCount += *status.Memory.ECCErrors.L2Cache
		}
		if status.Memory.ECCErrors.L2Cache != nil {
			doubleEccErrorCount += *status.Memory.ECCErrors.L2Cache
		}
	}
	defer nvml.Shutdown()
	return &gpuStatus{doubleEccErrorCount}, nil
}

func newGpuInfoCollector(logger *logger.Logger) gpuInfoCollector {
	// Currently, only support nvida gpu
	return &nvidiaGpuInfoCollector{logger}
}
