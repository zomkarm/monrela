"""
monrela/palette.py
Frameless command palette window.
Sends instruction to daemon via Unix socket, shows result, auto-hides.
Imports only: config (shared constants), PyQt6.
"""

import os
import sys
import json
import socket as _socket

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QFrame, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

from config import SOCKET_PATH, BUFFER_SIZE, ENCODING

# ── Palette ───────────────────────────────────────────────────────────────────
# Colour palette
C_BG      = "#0e1117"
C_SURFACE = "#161b24"
C_INPUT   = "#1c2333"
C_ACCENT  = "#00d4aa"
C_DIMACCENT="#00a882"
C_TEXT    = "#e8eaf0"
C_MUTED   = "#6b7892"
C_ERROR   = "#ff5c5c"
C_BORDER  = "#252d3d"

QSS = f"""
QWidget#root {{
    background: {C_BG};
    border: 1px solid {C_BORDER};
}}
QFrame#accent-bar {{
    background: {C_ACCENT};
    min-height: 2px;
    max-height: 2px;
    border: none;
}}
QFrame#header {{
    background: {C_BG};
    border-bottom: 1px solid {C_BORDER};
}}
QLabel#lbl-title {{
    color: {C_ACCENT};
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 3px;
    padding: 0px 14px;
}}
QLabel#lbl-version {{
    color: {C_MUTED};
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 10px;
    padding: 0px 14px;
}}
QLineEdit#monrela-input {{
    background: {C_INPUT};
    border: none;
    border-bottom: 1px solid {C_BORDER};
    border-radius: 0px;
    color: {C_TEXT};
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 15px;
    padding: 14px 18px;
    selection-background-color: {C_ACCENT};
    selection-color: {C_BG};
}}
QLineEdit#monrela-input:focus {{
    border-bottom: 1px solid {C_ACCENT};
    background: {C_SURFACE};
}}
QFrame#result-frame {{
    background: {C_SURFACE};
    border-top: 1px solid {C_BORDER};
}}
QLabel#result-msg {{
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 13px;
    font-weight: bold;
    padding: 10px 18px 4px 18px;
}}
QLabel#result-detail {{
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 11px;
    color: {C_MUTED};
    padding: 0px 18px 10px 18px;
}}
QFrame#footer {{
    background: {C_BG};
    border-top: 1px solid {C_BORDER};
}}
QLabel#lbl-hint {{
    color: {C_MUTED};
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 10px;
    letter-spacing: 0.5px;
    padding: 5px 14px;
}}
"""

# Verb hints shown in footer as user types
VERB_HINTS = {
    "OPEN":       ("OPEN <app>",                  C_ACCENT),
    "CLOSE":      ("CLOSE <app>",                 C_ERROR),
    "BROWSE":     ("BROWSE <url>",                "#5c9eff"),
    "SEARCH":     ('SEARCH [engine] "query"',     "#a78bfa"),
    "GOTO":       ("GOTO <path>",                 "#fbbf24"),
    "FIND":       ("FIND <filename>",             "#34d399"),
    "NOTE":       ('NOTE "text"',                 "#fb923c"),
    "RUN":        ("RUN <shell command>",         C_MUTED),
    "RUN_SCRIPT": ("RUN_SCRIPT <script name>",    C_ACCENT),
}

DEFAULT_HINT = "OPEN  CLOSE  BROWSE  SEARCH  GOTO  FIND  NOTE  RUN  RUN_SCRIPT"


class MonrelaPalette(QWidget):

    # Emitted when palette is fully closed — main.py connects this to cleanup
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._build_window()
        self._build_ui()
        self.setStyleSheet(QSS)

    # ── Window ────────────────────────────────

    def _build_window(self):
        self.setObjectName("root")
        self.setWindowTitle("Monrela")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setFixedWidth(680)

    def _centre(self):
        geo = self.screen().availableGeometry()
        self.move(
            (geo.width() - self.width()) // 2,
            int(geo.height() * 0.30),
        )

    # ── UI ────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 2px teal accent bar at top
        bar = QFrame(); bar.setObjectName("accent-bar"); bar.setFixedHeight(2)
        root.addWidget(bar)

        # Header: MONRELA label + version
        header = QFrame(); header.setObjectName("header")
        hl = QHBoxLayout(header); hl.setContentsMargins(0, 6, 0, 6)
        lbl = QLabel("MONRELA"); lbl.setObjectName("lbl-title")
        ver = QLabel("v1.0"); ver.setObjectName("lbl-version")
        ver.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(lbl); hl.addStretch(); hl.addWidget(ver)
        root.addWidget(header)

        # Input
        self._input = QLineEdit()
        self._input.setObjectName("monrela-input")
        self._input.setPlaceholderText("Enter instruction…   e.g.  OPEN browser")
        self._input.returnPressed.connect(self._submit)
        self._input.textChanged.connect(self._update_hint)
        root.addWidget(self._input)

        # Result area (hidden initially)
        self._result_frame = QFrame(); self._result_frame.setObjectName("result-frame")
        rl = QVBoxLayout(self._result_frame); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)
        self._result_msg    = QLabel(); self._result_msg.setObjectName("result-msg"); self._result_msg.setWordWrap(True)
        self._result_detail = QLabel(); self._result_detail.setObjectName("result-detail"); self._result_detail.setWordWrap(True)
        self._result_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rl.addWidget(self._result_msg)
        rl.addWidget(self._result_detail)
        self._result_frame.hide()
        root.addWidget(self._result_frame)

        # Footer hint bar
        footer = QFrame(); footer.setObjectName("footer")
        fl = QHBoxLayout(footer); fl.setContentsMargins(0,0,0,0)
        self._hint = QLabel(DEFAULT_HINT); self._hint.setObjectName("lbl-hint")
        esc = QLabel("ESC to close"); esc.setObjectName("lbl-hint")
        esc.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        fl.addWidget(self._hint); fl.addWidget(esc)
        root.addWidget(footer)

        # Auto-close timer
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset_and_hide)

    # ── Hint ──────────────────────────────────

    def _update_hint(self, text: str):
        verb = text.strip().upper().split()[0] if text.strip() else ""
        if verb in VERB_HINTS:
            hint_text, color = VERB_HINTS[verb]
            self._hint.setText(hint_text)
            self._hint.setStyleSheet(
                f"color: {color}; font-family: 'JetBrains Mono','Ubuntu Mono','Consolas',monospace;"
                f"font-size: 10px; padding: 5px 14px;"
            )
        else:
            self._hint.setText(DEFAULT_HINT)
            self._hint.setStyleSheet("")

    # ── Submit ────────────────────────────────

    def _submit(self):
        instruction = self._input.text().strip()
        if not instruction:
            return
        result = self._send(instruction)
        self._show_result(result)
        self._timer.start(4000 if result.get("ok") else 6000)

    def _send(self, instruction: str) -> dict:
        """Send instruction to daemon, return result dict."""
        try:
            with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
                s.settimeout(5.0)
                s.connect(SOCKET_PATH)
                s.sendall(json.dumps({"instruction": instruction}).encode(ENCODING))
                s.shutdown(_socket.SHUT_WR)
                chunks = []
                while True:
                    chunk = s.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return json.loads(b"".join(chunks).decode(ENCODING))
        except FileNotFoundError:
            return {"ok": False, "message": "Daemon not running", "detail": "Run: monrela --daemon"}
        except ConnectionRefusedError:
            return {"ok": False, "message": "Cannot connect to daemon", "detail": "Run: monrela --daemon"}
        except _socket.timeout:
            return {"ok": False, "message": "Daemon did not respond", "detail": ""}
        except Exception as e:
            return {"ok": False, "message": "Connection error", "detail": str(e)}

    # ── Result display ────────────────────────

    def _show_result(self, result: dict):
        ok      = result.get("ok", False)
        message = result.get("message", "")
        detail  = result.get("detail", "")

        prefix = "✓" if ok else "✗"
        color  = C_ACCENT if ok else C_ERROR
        self._result_msg.setText(f"{prefix}  {message}")
        self._result_msg.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold; padding: 10px 18px 4px 18px;")

        if detail:
            self._result_detail.setText(detail)
            self._result_detail.show()
        else:
            self._result_detail.hide()

        self._result_frame.show()
        self.adjustSize()

    # ── Reset / hide ──────────────────────────

    def _reset_and_hide(self):
        self._input.clear()
        self._result_frame.hide()
        self._result_msg.setText("")
        self._result_detail.setText("")
        self._hint.setText(DEFAULT_HINT)
        self._hint.setStyleSheet("")
        self.adjustSize()
        self.hide()
        self.closed.emit()   # tell main.py we're done — triggers lock file cleanup

    # ── Public: open palette ──────────────────

    def show_palette(self):
        self._reset_and_hide()
        self._centre()
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    # ── Keyboard ──────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._timer.stop()
            self._reset_and_hide()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        QTimer.singleShot(150, lambda: self.hide() if not self.isActiveWindow() else None)
        super().focusOutEvent(event)
