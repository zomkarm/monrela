"""
monrela/scripting.py
Self-contained script engine for .monrela files.

Supported syntax:
  SET name = value
  IF <condition> THEN <instruction>
  IF <condition> THEN <instruction> ELSE <instruction>
  REPEAT <n> <instruction>
  WAIT <seconds>
  TRY <instruction> FALLBACK <instruction>
  NOTIFY "message"
  <any normal verb>    ← passed through to daemon.execute

Condition forms:
  internet_up                     boolean, no arg
  app_running firefox             bool_arg
  file_exists ~/report.pdf        bool_arg
  disk_usage > 80                 numeric with operator
  memory_usage < 50               numeric with operator
  battery > 20                    numeric with operator
  time_is 09:00                   bool_arg
  day_is monday                   bool_arg

Isolated — only imports: conditions.py, config.py
daemon.execute is passed in at runtime to avoid circular imports.
"""

import os
import re
import time
import subprocess
import logging

from conditions import CONDITION_REGISTRY
from config import SCRIPTS_DIR, DATA_DIR

log = logging.getLogger("monrela.scripting")

# Valid comparison operators
OPERATORS = (">", "<", ">=", "<=", "==", "!=")


# ── Desktop notification ──────────────────────

def notify(title: str, message: str = "", urgency: str = "normal") -> None:
    """Send desktop notification via notify-send. Logs if unavailable."""
    try:
        cmd = ["notify-send", "-u", urgency, f"Monrela: {title}"]
        if message:
            cmd.append(str(message))
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        log.warning(f"[NOTIFY] {title} — {message}")
    except Exception as e:
        log.warning(f"notify failed: {e}")


# ── Variable store ────────────────────────────

class VariableStore:
    def __init__(self):
        self._v: dict[str, str] = {}

    def set(self, name: str, value: str) -> None:
        self._v[name.strip()] = value.strip()

    def get(self, name: str) -> str | None:
        return self._v.get(name.strip())

    def substitute(self, text: str) -> str:
        """Replace $varname with stored value. Unknown vars left as-is."""
        def replace(m):
            return self._v.get(m.group(1), m.group(0))
        return re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', replace, text)


# ── Condition evaluator ───────────────────────

def evaluate_condition(cond: str, variables: VariableStore) -> bool:
    """
    Evaluate a condition string. Returns True or False.
    Sends desktop notification on error.

    Handles three forms based on CONDITION_REGISTRY kind:
      "boolean"  → internet_up
      "bool_arg" → app_running firefox  /  file_exists ~/path
      "numeric"  → disk_usage > 80  /  battery < 20
    """
    cond   = variables.substitute(cond.strip())
    tokens = cond.split()

    if not tokens:
        notify("Script error", "Empty condition", "critical")
        return False

    keyword = tokens[0].lower()

    if keyword not in CONDITION_REGISTRY:
        notify("Script error", f"Unknown condition: '{keyword}'", "critical")
        return False

    fn, kind = CONDITION_REGISTRY[keyword]

    try:
        # ── Boolean no-arg: internet_up ───────
        if kind == "boolean":
            return fn()

        # ── Bool with arg: app_running firefox ─
        if kind == "bool_arg":
            if len(tokens) < 2:
                notify("Script error", f"'{keyword}' needs an argument", "critical")
                return False
            arg = " ".join(tokens[1:])
            return fn(arg)

        # ── Numeric: disk_usage > 80 ──────────
        if kind == "numeric":
            # Must have: keyword operator value
            # e.g. ["disk_usage", ">", "80"]
            if len(tokens) < 3 or tokens[1] not in OPERATORS:
                notify(
                    "Script error",
                    f"Numeric condition needs operator. e.g: {keyword} > 80",
                    "critical",
                )
                return False

            operator = tokens[1]
            try:
                threshold = float(tokens[2])
            except ValueError:
                notify("Script error", f"Expected number, got: '{tokens[2]}'", "critical")
                return False

            raw_value = fn()   # returns float
            return _compare(raw_value, operator, threshold)

    except Exception as e:
        notify("Script error", f"Condition failed: {cond} — {e}", "critical")
        log.error(f"Condition eval error '{cond}': {e}")
        return False

    return False


def _compare(value: float, operator: str, threshold: float) -> bool:
    """Apply comparison operator to two numeric values."""
    if operator == ">":  return value >  threshold
    if operator == "<":  return value <  threshold
    if operator == ">=": return value >= threshold
    if operator == "<=": return value <= threshold
    if operator == "==": return value == threshold
    if operator == "!=": return value != threshold
    return False


# ── Script file parser ────────────────────────

def parse_script(path: str) -> list[str]:
    """Read .monrela file, return executable lines (no blanks, no comments)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [
                ln.strip()
                for ln in f
                if ln.strip() and not ln.strip().startswith("#")
            ]
    except OSError as e:
        notify("Script error", f"Cannot read script: {e}", "critical")
        return []


# ── Line interpreter ──────────────────────────

def interpret_line(line: str, variables: VariableStore, executor) -> dict:
    """
    Interpret one script line after variable substitution.
    Script-only verbs (SET, IF, REPEAT, WAIT, TRY, NOTIFY) handled here.
    Everything else passed through to executor (daemon.execute).
    """
    line  = variables.substitute(line)
    upper = line.upper()

    # SET name = value
    if upper.startswith("SET "):
        return _do_set(line, variables)

    # NOTIFY "message"
    if upper.startswith("NOTIFY "):
        msg = line[7:].strip().strip('"\'')
        notify(msg)
        return _ok(f"Notified: {msg}")

    # WAIT <seconds>
    if upper.startswith("WAIT "):
        return _do_wait(line)

    # REPEAT <n> <instruction>
    if upper.startswith("REPEAT "):
        return _do_repeat(line, variables, executor)

    # TRY <instruction> FALLBACK <instruction>
    if upper.startswith("TRY "):
        return _do_try(line, variables, executor)

    # IF <condition> THEN <instruction> [ELSE <instruction>]
    if upper.startswith("IF "):
        return _do_if(line, variables, executor)

    # Passthrough — normal Monrela verb
    return executor(line)


# ── Verb handlers ─────────────────────────────

def _do_set(line: str, variables: VariableStore) -> dict:
    rest = line[4:].strip()
    if "=" not in rest:
        return _err(f"Invalid SET syntax. Use: SET name = value")
    name, _, value = rest.partition("=")
    name  = name.strip()
    value = value.strip().strip('"\'')
    if not name:
        return _err("SET requires a variable name")
    variables.set(name, value)
    return _ok(f"SET {name} = {value}")


def _do_wait(line: str) -> dict:
    parts = line.split()
    if len(parts) < 2:
        return _err("WAIT requires seconds. e.g: WAIT 3")
    try:
        seconds = float(parts[1])
        if seconds < 0 or seconds > 300:
            return _err("WAIT seconds must be between 0 and 300")
        time.sleep(seconds)
        return _ok(f"Waited {seconds}s")
    except ValueError:
        return _err(f"WAIT expects a number, got: {parts[1]}")


def _do_repeat(line: str, variables: VariableStore, executor) -> dict:
    parts = line.split(None, 2)
    if len(parts) < 3:
        return _err("Usage: REPEAT <n> <instruction>")
    try:
        n = int(parts[1])
        if n < 1 or n > 50:
            return _err("REPEAT count must be between 1 and 50")
    except ValueError:
        return _err(f"REPEAT expects integer, got: {parts[1]}")

    instruction = parts[2]
    results     = []
    all_ok      = True

    for i in range(1, n + 1):
        r = interpret_line(instruction, variables, executor)
        results.append(f"[{i}/{n}] {'✓' if r['ok'] else '✗'}  {instruction[:50]}")
        if not r["ok"]:
            all_ok = False
            notify("Script error", f"REPEAT stopped at iteration {i}: {r['message']}")
            break

    return {
        "ok":      all_ok,
        "message": f"REPEAT {n}x: {instruction[:40]}",
        "detail":  "\n".join(results),
    }


def _do_try(line: str, variables: VariableStore, executor) -> dict:
    parts = re.split(r'\bFALLBACK\b', line, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2:
        return _err("TRY requires FALLBACK. Usage: TRY <instr> FALLBACK <instr>")

    try_instr      = parts[0][4:].strip()   # strip TRY prefix
    fallback_instr = parts[1].strip()

    result = interpret_line(try_instr, variables, executor)
    if result.get("ok"):
        return result

    log.info(f"TRY failed — running FALLBACK")
    return interpret_line(fallback_instr, variables, executor)


def _do_if(line: str, variables: VariableStore, executor) -> dict:
    # Split on THEN
    parts = re.split(r'\bTHEN\b', line, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2:
        return _err("IF requires THEN. Usage: IF <condition> THEN <instruction>")

    condition_str = parts[0][3:].strip()   # strip IF prefix
    after_then    = parts[1].strip()

    # Split on optional ELSE
    else_parts = re.split(r'\bELSE\b', after_then, maxsplit=1, flags=re.IGNORECASE)
    then_instr = else_parts[0].strip()
    else_instr = else_parts[1].strip() if len(else_parts) > 1 else None

    if not condition_str:
        return _err("IF condition cannot be empty")
    if not then_instr:
        return _err("THEN instruction cannot be empty")

    result = evaluate_condition(condition_str, variables)

    if result:
        return interpret_line(then_instr, variables, executor)
    elif else_instr:
        return interpret_line(else_instr, variables, executor)
    else:
        return _ok(f"Condition false, skipped: {condition_str}")


# ── Main entry point ──────────────────────────

def run_script(name: str, executor) -> dict:
    """
    Load and run a .monrela script.
    Called by daemon.py — executor is daemon.execute.
    Returns standard result dict.
    """
    candidates = [
        os.path.join(SCRIPTS_DIR, name),
        os.path.join(SCRIPTS_DIR, name + ".monrela"),
    ]
    path = next((p for p in candidates if os.path.isfile(p)), None)

    if not path:
        msg = f"Script not found: {name}"
        notify("Script error", msg, "critical")
        return _err(msg, f"Scripts directory: {SCRIPTS_DIR}")

    lines = parse_script(path)
    if not lines:
        return _err(f"Script is empty or all comments: {name}")

    log.info(f"Running script '{name}' — {len(lines)} line(s)")

    variables = VariableStore()
    results   = []
    all_ok    = True

    for i, line in enumerate(lines, 1):
        try:
            r = interpret_line(line, variables, executor)
            results.append(f"[{i}] {'✓' if r['ok'] else '✗'}  {line[:60]}")
            if not r["ok"]:
                all_ok = False
                notify(
                    f"Script '{name}' — error at line {i}",
                    r.get("message", "Unknown error"),
                    "critical",
                )
        except Exception as e:
            all_ok = False
            results.append(f"[{i}] ✗  {line[:60]}")
            notify(f"Script '{name}' — crash at line {i}", str(e), "critical")
            log.error(f"Script '{name}' line {i} exception: {e}")

    if all_ok:
        notify(f"Script complete: {name}", f"{len(lines)} instruction(s) ran")

    return {
        "ok":      all_ok,
        "message": f"Script '{name}': {len(lines)} line(s) — {'ok' if all_ok else 'errors'}",
        "detail":  "\n".join(results),
    }


# ── Helpers ───────────────────────────────────

def _ok(message: str, detail: str = "") -> dict:
    return {"ok": True,  "message": message, "detail": detail}

def _err(message: str, detail: str = "") -> dict:
    return {"ok": False, "message": message, "detail": detail}
