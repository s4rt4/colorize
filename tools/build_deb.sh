#!/bin/sh
# Build dist/Colorize-<version>-linux-<arch>.deb from the PyInstaller build in
# dist/Colorize. Run tools/build.py first, then this script.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
version=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$here/colorize/__init__.py")
arch=$(dpkg --print-architecture)
case $arch in
    amd64) file_arch=x86_64 ;;
    arm64) file_arch=aarch64 ;;
    *) file_arch=$arch ;;
esac
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/DEBIAN" "$stage/opt/colorize" "$stage/usr/share/applications" \
         "$stage/usr/share/icons/hicolor/256x256/apps" "$stage/usr/bin"
cp -a "$here/dist/Colorize/." "$stage/opt/colorize/"
rm "$stage/opt/colorize/colorize.desktop" "$stage/opt/colorize/colorize.png" "$stage/opt/colorize/install.sh"
ln -s /opt/colorize/Colorize "$stage/usr/bin/colorize"
sed "s|@APPDIR@|/opt/colorize|g" "$here/packaging/linux/colorize.desktop" > "$stage/usr/share/applications/colorize.desktop"
cp "$here/packaging/linux/colorize.png" "$stage/usr/share/icons/hicolor/256x256/apps/"
size=$(du -sk "$stage/opt/colorize" | cut -f1)
cat > "$stage/DEBIAN/control" <<EOF
Package: colorize
Version: $version
Architecture: $arch
Maintainer: Sarta <surat.sarta@gmail.com>
Installed-Size: $size
Depends: libegl1, libgl1, libxkbcommon-x11-0, libxcb-cursor0, libdbus-1-3
Recommends: ghostscript
Suggests: xdg-desktop-portal
Section: graphics
Priority: optional
Homepage: https://github.com/s4rt4/colorize
Description: Offline color manager
 Pick, check and export color palettes: sample the screen, extract palettes
 from images, check contrast (WCAG) and color blindness, convert between
 RGB/OKLCH/CMYK and export to common swatch formats.
 This package ships a standalone build; no Python runtime is required.
 On Wayland, Sample Screen Color uses xdg-desktop-portal.
EOF
dpkg-deb --build --root-owner-group "$stage" "$here/dist/Colorize-$version-linux-$file_arch.deb"
echo "Built dist/Colorize-$version-linux-$file_arch.deb"
