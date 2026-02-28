import os
from pynq.ps import Clocks

# Defualt CPU path on the Ultra96
CPU_ROOT = "/sys/devices/system/cpu"


def _write_sys(path, value):
    """
    System write function. Enables editing of system files to change configurations
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(value))
        return True
    except OSError as e:
        print(f"[pm] skipped {path}: {e}")
        return False


def _cpus():
    """
    Fetch available CPUs for power profile
    """
    if not os.path.isdir(CPU_ROOT):
        return []
    return sorted(
        [e for e in os.listdir(CPU_ROOT) if e.startswith("cpu") and e[3:].isdigit()],
        key=lambda x: int(x[3:]),
    )


def _freq_table():
    """
    List available clocking frequency to set for CPUs
    """
    path = os.path.join(CPU_ROOT, "cpu0", "cpufreq", "scaling_available_frequencies")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sorted({int(x) for x in f.read().split()})
    except (OSError, ValueError):
        return []


def set_cpu_freq_userspace(policy="max", freq_khz=None):
    """
    Set CPU freqneucy under userspace profile
    """
    freqs = _freq_table()
    if not freqs:
        print("[pm] no available CPU frequencies found")
        return False

    target = min(freqs, key=lambda f: abs(f - int(freq_khz))) if freq_khz is not None else (freqs[-1] if policy == "max" else freqs[0])

    ok = False

    # Write frqeuency all available CPUs
    for cpu in _cpus():
        gov = os.path.join(CPU_ROOT, cpu, "cpufreq", "scaling_governor")
        spd = os.path.join(CPU_ROOT, cpu, "cpufreq", "scaling_setspeed")
        if os.path.exists(gov):
            _write_sys(gov, "userspace")
        if os.path.exists(spd):
            ok = _write_sys(spd, target) or ok

    if ok:
        print(f"[pm] set userspace CPU freq={target} kHz")
    return ok


def set_cpu_core_online(min_online):
    """
    Turn on [0, min_online] of CPU cores
    """
    min_online = max(1, int(min_online))
    for cpu in _cpus():
        idx = int(cpu[3:])
        online = os.path.join(CPU_ROOT, cpu, "online")
        if os.path.exists(online):
            _write_sys(online, 1 if idx < min_online else 0)
    print(f"[pm] set {min_online} cores online")


def set_pl_clock_mhz(mhz, idx=0):
    """
    Set clocking frequency for Programming Logic of FPGA
    """
    attr = f"fclk{int(idx)}_mhz"
    try:
        setattr(Clocks, attr, float(mhz))
        print(f"[pm] set {attr}={float(mhz)} MHz")
        return True
    except Exception as e:
        print(f"[pm] failed to set {attr}: {e}")
        return False


def apply_profile(profile):
    """
    Apply user's selected power profile
    """
    if profile == "performance":
        set_cpu_freq_userspace(policy="max")
        set_cpu_core_online(4)
        set_pl_clock_mhz(200.0, 0)
        print("[pm] profile=performance")
        return
    if profile == "powersave":
        set_cpu_freq_userspace(policy="min")
        set_cpu_core_online(1)
        set_pl_clock_mhz(100.0, 0)
        print("[pm] profile=powersave")
        return
