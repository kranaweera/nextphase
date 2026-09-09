#!/usr/bin/env bash
# Builds the React dashboard and copies it into src/nextphase/server/static/,
# so `nextphase ui` has something to serve. Only needed for local/source
# installs — PyPI releases bundle this automatically (see .github/workflows/release.yml).
set -euo pipefail

cd "$(dirname "$0")/../dashboard"
npm install
npm run build

STATIC_DIR="../src/nextphase/server/static"
rm -rf "$STATIC_DIR/assets" "$STATIC_DIR/index.html"
cp -r dist/* "$STATIC_DIR/"

echo "Dashboard built into $STATIC_DIR — run 'nextphase ui' to serve it."
