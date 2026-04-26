#!/usr/bin/env bash
# ─────────────────────────────────────────────
# Monrela — installer for Linux (Ubuntu/Debian)
# Usage:
#   ./install.sh             install
#   ./install.sh --uninstall remove everything
# ─────────────────────────────────────────────

set -e

APP_NAME="monrela"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

print_header() {
  echo ""
  echo "  ╔══════════════════════════════════╗"
  echo "  ║        Monrela  v1.0               ║"
  echo "  ║   Command Palette for Linux      ║"
  echo "  ╚══════════════════════════════════╝"
  echo ""
}

# ── Uninstall ─────────────────────────────────

if [[ "$1" == "--uninstall" ]]; then
  print_header
  echo "  Uninstalling Monrela..."

  if command -v monrela &>/dev/null; then
    monrela --stop 2>/dev/null || true
    sleep 0.5
  fi

  rm -rf  "$INSTALL_DIR"
  rm -f   "$BIN_DIR/monrela"
  rm -f   "$DESKTOP_DIR/monrela.desktop"
  rm -f   "$AUTOSTART_DIR/monrela-daemon.desktop"

  echo "  [✓] Monrela removed."
  echo ""
  exit 0
fi

# ── Install ───────────────────────────────────

print_header

# Python check
if ! command -v python3 &>/dev/null; then
  echo "  [ERROR] python3 not found. Run: sudo apt install python3 python3-pip"
  exit 1
fi

PYVER=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYVER" -lt 10 ]; then
  echo "  [ERROR] Python 3.10+ required."
  exit 1
fi
echo "  [✓] Python $(python3 --version)"

# pip check
if ! command -v pip3 &>/dev/null; then
  echo "  [ERROR] pip3 not found. Run: sudo apt install python3-pip"
  exit 1
fi
echo "  [✓] pip3 found"

# Install dependencies
echo ""
echo "  Installing dependencies..."
pip3 install --user -r requirements.txt --quiet
echo "  [✓] Dependencies installed"

# Copy files
echo ""
echo "  Copying files to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp -r main.py daemon.py palette.py actions.py config.py conditions.py scripting.py script_manager.py \
      config scripts assets requirements.txt "$INSTALL_DIR/"
echo "  [✓] Files copied"

# Launcher
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/monrela" << LAUNCHER
#!/usr/bin/env bash
cd "$INSTALL_DIR"
python3 main.py "\$@"
LAUNCHER
chmod +x "$BIN_DIR/monrela"
echo "  [✓] Launcher: $BIN_DIR/monrela"

# Desktop entry
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/monrela.desktop" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Monrela
Comment=Command Palette for Linux
Exec=$BIN_DIR/monrela
Icon=$INSTALL_DIR/assets/icon.png
Terminal=false
Categories=Utility;
Keywords=command;palette;launcher;
DESKTOP
echo "  [✓] Desktop entry created"

# Autostart daemon at login
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/monrela-daemon.desktop" << AUTOSTART
[Desktop Entry]
Type=Application
Name=Monrela Daemon
Exec=$BIN_DIR/monrela --daemon
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
AUTOSTART
echo "  [✓] Daemon autostart at login"

# PATH check
echo ""
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "  [!] Add this to ~/.bashrc then run: source ~/.bashrc"
  echo ""
  echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo ""
else
  echo "  [✓] $BIN_DIR is in PATH"
fi

echo "  ────────────────────────────────────"
echo "  Done! Quick start:"
echo ""
echo "    monrela --daemon     start daemon"
echo "    monrela              open palette"
echo "    monrela --stop       stop daemon"
echo ""
echo "  Keyboard shortcut:"
echo "    Settings → Keyboard → Custom Shortcuts → +"
echo "    Command : $BIN_DIR/monrela"
echo "    Key     : Ctrl+Alt+Space"
echo ""
echo "  Uninstall: ./install.sh --uninstall"
echo ""
