#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Execute no Ubuntu Linux ou WSL2. Não execute no PowerShell.' >&2
  exit 1
fi
python -m unittest discover -s tests -v
if [[ ! -d .p4a ]]; then
  git clone --depth 1 --branch v2026.05.09 https://github.com/kivy/python-for-android .p4a
fi
python tools/prepare_p4a.py .p4a
buildozer -v android debug
echo 'APK gerado na pasta bin/'
