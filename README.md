# Monrela

> A keyboard-driven command palette for Linux.
> Type a pseudocode instruction, get it done instantly — from anywhere on your desktop.

---

## What it does

Press a hotkey → a small dark palette appears → type one instruction → done.
No natural language guessing. No AI. No cloud. A fixed vocabulary of verbs that map directly to system actions.

```
OPEN browser
BROWSE claude.ai
SEARCH youtube "lofi music"
GOTO ~/projects
FIND budget.pdf
RUN docker ps
NOTE "fix nginx config tomorrow"
RUN_SCRIPT morning
```

---

## Project structure

```
monrela/
├── main.py            ← single entry point
├── daemon.py          ← socket server + parser + executor
├── palette.py         ← PyQt6 frameless palette window
├── actions.py         ← all action classes (one verb = one class)
├── config.py          ← shared constants + aliases loader
├── install.sh         ← install / uninstall
├── requirements.txt
├── README.md
├── assets/
│   └── icon.png
├── config/
│   └── aliases.json   ← user-editable app name mappings
└── scripts/
    └── morning.monrela  ← example .monrela script
```

---

## Verbs

| Verb | Usage | What it does |
|---|---|---|
| `OPEN` | `OPEN browser` | Launch an application |
| `CLOSE` | `CLOSE firefox` | Terminate a running app |
| `BROWSE` | `BROWSE claude.ai` | Open URL in default browser |
| `SEARCH` | `SEARCH youtube "lofi"` | Web search via browser |
| `GOTO` | `GOTO ~/projects` | Open folder in file manager |
| `FIND` | `FIND budget.pdf` | Search for a file |
| `NOTE` | `NOTE "fix nginx tomorrow"` | Save a timestamped note |
| `RUN` | `RUN docker ps` | Run a shell command, show output |
| `RUN_SCRIPT` | `RUN_SCRIPT morning` | Run a saved .monrela script |

**SEARCH engines:** `google` (default), `youtube`, `github`, `ddg`, `wikipedia`

---

## Scripts

Save multi-step routines in `scripts/` as `.monrela` files:

```bash
# scripts/morning.monrela
OPEN browser
BROWSE mail.google.com
NOTE "Morning session started"
```

Run with: `RUN_SCRIPT morning`

---

## Installation

```bash
chmod +x install.sh
./install.sh
```

## Running

```bash
monrela --daemon     # start daemon (auto-started at login after install)
monrela              # open palette (auto-starts daemon if not running)
monrela --stop       # stop daemon
monrela --status     # check daemon status
```

## Keyboard shortcut

Settings → Keyboard → Custom Shortcuts → +
- Name: `Monrela`
- Command: `/home/YOUR_USERNAME/.local/bin/monrela`
- Key: `Ctrl+Alt+Space`

## Aliases

Edit `config/aliases.json` to map friendly names → commands.
Changes take effect immediately — no daemon restart needed.

## Notes file

Quick notes are saved to: `~/.local/share/monrela/notes.log`

## Uninstall

```bash
./install.sh --uninstall
```

## License

MIT
