#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Execute no Ubuntu Linux ou WSL2. Não execute no PowerShell.' >&2
  exit 1
fi
python -m unittest discover -s tests -v
buildozer -v android debug
echo 'APK gerado na pasta bin/'
