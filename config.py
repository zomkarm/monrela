"""
monrela/config.py
Shared constants and config loader.
Imported by both daemon.py and palette.py.
"""

import os
import json

# ── Socket ────────────────────────────────────
SOCKET_PATH = "/tmp/monrela_daemon.sock"
BUFFER_SIZE = 65536
ENCODING    = "utf-8"

# ── Paths ─────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR  = os.path.join(BASE_DIR, "config")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
DATA_DIR    = os.path.expanduser("~/.local/share/monrela")
LOG_FILE    = os.path.join(DATA_DIR, "daemon.log")
NOTES_FILE  = os.path.join(DATA_DIR, "notes.log")
ALIASES_FILE= os.path.join(CONFIG_DIR, "aliases.json")


def load_aliases() -> dict:
    """
    Load config/aliases.json.
    Returns lowercase-keyed dict. Returns {} on any error.
    Reloaded on every request — edits take effect without restart.
    """
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
    """Check whether a daemon is already listening on the socket."""
    import socket as _socket
    if not os.path.exists(SOCKET_PATH):
        return False
    try:
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(SOCKET_PATH)
        return True
    except OSError:
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass
        return False
