"""
monrela/actions.py
All action classes in one file.
Each class handles one verb. Add a new class + register it in REGISTRY.

Result dataclass is defined here too — no base module needed.
"""

import os
import subprocess
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote_plus

from config import SCRIPTS_DIR, NOTES_FILE, DATA_DIR


# ── Result ────────────────────────────────────

@dataclass
class Result:
    ok:      bool
    message: str
    detail:  str = ""


# ── Helpers ───────────────────────────────────

def _launch(cmd: list) -> None:
    """Launch a process detached from the daemon."""
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _resolve(name: str, aliases: dict) -> str:
    """Resolve app name through aliases, fallback to name itself."""
    return aliases.get(name.lower()) or name


# ── OPEN ──────────────────────────────────────

class OpenAction:
    """OPEN <app>  — launch an application."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, "Usage: OPEN <app name>")

        name    = " ".join(args).lower().strip()
        command = _resolve(name, aliases) or args[0]

        try:
            _launch([command])
            return Result(True, f"Opening {name}")
        except FileNotFoundError:
            return Result(
                False,
                f"App not found: {command}",
                "Check aliases.json or verify the app is installed."
            )
        except Exception as e:
            return Result(False, f"Failed: {command}", str(e))


# ── CLOSE ─────────────────────────────────────

class CloseAction:
    """CLOSE <app>  — terminate a running application."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, "Usage: CLOSE <app name>")

        name    = " ".join(args).lower().strip()
        command = _resolve(name, aliases) or args[0]

        # Try exact match first, then partial
        for flag in ["-x", "-f"]:
            r = subprocess.run(["pkill", flag, command], capture_output=True)
            if r.returncode == 0:
                return Result(True, f"Closed {name}")

        return Result(False, f"No running process found: {command}")


# ── BROWSE ────────────────────────────────────

class BrowseAction:
    """BROWSE <url>  — open URL in default browser."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, "Usage: BROWSE <url>")

        url = args[0].strip()

        if not re.match(r"^https?://", url):
            prefix = "http://" if (url.startswith("localhost") or re.match(r"^\d+\.\d+", url)) else "https://"
            url = prefix + url

        try:
            _launch(["xdg-open", url])
            return Result(True, f"Opening {url}")
        except Exception as e:
            return Result(False, "Failed to open browser", str(e))


# ── SEARCH ────────────────────────────────────

SEARCH_ENGINES = {
    "google":    "https://www.google.com/search?q={}",
    "youtube":   "https://www.youtube.com/results?search_query={}",
    "github":    "https://github.com/search?q={}",
    "ddg":       "https://duckduckgo.com/?q={}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
    "wiki":      "https://en.wikipedia.org/w/index.php?search={}",
}

class SearchAction:
    """SEARCH [engine] <query>  — web search via browser."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, 'Usage: SEARCH [engine] "query"')

        if args[0].lower() in SEARCH_ENGINES and len(args) > 1:
            engine = args[0].lower()
            query  = " ".join(args[1:]).strip('"\'')
        else:
            engine = "google"
            query  = " ".join(args).strip('"\'')

        if not query:
            return Result(False, "No search query provided.")

        url = SEARCH_ENGINES[engine].format(quote_plus(query))
        try:
            _launch(["xdg-open", url])
            return Result(True, f"Searching {engine}: {query}")
        except Exception as e:
            return Result(False, "Failed to open browser", str(e))


# ── GOTO ──────────────────────────────────────

class GotoAction:
    """GOTO <path>  — open folder in file manager."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, "Usage: GOTO <path>")

        raw  = " ".join(args).strip().strip('"\'')
        path = os.path.expandvars(os.path.expanduser(raw))

        if not os.path.exists(path):
            return Result(False, f"Path not found: {path}")
        if not os.path.isdir(path):
            return Result(False, f"Not a directory: {path}")

        try:
            _launch(["xdg-open", path])
            return Result(True, f"Opening {path}")
        except Exception as e:
            return Result(False, "Failed to open file manager", str(e))


# ── FIND ──────────────────────────────────────

class FindAction:
    """FIND <name>  — search for a file by name."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, "Usage: FIND <filename>")

        pattern = " ".join(args).strip().strip('"\'')

        # Use locate if available (fast), else find (slower)
        if self._has_locate():
            lines = self._locate(pattern)
        else:
            lines = self._find(pattern)

        if not lines:
            return Result(False, f"No files found: {pattern}")

        shown  = lines[:8]
        extra  = f"\n...and {len(lines)-8} more" if len(lines) > 8 else ""
        return Result(True, f"Found {len(lines)} match(es): {pattern}", "\n".join(shown) + extra)

    def _has_locate(self) -> bool:
        return subprocess.run(["which", "locate"], capture_output=True).returncode == 0

    def _locate(self, pattern: str) -> list:
        r = subprocess.run(["locate", "--basename", f"*{pattern}*"], capture_output=True, text=True, timeout=10)
        return [l for l in r.stdout.splitlines() if l.strip()]

    def _find(self, pattern: str) -> list:
        home = os.path.expanduser("~")
        r = subprocess.run(["find", home, "-iname", f"*{pattern}*", "-maxdepth", "8"], capture_output=True, text=True, timeout=15)
        return [l for l in r.stdout.splitlines() if l.strip()]


# ── NOTE ──────────────────────────────────────

class NoteAction:
    """NOTE <text>  — save a quick timestamped note."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, 'Usage: NOTE "your text"')

        text = " ".join(args).strip().strip('"\'')
        if not text:
            return Result(False, "Note text cannot be empty.")

        os.makedirs(DATA_DIR, exist_ok=True)
        ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}]  {text}\n"

        try:
            with open(NOTES_FILE, "a", encoding="utf-8") as f:
                f.write(line)
            return Result(True, "Note saved", text)
        except OSError as e:
            return Result(False, "Failed to save note", str(e))


# ── RUN ───────────────────────────────────────

# Commands blocked for safety
BLOCKED_CMDS = {"rm", "rmdir", "mkfs", "dd", "fdisk", "shred",
                "wipefs", "shutdown", "reboot", "halt", "poweroff"}

class RunAction:
    """RUN <command>  — execute a shell command and show output."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, "Usage: RUN <command>")

        command  = " ".join(args).strip()
        base_cmd = args[0].lstrip("sudo").strip().lower()

        if base_cmd in BLOCKED_CMDS:
            return Result(False, f"Blocked: {args[0]}", "Destructive commands are not permitted.")

        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
            output = r.stdout.strip() or r.stderr.strip() or "(no output)"

            lines = output.splitlines()
            if len(lines) > 20:
                output = "\n".join(lines[:20]) + f"\n...({len(lines)-20} more lines)"

            if r.returncode == 0:
                return Result(True, f"$ {command}", output)
            else:
                return Result(False, f"Exit {r.returncode}: {command}", output)

        except subprocess.TimeoutExpired:
            return Result(False, "Timed out (15s limit)")
        except Exception as e:
            return Result(False, "Execution error", str(e))


# ── RUN_SCRIPT ────────────────────────────────

class RunScriptAction:
    """RUN_SCRIPT <name>  — run a saved .monrela script."""

    def run(self, args: list, aliases: dict) -> Result:
        if not args:
            return Result(False, "Usage: RUN_SCRIPT <name>")

        name  = args[0].strip()
        paths = [
            os.path.join(SCRIPTS_DIR, name),
            os.path.join(SCRIPTS_DIR, name + ".monrela"),
        ]
        path = next((p for p in paths if os.path.isfile(p)), None)

        if not path:
            return Result(False, f"Script not found: {name}", f"Place .monrela files in: {SCRIPTS_DIR}")

        instructions = self._read(path)
        if not instructions:
            return Result(False, f"Script is empty: {name}")

        # Return instructions for daemon to execute sequentially
        # (daemon handles multi-step execution)
        return Result(True, f"__SCRIPT__", "\n".join(instructions))

    def _read(self, path: str) -> list:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return [
                    l.strip() for l in f
                    if l.strip() and not l.strip().startswith("#")
                ]
        except OSError:
            return []


class ManageScriptsAction:
    """MANAGE_SCRIPTS — open the script manager window."""

    def run(self, args: list, aliases: dict) -> Result:
        try:
            # Import here to avoid loading Qt in daemon context
            from PyQt6.QtWidgets import QApplication
            import script_manager

            app = QApplication.instance()
            if app is None:
                return Result(False, "Palette must be open to use MANAGE_SCRIPTS")

            win = script_manager.ScriptManagerWindow()
            win.show()
            win.raise_()
            win.activateWindow()
            return Result(True, "Script manager opened")
        except Exception as e:
            return Result(False, "Could not open script manager", str(e))            


# ── Registry ──────────────────────────────────

REGISTRY = {
    "OPEN":       OpenAction,
    "CLOSE":      CloseAction,
    "BROWSE":     BrowseAction,
    "SEARCH":     SearchAction,
    "GOTO":       GotoAction,
    "FIND":       FindAction,
    "NOTE":       NoteAction,
    "RUN":        RunAction,
    "RUN_SCRIPT": RunScriptAction,
    "MANAGE_SCRIPTS": ManageScriptsAction,
}

VERB_LIST = list(REGISTRY.keys())


def get_action(verb: str):
    """Return instantiated action for verb, or None."""
    cls = REGISTRY.get(verb.upper())
    return cls() if cls else None
