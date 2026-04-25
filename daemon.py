"""
monrela/daemon.py
Persistent background process.
Listens on Unix socket. Parses instructions. Dispatches to actions.
Stays alive until killed — no cold start on subsequent palette opens.

Run with:  python3 main.py --daemon
"""

import os
import sys
import json
import signal
import socket
import logging

from config import (
    SOCKET_PATH, BUFFER_SIZE, ENCODING,
    DATA_DIR, LOG_FILE,
    load_aliases,
)
from actions import get_action, VERB_LIST


# ── Logging ───────────────────────────────────

os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("monrela")


# ── Parser ────────────────────────────────────

def parse_instruction(raw: str) -> tuple:
    """
    Parse 'VERB arg1 "quoted arg" arg3' into (VERB, [args]).
    Quoted strings (single or double) become single args.
    Returns ("", []) for blank input.
    """
    raw = raw.strip()
    if not raw:
        return ("", [])

    tokens     = []
    current    = []
    in_quote   = False
    quote_char = None

    for ch in raw:
        if ch in ('"', "'") and not in_quote:
            in_quote   = True
            quote_char = ch
        elif ch == quote_char and in_quote:
            in_quote = False
            tokens.append("".join(current))
            current  = []
        elif ch == " " and not in_quote:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)

    if current:
        tokens.append("".join(current))

    if not tokens:
        return ("", [])

    return (tokens[0].upper(), tokens[1:])


# ── Executor ──────────────────────────────────

def execute(raw: str) -> dict:
    """
    Parse and run one instruction string.
    Always returns {"ok": bool, "message": str, "detail": str}.
    """
    verb, args = parse_instruction(raw)

    if not verb:
        return _resp(False, "Empty instruction")

    action = get_action(verb)
    if action is None:
        return _resp(False, f"Unknown verb: {verb}", f"Available: {' '.join(VERB_LIST)}")

    aliases = load_aliases()

    try:
        result = action.run(args, aliases)

        # RUN_SCRIPT returns instructions embedded in detail for sequential exec
        if result.ok and result.message == "__SCRIPT__":
            return _run_script_lines(result.detail.splitlines())

        log.info(f"{'OK' if result.ok else 'ERR'}  {raw[:80]}")
        return _resp(result.ok, result.message, result.detail)

    except Exception as e:
        log.error(f"Action error '{raw}': {e}")
        return _resp(False, "Internal error", str(e))


def _run_script_lines(lines: list) -> dict:
    """Execute each instruction in a script sequentially."""
    results = []
    all_ok  = True
    for line in lines:
        r = execute(line)
        results.append(f"{'✓' if r['ok'] else '✗'}  {line}")
        if not r["ok"]:
            all_ok = False
    return _resp(all_ok, f"Script: {len(lines)} instruction(s) run", "\n".join(results))


def _resp(ok: bool, message: str, detail: str = "") -> dict:
    return {"ok": ok, "message": message, "detail": detail}


# ── Socket server ─────────────────────────────

class MonrelaDaemon:

    def __init__(self):
        self.running = True
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT,  self._on_signal)

    def _on_signal(self, signum, frame):
        log.info("Shutting down.")
        self.running = False
        self._remove_socket()
        sys.exit(0)

    def _remove_socket(self):
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass

    def start(self):
        self._remove_socket()

        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            srv.bind(SOCKET_PATH)
        except OSError as e:
            log.error(f"Cannot bind {SOCKET_PATH}: {e}")
            sys.exit(1)

        srv.listen(5)
        log.info(f"Monrela daemon ready — socket: {SOCKET_PATH}")
        log.info(f"Verbs: {', '.join(VERB_LIST)}")

        try:
            while self.running:
                srv.settimeout(1.0)
                try:
                    conn, _ = srv.accept()
                    self._handle(conn)
                except socket.timeout:
                    continue
        finally:
            srv.close()
            self._remove_socket()

    def _handle(self, conn: socket.socket):
        try:
            chunks = []
            conn.settimeout(5.0)
            while True:
                chunk = conn.recv(BUFFER_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)

            data        = json.loads(b"".join(chunks).decode(ENCODING))
            instruction = data.get("instruction", "").strip()

            if instruction == "__STOP__":
                log.info("Stop signal received.")
                conn.sendall(json.dumps(_resp(True, "Daemon stopped")).encode(ENCODING))
                conn.close()
                self._on_signal(None, None)
                return

            log.info(f"→ {instruction}")
            result   = execute(instruction)
            response = json.dumps(result).encode(ENCODING)
            conn.sendall(response)

        except json.JSONDecodeError:
            err = json.dumps(_resp(False, "Could not parse instruction")).encode(ENCODING)
            try:
                conn.sendall(err)
            except Exception:
                pass
        except Exception as e:
            log.error(f"Handler error: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass


def run_daemon():
    MonrelaDaemon().start()
