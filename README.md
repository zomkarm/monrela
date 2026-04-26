# Monrela

A lightweight, offline command palette for Linux.
Type a pseudocode instruction, get it done — from anywhere on your desktop.

---

## What it is

Press a hotkey → a small dark palette appears → type one instruction → done.

No natural language guessing. No AI. No cloud. No subscriptions.
A fixed vocabulary of verbs that map directly to system actions, plus a scripting
system for multi-step automation.

```
OPEN browser
BROWSE claude.ai
SEARCH youtube "lofi music"
GOTO ~/projects
FIND budget.pdf
RUN docker ps
NOTE "fix nginx config tomorrow"
RUN_SCRIPT syscheck
```

---

## How it works

Monrela runs as two processes:

**Daemon** — a persistent background process that starts at login and stays alive.
It holds a Unix socket open, waiting for instructions. Because it never stops,
there is no cold-start delay when you open the palette.

**Palette** — a frameless window that appears on your hotkey. You type an
instruction, it sends it to the daemon over the socket, shows the result,
then closes. The palette process exits completely after each use.

---

## Installation

```bash
chmod +x install.sh
./install.sh
```

The installer checks Python, installs dependencies, copies files to
`~/.local/share/monrela/`, creates a launcher at `~/.local/bin/monrela`,
adds a desktop entry, and sets up the daemon to auto-start at login.

**Uninstall:**
```bash
./install.sh --uninstall
```

---

## Running

```bash
monrela              # open the palette (auto-starts daemon if needed)
monrela --daemon     # start the daemon manually
monrela --stop       # stop the daemon
monrela --status     # check if daemon is running
```

**Keyboard shortcut (recommended):**

Settings → Keyboard → Custom Shortcuts → +
- Name: `Monrela`
- Command: `/home/YOUR_USERNAME/.local/bin/monrela`
- Key: `Ctrl+Alt+Space`

---

## Verbs

| Verb | Usage | What it does |
|---|---|---|
| `OPEN` | `OPEN browser` | Launch an application |
| `CLOSE` | `CLOSE firefox` | Terminate a running app |
| `BROWSE` | `BROWSE claude.ai` | Open URL in default browser |
| `SEARCH` | `SEARCH youtube "lofi"` | Web search via browser |
| `GOTO` | `GOTO ~/projects` | Open folder in file manager |
| `FIND` | `FIND budget.pdf` | Search for a file by name |
| `NOTE` | `NOTE "fix nginx tomorrow"` | Save a timestamped note |
| `RUN` | `RUN docker ps` | Run a shell command, show output |
| `RUN_SCRIPT` | `RUN_SCRIPT syscheck` | Run a saved script |

**SEARCH engines:** `google` (default) · `youtube` · `github` · `ddg` · `wikipedia`

---

## App aliases

Edit `config/aliases.json` to map friendly names to actual commands.
Changes take effect immediately — no daemon restart needed.

```json
{
  "browser":      "firefox",
  "editor":       "code",
  "terminal":     "gnome-terminal",
  "file manager": "nautilus"
}
```

---

## Scripting

Scripts are plain text files saved in the `scripts/` folder with a `.monrela` extension.
Each line is one instruction. Lines starting with `#` are comments.

**Run a script:**
```
RUN_SCRIPT syscheck
```

**Script syntax:**

```bash
# Variables
SET name = value
NOTE "Hello $name"

# Conditionals
IF internet_up THEN NOTE "online"
IF disk_usage > 80 THEN NOTIFY "Disk full" ELSE NOTE "Disk ok"

# Wait
WAIT 3

# Repeat
REPEAT 5 NOTE "hello"

# Try with fallback
TRY OPEN firefox FALLBACK NOTIFY "Firefox not found"

# Desktop notification
NOTIFY "Title" "Optional message body"
```

**Available conditions:**

| Condition | Form | Example |
|---|---|---|
| `disk_usage` | numeric | `disk_usage > 80` |
| `memory_usage` | numeric | `memory_usage > 85` |
| `cpu_usage` | numeric | `cpu_usage > 90` |
| `battery` | numeric | `battery < 20` |
| `internet_up` | boolean | `internet_up` |
| `internet_down` | boolean | `internet_down` |
| `app_running` | bool+arg | `app_running firefox` |
| `file_exists` | bool+arg | `file_exists ~/report.pdf` |
| `dir_exists` | bool+arg | `dir_exists ~/projects` |
| `time_is` | bool+arg | `time_is 09:00` |
| `day_is` | bool+arg | `day_is monday` |

---

## Included scripts

| Script | What it does |
|---|---|
| `syscheck` | Full system health check — disk, memory, CPU, network |
| `netcheck` | Network diagnostics — connectivity and interface info |
| `resources` | Snapshot of CPU, memory, disk and top processes |
| `ports` | Show what is listening on common development ports |
| `monrela_test` | Sanity test for the scripting engine |

---

## Data locations

| Data | Location |
|---|---|
| Quick notes | `~/.local/share/monrela/notes.log` |
| Daemon log | `~/.local/share/monrela/daemon.log` |
| Scripts | `~/.local/share/monrela/scripts/` |
| Aliases | `~/.local/share/monrela/config/aliases.json` |

---

## Project structure

```
monrela/
├── main.py          ← entry point
├── daemon.py        ← socket server, parser, executor
├── palette.py       ← PyQt6 frameless palette window
├── actions.py       ← all 9 verb implementations
├── scripting.py     ← script engine: IF, SET, REPEAT, WAIT, TRY
├── conditions.py    ← system state checks used by scripting
├── config.py        ← shared constants and paths
├── install.sh       ← install and uninstall
├── requirements.txt
├── assets/
│   └── icon.png
├── config/
│   └── aliases.json
└── scripts/
    ├── syscheck.monrela
    ├── netcheck.monrela
    ├── resources.monrela
    ├── ports.monrela
    └── monrela_test.monrela
```

---

## Adding a new verb

1. Add a class to `actions.py` with a `run(args, aliases)` method
2. Register it in `REGISTRY` at the bottom of `actions.py`
3. Done — no other file needs changing

## Adding a new condition

1. Add a function to `conditions.py`
2. Register it in `CONDITION_REGISTRY` with its kind (`numeric`, `boolean`, or `bool_arg`)
3. Done — scripting engine picks it up automatically

---

## Requirements

- Python 3.10+
- PyQt6
- pyperclip

---

## License

MIT