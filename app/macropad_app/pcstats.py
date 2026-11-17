"""PC numbers for the "PC stats" widget: CPU and RAM use (psutil) and, for
NVIDIA graphics cards, GPU use and temperature (NVML). Anything that is not
available is None."""

import logging

log = logging.getLogger("macropad.pcstats")


class PcStats:
    def __init__(self):
        self._psutil = None
        self._nvml = None
        self._gpu = None
        try:
            import psutil
            self._psutil = psutil
            psutil.cpu_percent(interval=None)        # the first call only starts measuring
        except Exception as e:
            log.info("CPU/RAM numbers not available: %s", e)
        try:
            import pynvml
            pynvml.nvmlInit()
            if pynvml.nvmlDeviceGetCount() > 0:
                self._nvml = pynvml
                self._gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as e:
            log.info("No NVIDIA GPU numbers: %s", e)

    def sample(self):
        """(cpu %, ram %, gpu %, gpu °C), None where unknown."""
        cpu = ram = gpu = temp = None
        if self._psutil:
            try:
                cpu = self._psutil.cpu_percent(interval=None)
                ram = self._psutil.virtual_memory().percent
            except Exception:
                pass
        if self._nvml:
            try:
                gpu = float(self._nvml.nvmlDeviceGetUtilizationRates(self._gpu).gpu)
                temp = float(self._nvml.nvmlDeviceGetTemperature(self._gpu, 0))   # 0 = the GPU itself
            except Exception:
                pass
        return cpu, ram, gpu, temp
