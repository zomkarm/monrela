#!/usr/bin/env python3
"""
monrela/main.py
Single entry point for Monrela.

  python3 main.py             → open palette (auto-starts daemon if needed)
  python3 main.py --daemon    → start daemon process
  python3 main.py --stop      → stop running daemon
  python3 main.py --status    → check if daemon is running
"""

import os
import sys
import json
import socket
import subprocess
import time

# Ensure monrela's own directory is always on the path
# so all flat imports (config, actions, daemon, palette) work correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SOCKET_PATH, ENCODING, daemon_running


def main():
    args = sys.argv[1:]

    if "--daemon" in args:
        _start_daemon()

    elif "--stop" in args:
        _stop_daemon()

    elif "--status" in args:
        if daemon_running():
            print("Monrela daemon is running.")
        else:
            print("Monrela daemon is not running.")

    else:
        _open_palette()


# ── Daemon ────────────────────────────────────

def _start_daemon():
    if daemon_running():
        print("Monrela daemon is already running.")
        return
    from daemon import run_daemon
    run_daemon()


def _stop_daemon():
    if not daemon_running():
        print("Monrela daemon is not running.")
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect(SOCKET_PATH)
            s.sendall(json.dumps({"instruction": "__STOP__"}).encode(ENCODING))
        print("Monrela daemon stopped.")
    except Exception as e:
        print(f"Could not stop daemon: {e}")


# ── Palette ───────────────────────────────────

def _open_palette():
    # Auto-start daemon in background if not running
    if not daemon_running():
        script = os.path.abspath(__file__)
        subprocess.Popen(
            [sys.executable, script, "--daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # Wait up to 2 seconds for daemon to be ready
        for _ in range(10):
            time.sleep(0.2)
            if daemon_running():
                break

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon

    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("Monrela")
    app.setQuitOnLastWindowClosed(True)

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    from palette import MonrelaPalette
    win = MonrelaPalette()
    win.show_palette()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
