#!/bin/bash
# Session Sync — build a .deb with one command: ./build-deb.sh
# Output: dist/session-sync_<version>_all.deb
set -e
cd "$(dirname "$0")"

APP="session-sync"
VERSION="$(python3 -c 'import config; print(config.APP_VERSION)')"
ARCH="all"

# Stage on a POSIX filesystem — the checkout may live on NTFS/exFAT where
# chmod is a no-op and dpkg-deb rejects the permissions.
BUILD_ROOT="$(mktemp -d /tmp/${APP}-build.XXXXXX)"
BUILD="$BUILD_ROOT/${APP}_${VERSION}_${ARCH}"
cleanup() { rm -rf "$BUILD_ROOT"; }
trap cleanup EXIT

echo "== building ${APP} ${VERSION} (.deb) =="
mkdir -p "$BUILD/DEBIAN" \
         "$BUILD/opt/$APP/assets" \
         "$BUILD/usr/bin" \
         "$BUILD/usr/share/applications" \
         "$BUILD/usr/share/icons/hicolor/scalable/apps" \
         "$BUILD/etc/xdg/autostart"

# --- application code
for f in main.py config.py markets.py calendar_api.py notifier.py ui.py updater.py; do
  install -m 0644 "$f" "$BUILD/opt/$APP/$f"
done
install -m 0644 assets/icon.svg "$BUILD/opt/$APP/assets/icon.svg"

# --- icons: scalable SVG + rendered PNGs
install -m 0644 assets/icon.svg "$BUILD/usr/share/icons/hicolor/scalable/apps/$APP.svg"
QT_QPA_PLATFORM=offscreen python3 tools/render_icons.py "$BUILD/usr/share/icons/hicolor" >/dev/null

# --- launcher + desktop entries
install -m 0755 packaging/usr/bin/session-sync "$BUILD/usr/bin/$APP"
install -m 0644 "packaging/usr/share/applications/$APP.desktop" "$BUILD/usr/share/applications/"
install -m 0644 "packaging/etc/xdg/autostart/$APP.desktop" "$BUILD/etc/xdg/autostart/"

# --- DEBIAN metadata (version substitution)
sed "s/__VERSION__/$VERSION/" packaging/DEBIAN/control > "$BUILD/DEBIAN/control"
install -m 0755 packaging/DEBIAN/postinst "$BUILD/DEBIAN/postinst"
install -m 0755 packaging/DEBIAN/postrm "$BUILD/DEBIAN/postrm"

# --- normalize permissions (umask-proof; dpkg-deb requires sane modes)
find "$BUILD" -type d -exec chmod 0755 {} +
find "$BUILD" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD/DEBIAN/postinst" "$BUILD/DEBIAN/postrm" "$BUILD/usr/bin/$APP"

# --- build
mkdir -p dist
dpkg-deb --build --root-owner-group "$BUILD" "dist/${APP}_${VERSION}_${ARCH}.deb"

echo ""
echo "built: dist/${APP}_${VERSION}_${ARCH}.deb"
echo "install: sudo apt install ./dist/${APP}_${VERSION}_${ARCH}.deb"
