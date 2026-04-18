#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
  python3 app4_malowanie_glosem_i_wzrokiem.py
elif command -v python >/dev/null 2>&1; then
  python app4_malowanie_glosem_i_wzrokiem.py
else
  echo "Python is not installed. Install Python 3 first."
  exit 1
fi
