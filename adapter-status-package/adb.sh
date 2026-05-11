#!/usr/bin/env bash
set -u

CONFIG_FILE="${HOME}/.config/adapter-status/config.json"
PROCESS_FILE="${HOME}/.cache/adapter-status/child-processes.json"

register_tracked_process() {
  [ "${ADAPTER_STATUS_TRACK:-}" = "1" ] || return 0

  python3 - "$PROCESS_FILE" "$$" "${ADAPTER_STATUS_RUN_ID:-adb-sh}" "${ADAPTER_STATUS_OWNER_PID:-0}" <<'PY' >/dev/null 2>&1 || true
import json
import os
import sys
import time

path, pid_text, owner_run, owner_pid_text = sys.argv[1:5]

try:
    pid = int(pid_text)
except ValueError:
    sys.exit(0)

def proc_start_time(process_id):
    try:
        with open(f"/proc/{process_id}/stat", "r", encoding="utf-8") as handle:
            data = handle.read()
    except OSError:
        return None
    marker = data.rfind(")")
    if marker < 0:
        return None
    fields = data[marker + 2 :].split()
    if len(fields) <= 19:
        return None
    return fields[19]

def record_alive(record):
    try:
        record_pid = int(record.get("pid", 0))
    except (TypeError, ValueError):
        return False
    start_time = record.get("start_time")
    return record_pid > 1 and start_time and proc_start_time(record_pid) == str(start_time)

start_time = proc_start_time(pid)
if not start_time:
    sys.exit(0)

try:
    pgid = os.getpgid(pid)
except OSError:
    pgid = pid

try:
    owner_pid = int(owner_pid_text)
except ValueError:
    owner_pid = os.getppid()

try:
    with open(path, "r", encoding="utf-8") as handle:
        records = json.load(handle)
except (OSError, json.JSONDecodeError):
    records = []

if not isinstance(records, list):
    records = []

records = [item for item in records if record_alive(item)]
record = {
    "pid": pid,
    "pgid": pgid,
    "start_time": start_time,
    "command": "bash ./adb.sh",
    "purpose": "terminal-adb.sh",
    "owner_pid": owner_pid,
    "owner_run": owner_run,
    "created_at": time.time(),
}

if not any(item.get("pid") == pid and item.get("start_time") == start_time for item in records):
    records.append(record)

os.makedirs(os.path.dirname(path), exist_ok=True)
temp_path = f"{path}.{os.getpid()}.tmp"
with open(temp_path, "w", encoding="utf-8") as handle:
    json.dump(records, handle, indent=2, sort_keys=True)
os.replace(temp_path, path)
PY
}

register_tracked_process

read_config() {
  python3 - "$CONFIG_FILE" <<'PY'
import json
import os
import re
import sys

config = {
    "iface": "enx1c860b2bbfcf",
    "host_cidr": "192.168.244.10/24",
    "device_ip": "192.168.244.1",
    "adb_port": "4321",
}

iface_pattern = re.compile(r"^[A-Za-z0-9_.-]{1,15}$")
usb_iface_pattern = re.compile(r"enx[0-9A-Fa-f]{12}")

def sanitize_iface(value):
    text = str(value or "").strip()
    if iface_pattern.fullmatch(text):
        return text
    match = usb_iface_pattern.search(text)
    if match:
        return match.group(0)
    return config["iface"]

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as handle:
        saved = json.load(handle)
    for key in config:
        value = saved.get(key)
        if isinstance(value, str) and value.strip():
            config[key] = sanitize_iface(value) if key == "iface" else value.strip()
except (OSError, json.JSONDecodeError):
    pass

print(config["iface"])
print(config["host_cidr"])
print(config["device_ip"])
print(config["adb_port"])
PY
}

mapfile -t CONFIG < <(read_config)
IFACE="${CONFIG[0]}"
HOST_CIDR="${CONFIG[1]}"
DEVICE_IP="${CONFIG[2]}"
ADB_PORT="${CONFIG[3]}"

ADB_VENDOR_KEYS="$(find "${HOME}/.android" -maxdepth 2 -type f -name adbkey | sort | paste -sd: -)"
export ADB_VENDOR_KEYS

if ! ip link show "$IFACE" >/dev/null 2>&1; then
  DETECTED_IFACE="$(ip -o link show | awk -F': ' '$2 ~ /^enx/ { sub(/@.*/, "", $2); print $2; exit }')"
  if [ -n "$DETECTED_IFACE" ]; then
    echo "Configured interface '$IFACE' not found. Using detected interface '$DETECTED_IFACE'."
    IFACE="$DETECTED_IFACE"
  else
    echo "No USB Ethernet interface found. Available interfaces:"
    ip -br link
    exit 1
  fi
fi

TARGET="${DEVICE_IP}:${ADB_PORT}"

echo "Interface: $IFACE"
echo "Host IP:   $HOST_CIDR"
echo "ADB:       $TARGET"

sudo ip addr replace "$HOST_CIDR" dev "$IFACE"
sudo ip link set "$IFACE" up

if [ -z "$ADB_VENDOR_KEYS" ]; then
  echo "No ADB keys found in ${HOME}/.android"
  exit 1
fi

adb connect "$TARGET" >/dev/null 2>&1 || true
DEVICE_STATE="$(adb devices | awk -v target="$TARGET" '$1 == target { print $2 }')"

if [ "$DEVICE_STATE" = "unauthorized" ] || [ "$DEVICE_STATE" = "offline" ] || [ -z "$DEVICE_STATE" ]; then
  echo "ADB state is '${DEVICE_STATE:-not connected}'. Restarting ADB server with ADB_VENDOR_KEYS."
  adb disconnect "$TARGET" >/dev/null 2>&1 || true
  adb kill-server >/dev/null 2>&1 || true
  adb start-server
  adb connect "$TARGET"
fi

adb devices
adb shell
