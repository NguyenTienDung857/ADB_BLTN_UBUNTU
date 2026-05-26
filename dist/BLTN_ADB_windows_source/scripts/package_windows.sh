#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p dist

python3 -B -c "import glob, os, py_compile; files=['adapter-status-ui']+glob.glob('adapter_status/*.py')+glob.glob('adapter_status/adb/*.py')+glob.glob('adapter_status/services/*.py')+glob.glob('adapter_status/ui/*.py'); os.makedirs('/tmp/bltn-pycompile', exist_ok=True); [py_compile.compile(path, cfile=f'/tmp/bltn-pycompile/{index}.pyc', doraise=True) for index, path in enumerate(files)]; print(f'compiled {len(files)} files')"
python3 -B -m adapter_status.windows_preflight --static-only
bash -n docs/adb.sh docs/adbscript_linux.sh

ZIP_PATH="dist/BLTN_ADB_windows_source.zip"
rm -f "$ZIP_PATH"
zip -r "$ZIP_PATH" \
  adapter-status-ui \
  adapter_status \
  docs \
  ecu-files \
  tools \
  scripts \
  run_windows.cmd \
  bootstrap_windows.cmd \
  check_windows_runtime.cmd \
  smoke_windows.cmd \
  validate_windows_with_device.cmd \
  requirements-windows.txt \
  AGENTS.md \
  -x '*/__pycache__/*' '*.pyc' '.test-home/*' 'dist/*'

python3 -B scripts/verify_windows_package.py "$ZIP_PATH"
zip -T "$ZIP_PATH"
du -h "$ZIP_PATH"
