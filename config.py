"""
monrela/config.py
Shared constants and config loader.
All paths resolve from the actual location of this file.
"""

import os
import json
import socket as _socket

# ── Socket ────────────────────────────────────
SOCKET_PATH = "/tmp/monrela_daemon.sock"
BUFFER_SIZE = 65536
ENCODING    = "utf-8"

# ── PID file — used to track daemon process ───
PID_FILE    = "/tmp/monrela_daemon.pid"

# ── Paths ─────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR   = os.path.join(BASE_DIR, "config")
SCRIPTS_DIR  = os.path.join(BASE_DIR, "scripts")
ALIASES_FILE = os.path.join(CONFIG_DIR, "aliases.json")

DATA_DIR     = os.path.expanduser("~/.local/share/monrela")
LOG_FILE     = os.path.join(DATA_DIR, "daemon.log")
NOTES_FILE   = os.path.join(DATA_DIR, "notes.log")


def load_aliases() -> dict:
    """Load aliases.json. Returns {} on any error."""
    if not os.path.exists(ALIASES_FILE):
        return {}
    try:
        with open(ALIASES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {
            k.lower(): v
            for k, v in raw.items()
            if not k.startswith("_")
        }
    except Exception:
        return {}


def daemon_running() -> bool:
    """
    Reliably check if a monrela daemon is alive.
    Strategy:
      1. Check PID file — if PID exists and process is alive, daemon is running.
      2. Fallback: try connecting to the socket.
      3. Clean up stale files if daemon is not actually running.
    """
    # ── PID file check (most reliable) ───────
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            # os.kill(pid, 0) doesn't kill — just checks if process exists
            os.kill(pid, 0)
            return True   # process is alive
        except (ValueError, ProcessLookupError):
            # PID file exists but process is dead — clean up
            _cleanup_stale()
            return False
        except PermissionError:
            # Process exists but owned by another user — treat as running
            return True

    # ── Socket fallback ───────────────────────
    if not os.path.exists(SOCKET_PATH):
        return False

    try:
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(SOCKET_PATH)
        return True
    except OSError:
        _cleanup_stale()
        return False


def write_pid_file():
    """Write current process PID to PID_FILE. Called by daemon on start."""
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


def _cleanup_stale():
    """Remove stale socket and PID files left by a dead daemon."""
    for path in (SOCKET_PATH, PID_FILE):
        try:
            os.unlink(path)
        except OSError:
            pass
