"""Run a command and measure wall time, CPU time, peak RAM and GPU memory.

Windows only, stdlib only: RAM via psapi PeakWorkingSetSize of the launched
process (not its children), GPU via nvidia-smi polling (whole-GPU numbers).
"""
import ctypes
import ctypes.wintypes as wt
import datetime
import json
import subprocess
import threading
import time

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
# Without explicit types ctypes truncates 64-bit handles (GetCurrentProcess() is -1).
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wt.DWORD]


def open_process(pid):
    return kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)


def peak_rss(handle):
    c = PROCESS_MEMORY_COUNTERS()
    c.cb = ctypes.sizeof(c)
    if psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb):
        return c.PeakWorkingSetSize
    return 0


def cpu_seconds(handle):
    t = [wt.FILETIME() for _ in range(4)]
    if not kernel32.GetProcessTimes(handle, *[ctypes.byref(x) for x in t]):
        return 0.0
    to_s = lambda f: ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7
    return to_s(t[2]) + to_s(t[3])


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def system_used_mb():
    """Whole-system RAM in use; catches child processes that launchers hide from per-process counters."""
    s = MEMORYSTATUSEX()
    s.dwLength = ctypes.sizeof(s)
    kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return (s.ullTotalPhys - s.ullAvailPhys) / 2**20


def gpu_sample():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu,utilization.encoder",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    mem, util, enc = (float(v) for v in out.strip().split(","))
    return mem, util, enc


def run(cmd, log_path=None):
    base_mem, _, _ = gpu_sample()
    base_sys = system_used_mb()
    samples, sys_peak = [], [base_sys]
    stop = threading.Event()

    def poll_gpu():
        while not stop.is_set():
            samples.append(gpu_sample())
            sys_peak.append(system_used_mb())
            time.sleep(0.25)

    poller = threading.Thread(target=poll_gpu, daemon=True)
    log = open(log_path, "w", encoding="utf-8") if log_path else subprocess.DEVNULL
    start = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    handle = open_process(proc.pid)
    poller.start()
    peak = 0
    while proc.poll() is None:
        peak = max(peak, peak_rss(handle))
        time.sleep(0.1)
    wall = time.perf_counter() - start
    peak = max(peak, peak_rss(handle))
    cpu = cpu_seconds(handle)
    kernel32.CloseHandle(handle)
    stop.set()
    poller.join()
    if log_path:
        log.close()
    gpu_peak = max((s[0] for s in samples), default=base_mem)
    return {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "returncode": proc.returncode,
        "wall_s": round(wall, 2),
        "cpu_s": round(cpu, 2),
        "avg_cores_busy": round(cpu / wall, 2) if wall else None,
        "peak_ram_mb": round(peak / 2**20, 1),
        "system_ram_delta_mb": round(max(sys_peak) - base_sys, 1),
        "gpu_mem_baseline_mb": base_mem,
        "gpu_mem_peak_mb": gpu_peak,
        "gpu_mem_delta_mb": gpu_peak - base_mem,
        "gpu_util_max_pct": max((s[1] for s in samples), default=0),
        "nvenc_util_max_pct": max((s[2] for s in samples), default=0),
        "gpu_samples": len(samples),
        "cmd": cmd,
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(run(sys.argv[1:]), indent=2))
