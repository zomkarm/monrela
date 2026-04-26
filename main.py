#!/usr/bin/env python3
"""
monrela/main.py
Single entry point.

  monrela             → open palette (starts daemon if needed)
  monrela --daemon    → start daemon process
  monrela --stop      → stop running daemon and confirm
  monrela --status    → check if daemon is running
"""

import os
import sys
import json
import socket
import subprocess
import time

# Always resolve imports from this file's own directory
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


# ── Daemon start ──────────────────────────────

def _start_daemon():
    """Start daemon. Guard against double-start."""
    if daemon_running():
        print("Monrela daemon is already running.")
        return
    from daemon import run_daemon
    run_daemon()


# ── Daemon stop ───────────────────────────────

def _stop_daemon():
    """
    Send stop signal and WAIT until daemon is confirmed dead.
    Prints result only after confirming.
    """
    if not daemon_running():
        print("Monrela daemon is not running.")
        return

    # Send __STOP__ instruction
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect(SOCKET_PATH)
            s.sendall(json.dumps({"instruction": "__STOP__"}).encode(ENCODING))
            # Read acknowledgement
            try:
                s.recv(4096)
            except Exception:
                pass
    except Exception as e:
        print(f"Could not send stop signal: {e}")
        return

    # Wait up to 3 seconds for daemon to fully exit
    for _ in range(15):
        time.sleep(0.2)
        if not daemon_running():
            print("Monrela daemon stopped.")
            return

    print("Warning: daemon may still be running. Check with: monrela --status")


# ── Palette ───────────────────────────────────

def _open_palette():
    """
    Open the command palette.
    Enforces a single palette instance — if already open, does nothing.
    Auto-starts daemon if not running.
    """
    # ── Single instance guard ─────────────────
    # Use a lock file to prevent multiple palette processes
    lock_file = "/tmp/monrela_palette.lock"

    if os.path.exists(lock_file):
        try:
            with open(lock_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)   # check if process is alive
            # Palette already open — signal it to show itself and exit
            # Since we can't easily signal PyQt to raise, just exit cleanly
            sys.exit(0)
        except (ValueError, ProcessLookupError):
            # Lock file is stale — remove it
            try:
                os.unlink(lock_file)
            except OSError:
                pass

    # Write our PID to lock file
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass

    # ── Auto-start daemon if needed ───────────
    if not daemon_running():
        script = os.path.abspath(__file__)
        subprocess.Popen(
            [sys.executable, script, "--daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # Wait up to 2 seconds for daemon socket to appear
        for _ in range(10):
            time.sleep(0.2)
            if daemon_running():
                break

    # ── Launch Qt palette ─────────────────────
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon

    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("Monrela")
    app.setQuitOnLastWindowClosed(False)  # we control quit explicitly

    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png"
    )
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    from palette import MonrelaPalette
    win = MonrelaPalette()
    win.show_palette()

    # Exit Qt loop cleanly when palette closes
    def on_close():
        # Remove palette lock file on exit
        try:
            os.unlink(lock_file)
        except OSError:
            pass
        app.quit()

    win.closed.connect(on_close)

    ret = app.exec()

    # Final cleanup of lock file
    try:
        os.unlink(lock_file)
    except OSError:
        pass

    sys.exit(ret)


if __name__ == "__main__":
    main()
