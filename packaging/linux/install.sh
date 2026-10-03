#!/bin/sh
# Install Colorize for the current user: menu entry + icon pointing at this folder.
# Run from the unpacked folder: ./install.sh   (remove with ./install.sh --uninstall)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$apps/colorize.desktop" "$icons/colorize.png"
    echo "Colorize menu entry removed (the app folder itself is left alone)."
    exit 0
fi
mkdir -p "$apps" "$icons"
cp "$here/colorize.png" "$icons/colorize.png"
sed "s|@APPDIR@|$here|g" "$here/colorize.desktop" > "$apps/colorize.desktop"
chmod +x "$here/Colorize"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q "${icons%/256x256/apps}" || true
echo "Colorize installed in the application menu (runs from $here)."
