#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

OUT_BIN="$SCRIPT_DIR/litmus_test_x86"
SRC_FILE="$SCRIPT_DIR/litmus_test.c"
DATA_OUT="${1:-$ROOT_DIR/data/phase17_rosetta_results.json}"
ITERATIONS="${2:-2000000}"

echo "================================================================================"
echo " Project Chimera - Phase 17: Rosetta 2 TSO Hardware Bit Probe"
echo " Target Architecture: x86_64 via Rosetta 2 (Apple ACTLR_EL1 Hardware TSO)"
echo "================================================================================"

echo "[1/2] Compiling litmus test targeting x86_64-apple-macos11..."
clang -O2 -target x86_64-apple-macos11 -lpthread "$SRC_FILE" -o "$OUT_BIN"
codesign -s - "$OUT_BIN" >/dev/null 2>&1 || true
echo "  -> Compiled & Signed: $OUT_BIN"

echo "[2/2] Executing $ITERATIONS iterations under Rosetta 2 (arch -x86_64)..."
arch -x86_64 "$OUT_BIN" "$ITERATIONS" "$DATA_OUT"

echo "================================================================================"
echo " Phase 17 Complete. Results saved to $DATA_OUT"
echo "================================================================================"
