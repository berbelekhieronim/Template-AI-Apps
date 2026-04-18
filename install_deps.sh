#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Installing student dependencies..."

if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install -r requirements-students.txt
elif command -v python >/dev/null 2>&1; then
  python -m pip install -r requirements-students.txt
else
  echo "Python is not installed. Install Python 3 first."
  exit 1
fi

echo "Done."
