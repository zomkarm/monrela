"""
monrela/conditions.py
System condition check functions.
Called only by scripting.py — no other file imports this.

IMPORTANT design rule:
  - Numeric conditions (disk_usage, memory_usage, cpu_usage, battery)
    return a RAW NUMBER (float/int), not a bool.
    scripting.py applies the operator ( > < == ) itself.

  - Boolean conditions (internet_up, app_running, file_exists etc.)
    return True/False directly.

This makes the operator logic in scripting.py clean and correct.
"""

import os
import shutil
import subprocess
import datetime
import time


# ── Numeric conditions (return raw value) ─────

def get_disk_usage() -> float:
    """Return root disk usage as percentage (0-100)."""
    try:
        total, used, free = shutil.disk_usage("/")
        return (used / total) * 100
    except Exception:
        return 0.0


def get_memory_usage() -> float:
    """Return RAM usage as percentage (0-100)."""
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        info = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(":")] = int(parts[1])
        total     = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        if total == 0:
            return 0.0
        return ((total - available) / total) * 100
    except Exception:
        return 0.0


def get_cpu_usage() -> float:
    """Return CPU usage percentage. Samples over 0.3 seconds."""
    try:
        def read_stat():
            with open("/proc/stat", "r") as f:
                line = f.readline()
            parts = list(map(int, line.split()[1:]))
            return parts[3], sum(parts)  # idle, total

        idle1, total1 = read_stat()
        time.sleep(0.3)
        idle2, total2 = read_stat()
        delta_total = total2 - total1
        delta_idle  = idle2  - idle1
        if delta_total == 0:
            return 0.0
        return (1 - delta_idle / delta_total) * 100
    except Exception:
        return 0.0


def get_battery_level() -> float:
    """
    Return battery percentage (0-100).
    Returns 100.0 on desktop systems with no battery
    so battery conditions don't trigger unexpectedly.
    """
    try:
        power_dir = "/sys/class/power_supply"
        if not os.path.exists(power_dir):
            return 100.0
        for entry in os.listdir(power_dir):
            cap_file = os.path.join(power_dir, entry, "capacity")
            typ_file = os.path.join(power_dir, entry, "type")
            if os.path.exists(cap_file) and os.path.exists(typ_file):
                with open(typ_file) as f:
                    if "Battery" in f.read():
                        with open(cap_file) as cf:
                            return float(cf.read().strip())
        return 100.0
    except Exception:
        return 100.0


# ── Boolean conditions (return True/False) ────

def app_running(name: str) -> bool:
    """True if a process matching name is running."""
    try:
        r = subprocess.run(["pgrep", "-x", name], capture_output=True)
        if r.returncode == 0:
            return True
        r2 = subprocess.run(["pgrep", "-f", name], capture_output=True)
        return r2.returncode == 0
    except Exception:
        return False


def file_exists(path: str) -> bool:
    """True if a file exists at path."""
    return os.path.isfile(os.path.expandvars(os.path.expanduser(path)))


def dir_exists(path: str) -> bool:
    """True if a directory exists at path."""
    return os.path.isdir(os.path.expandvars(os.path.expanduser(path)))


def internet_up() -> bool:
    """True if internet is reachable."""
    try:
        r = subprocess.run(
            ["ping", "-c", "1", "-W", "1", "8.8.8.8"],
            capture_output=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def internet_down() -> bool:
    return not internet_up()


def time_is(target: str) -> bool:
    """True if current time matches HH:MM (within the same minute)."""
    try:
        now = datetime.datetime.now()
        t   = datetime.datetime.strptime(target.strip(), "%H:%M")
        return now.hour == t.hour and now.minute == t.minute
    except Exception:
        return False


def day_is(target: str) -> bool:
    """
    True if today matches day name or category.
    Accepts: monday tuesday wednesday thursday friday saturday sunday
             weekday weekend
    """
    target  = target.strip().lower()
    weekday = datetime.datetime.now().weekday()  # 0=Mon 6=Sun

    names = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    }
    if target == "weekday": return weekday < 5
    if target == "weekend":  return weekday >= 5
    if target in names:      return weekday == names[target]
    return False


# ── Registry ──────────────────────────────────
#
# Maps condition keyword → (function, kind)
# kind = "numeric"  → function returns a float, scripting.py applies operator
# kind = "boolean"  → function returns True/False directly
# kind = "bool_arg" → function takes one string arg, returns True/False

CONDITION_REGISTRY = {
    # Numeric — return raw value, operator applied by scripting.py
    "disk_usage":   (get_disk_usage,    "numeric"),
    "memory_usage": (get_memory_usage,  "numeric"),
    "cpu_usage":    (get_cpu_usage,     "numeric"),
    "battery":      (get_battery_level, "numeric"),

    # Boolean no-arg
    "internet_up":   (internet_up,   "boolean"),
    "internet_down": (internet_down, "boolean"),

    # Boolean with string arg
    "app_running":  (app_running,  "bool_arg"),
    "file_exists":  (file_exists,  "bool_arg"),
    "dir_exists":   (dir_exists,   "bool_arg"),
    "time_is":      (time_is,      "bool_arg"),
    "day_is":       (day_is,       "bool_arg"),
}
