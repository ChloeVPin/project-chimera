#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS_DIR="$ROOT_DIR/docs"

echo "================================================================================"
echo " Project Chimera - GitHub Pages Site Exporter"
echo " Prepares static visualization portal and research artifacts for GitHub Pages"
echo "================================================================================"

echo "[1/4] Initializing export directory at: $DOCS_DIR"
rm -rf "$DOCS_DIR"
mkdir -p "$DOCS_DIR"
mkdir -p "$DOCS_DIR/data"
mkdir -p "$DOCS_DIR/reports"
mkdir -p "$DOCS_DIR/paper"

echo "[2/4] Copying visualizer frontend and data bundles..."
cp "$ROOT_DIR/visualizer/index.html" "$DOCS_DIR/index.html"
cp "$ROOT_DIR/visualizer/data_bundle.js" "$DOCS_DIR/data_bundle.js"

echo "[3/4] Packaging research assets and PDF monograph..."
if [ -f "$ROOT_DIR/paper/project_chimera_monograph.pdf" ]; then
  cp "$ROOT_DIR/paper/project_chimera_monograph.pdf" "$DOCS_DIR/paper/project_chimera_monograph.pdf"
  echo "  -> Bundled PDF Monograph ($(du -h "$DOCS_DIR/paper/project_chimera_monograph.pdf" | cut -f1))"
fi

cp "$ROOT_DIR/data/"*.json "$DOCS_DIR/data/"
cp "$ROOT_DIR/reports/"*.md "$DOCS_DIR/reports/"

echo "[4/4] Creating .nojekyll for zero-config GitHub Pages..."
touch "$DOCS_DIR/.nojekyll"

cat << 'EOF' > "$DOCS_DIR/CNAME.example"
# Optional: Set your custom domain here:
# chimera.yourdomain.org
EOF

TOTAL_FILES=$(find "$DOCS_DIR" -type f | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$DOCS_DIR" | cut -f1)

echo "================================================================================"
echo " Export Complete! $TOTAL_FILES files packaged ($TOTAL_SIZE) in ./docs"
echo " GitHub Pages configuration: Set Source to Deploy from a branch -> /docs folder"
echo "================================================================================"
