"""
monrela/script_manager.py
Script manager window — create, edit, delete .monrela scripts.
Opened via MANAGE_SCRIPTS verb from the palette.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPlainTextEdit,
    QLineEdit, QPushButton, QLabel, QFrame,
    QMessageBox, QSplitter,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from config import SCRIPTS_DIR


# Minimal stylesheet matching Monrela's palette aesthetic
QSS = """
QWidget {
    background-color: #0e1117;
    color: #e8eaf0;
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 13px;
}
QFrame#sidebar {
    background-color: #161b24;
    border-right: 1px solid #252d3d;
}
QLabel#panel-title {
    color: #00d4aa;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 2px;
    padding: 10px 14px 6px 14px;
}
QListWidget {
    background-color: #161b24;
    border: none;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 4px;
    color: #e8eaf0;
}
QListWidget::item:selected {
    background-color: #00d4aa;
    color: #0e1117;
}
QListWidget::item:hover:!selected {
    background-color: #252d3d;
}
QPlainTextEdit {
    background-color: #161b24;
    border: 1px solid #252d3d;
    border-radius: 4px;
    color: #e8eaf0;
    font-family: "JetBrains Mono","Ubuntu Mono","Consolas",monospace;
    font-size: 13px;
    padding: 10px;
    selection-background-color: #00d4aa;
    selection-color: #0e1117;
}
QPlainTextEdit:focus {
    border-color: #00d4aa;
}
QLineEdit {
    background-color: #1c2333;
    border: 1px solid #252d3d;
    border-radius: 4px;
    color: #e8eaf0;
    padding: 7px 10px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #00d4aa;
}
QPushButton {
    background-color: #00d4aa;
    color: #0e1117;
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover { background-color: #00a882; }
QPushButton:pressed { background-color: #008f6e; }
QPushButton#btn-danger {
    background-color: #252d3d;
    color: #ff5c5c;
    border: 1px solid #ff5c5c;
}
QPushButton#btn-danger:hover { background-color: #ff5c5c; color: #0e1117; }
QPushButton#btn-secondary {
    background-color: #252d3d;
    color: #e8eaf0;
    border: 1px solid #252d3d;
}
QPushButton#btn-secondary:hover { background-color: #2d3748; }
QSplitter::handle { background-color: #252d3d; width: 1px; }
"""


class ScriptManagerWindow(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = None   # path of script being edited
        self._setup_window()
        self._build_ui()
        self.setStyleSheet(QSS)
        self._load_scripts()

    # ── Window ────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("Monrela — Script Manager")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(900, 580)
        self.setMinimumSize(700, 450)
        # Centre on screen
        screen = self.screen().availableGeometry()
        self.move(
            (screen.width()  - 900) // 2,
            (screen.height() - 580) // 2,
        )

    # ── UI ────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        # ── Left sidebar: script list ─────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        scripts_label = QLabel("SCRIPTS")
        scripts_label.setObjectName("panel-title")
        sl.addWidget(scripts_label)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_script_selected)
        sl.addWidget(self._list)

        # New script button at bottom of sidebar
        new_btn = QPushButton("+ New Script")
        new_btn.setObjectName("btn-secondary")
        new_btn.setFixedHeight(38)
        new_btn.clicked.connect(self._on_new)
        sl.addWidget(new_btn)

        splitter.addWidget(sidebar)

        # ── Right: editor area ────────────────
        editor_widget = QWidget()
        el = QVBoxLayout(editor_widget)
        el.setContentsMargins(16, 14, 16, 14)
        el.setSpacing(10)

        # Script name field
        name_row = QHBoxLayout()
        name_label = QLabel("Script name:")
        name_label.setFixedWidth(100)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. syscheck  (no spaces, no extension)")
        name_row.addWidget(name_label)
        name_row.addWidget(self._name_input)
        el.addLayout(name_row)

        # Editor
        editor_label = QLabel("EDITOR")
        editor_label.setObjectName("panel-title")
        editor_label.setContentsMargins(0, 0, 0, 0)
        el.addWidget(editor_label)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText(
            "# Write your script here\n"
            "# Each line is one Monrela instruction\n"
            "# Lines starting with # are comments\n\n"
            "IF internet_up THEN NOTE \"Online\"\n"
            "RUN_SCRIPT syscheck\n"
        )
        self._editor.setFont(QFont("JetBrains Mono, Ubuntu Mono, Consolas", 13))
        el.addWidget(self._editor)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._save_btn = QPushButton("Save Script")
        self._save_btn.clicked.connect(self._on_save)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("btn-danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("btn-secondary")
        self._clear_btn.clicked.connect(self._on_clear)

        btn_row.addWidget(self._save_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._clear_btn)
        btn_row.addWidget(self._delete_btn)
        el.addLayout(btn_row)

        splitter.addWidget(editor_widget)
        splitter.setSizes([220, 680])

        root.addWidget(splitter)

    # ── Load scripts from disk ────────────────

    def _load_scripts(self):
        self._list.clear()
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        try:
            files = sorted(f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".monrela"))
            for f in files:
                name = f.replace(".monrela", "")
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, os.path.join(SCRIPTS_DIR, f))
                self._list.addItem(item)
        except OSError:
            pass

    # ── Script selected from list ─────────────

    def _on_script_selected(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._editor.setPlainText(content)
            self._name_input.setText(name)
            self._current_file = path
            self._delete_btn.setEnabled(True)
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Could not read script:\n{e}")

    # ── New script ────────────────────────────

    def _on_new(self):
        self._editor.clear()
        self._name_input.clear()
        self._name_input.setFocus()
        self._current_file = None
        self._delete_btn.setEnabled(False)
        self._list.clearSelection()

    # ── Save script ───────────────────────────

    def _on_save(self):
        name    = self._name_input.text().strip()
        content = self._editor.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Name required", "Please enter a script name.")
            self._name_input.setFocus()
            return
        if not content:
            QMessageBox.warning(self, "Content required", "Script cannot be empty.")
            self._editor.setFocus()
            return

        # Sanitise name — no spaces, no extension, no path separators
        name = name.replace(" ", "_").replace("/", "").replace("\\", "")
        name = name.replace(".monrela", "")

        path = os.path.join(SCRIPTS_DIR, name + ".monrela")

        # Warn if overwriting a different script than currently loaded
        if (os.path.exists(path) and
                self._current_file and
                os.path.abspath(path) != os.path.abspath(self._current_file)):
            reply = QMessageBox.question(
                self, "Overwrite?",
                f"A script named '{name}' already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            os.makedirs(SCRIPTS_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            self._current_file = path
            self._delete_btn.setEnabled(True)
            self._load_scripts()
            # Re-select saved item
            for i in range(self._list.count()):
                if self._list.item(i).text() == name:
                    self._list.setCurrentRow(i)
                    break
        except OSError as e:
            QMessageBox.warning(self, "Save failed", f"Could not save script:\n{e}")

    # ── Delete script ─────────────────────────

    def _on_delete(self):
        if not self._current_file:
            return
        name = os.path.basename(self._current_file).replace(".monrela", "")
        reply = QMessageBox.question(
            self, "Delete script",
            f"Delete '{name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            os.unlink(self._current_file)
            self._on_clear()
            self._load_scripts()
        except OSError as e:
            QMessageBox.warning(self, "Delete failed", f"Could not delete script:\n{e}")

    # ── Clear editor ──────────────────────────

    def _on_clear(self):
        self._editor.clear()
        self._name_input.clear()
        self._current_file = None
        self._delete_btn.setEnabled(False)
        self._list.clearSelection()