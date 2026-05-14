import os
import re
import socket
import threading
import time

from ..adb.executor import run
from ..config import adb_target
from ..constants import (
    DEVICE_INFO_EMPTY_TEXT,
    DEVICE_INFO_LINE_PATTERN,
    DEVICE_INFO_TTL_SECONDS,
    FILE_EXPLORER_TIMEOUT,
)
from ..processes import clean_command_output

DEVICE_INFO_CACHE = {
    "target": "",
    "timestamp": 0.0,
    "text": "",
}
DEVICE_INFO_LOCK = threading.Lock()

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def detect_usb_iface():
    try:
        names = sorted(os.listdir("/sys/class/net"))
    except OSError:
        return None
    for name in names:
        if name.startswith("enx"):
            return name
    return None



def adb_state_from_devices(devices_output, target):
    for line in devices_output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == target:
            return parts[1]
    return ""


def tcp_port_open(host, port, timeout=0.4):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def configure_ip_commands(config):
    return [
        ["sudo", "ip", "addr", "replace", config["host_cidr"], "dev", config["iface"]],
        ["sudo", "ip", "link", "set", config["iface"], "up"],
    ]


def adb_connect_commands(config):
    return [
        ["adb", "connect", adb_target(config)],
        ["adb", "devices"],
    ]


def ensure_adb_device(config):
    target = adb_target(config)
    code, output = run(["adb", "devices"], timeout=2, purpose="file-explorer-state")
    if code != 0:
        return "", output or "Không chạy được adb devices."
    return adb_state_from_devices(output, target), output


def first_nonempty_line(text):
    for line in str(text or "").splitlines():
        value = line.strip().strip("\x00")
        if value:
            return value
    return ""


def parse_shell_sections(output):
    sections = {}
    current = ""
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip("\r")
        if line.startswith("__") and line.endswith("__") and len(line) > 4:
            current = line[2:-2]
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def parse_device_version_line(text):
    match = DEVICE_INFO_LINE_PATTERN.search(str(text or ""))
    if not match:
        return {}
    model, app, hw, sw_version, platform = [part.strip() for part in match.groups()]
    return {
        "model_app": f"{model}[{app}]" if app else model,
        "hw": hw,
        "sw_version": sw_version,
        "platform": platform,
    }


def build_device_info_text(sections):
    runtime_info = parse_device_version_line(sections.get("PLATFORM_LOG", ""))

    sw_file_version = first_nonempty_line(sections.get("VRS_SW", ""))

    def value(text):
        text = str(text or "").strip()
        return text if text else "--"

    return (
        f"Model: {value(runtime_info.get('model_app'))}   |   "
        f"HW: {value(runtime_info.get('hw'))}   |   "
        f"SW Ver: {value(runtime_info.get('sw_version') or sw_file_version)}   |   "
        f"PLATFORM: {value(runtime_info.get('platform'))}"
    )


def collect_device_info_text(config):
    target = adb_target(config)
    now = time.time()
    with DEVICE_INFO_LOCK:
        if (
            DEVICE_INFO_CACHE["target"] == target
            and DEVICE_INFO_CACHE["text"]
            and now - DEVICE_INFO_CACHE["timestamp"] < DEVICE_INFO_TTL_SECONDS
        ):
            return DEVICE_INFO_CACHE["text"]

    shell_command = """
printf '__VRS_SW__\\n'
cat /ydvrs/bin/ver/sw_ver.txt 2>/dev/null || cat /mnt/data/share/hu/ver/sw_ver.txt 2>/dev/null
printf '__PLATFORM_LOG__\\n'
for f in $(ls -t /mnt/data/logs/dvrs_* 2>/dev/null | head -n 8); do
    line=$(grep -a 'PLATFORM' "$f" 2>/dev/null | tail -n 1)
    if [ -n "$line" ]; then
        echo "$line"
        break
    fi
done
"""
    code, output = run(
        ["adb", "-s", target, "shell", shell_command],
        timeout=8,
        purpose="status-device-info",
    )
    if code != 0:
        text = DEVICE_INFO_EMPTY_TEXT
    else:
        sections = parse_shell_sections(clean_command_output(output))
        text = build_device_info_text(sections)

    with DEVICE_INFO_LOCK:
        DEVICE_INFO_CACHE.update(
            {
                "target": target,
                "timestamp": now,
                "text": text,
            }
        )
    return text


def adb_shell(config, shell_command, timeout=FILE_EXPLORER_TIMEOUT, purpose="file-explorer"):
    return run(
        ["adb", "-s", adb_target(config), "shell", shell_command],
        timeout=timeout,
        purpose=purpose,
    )



def is_root_id_output(output):
    return bool(re.search(r"\buid=0(?:\(|\b)", output or ""))

def ensure_adb_root_device(config, purpose="root-check"):
    target = adb_target(config)
    state, devices_output = ensure_adb_device(config)
    if state != "device":
        return (
            False,
            (
                f"ADB chưa sẵn sàng cho {target}. State: {state or 'not connected'}\n"
                f"{devices_output}"
            ).strip(),
        )

    code, output = run(["adb", "-s", target, "shell", "id"], timeout=3, purpose=purpose)
    output = clean_command_output(output)
    if code != 0:
        return False, f"Không kiểm tra được root bằng adb shell id.\n{output}".strip()
    if not is_root_id_output(output):
        return False, f"ADB đã connect nhưng chưa có root.\nid output: {output}".strip()
    return True, output or "uid=0(root)"


def wait_for_adb_device(config, wait_seconds=10.0, log=None, purpose="adb-wait"):
    target = adb_target(config)
    deadline = time.monotonic() + wait_seconds
    last_state = ""
    last_devices = ""

    while time.monotonic() < deadline:
        code, devices = run(["adb", "devices"], timeout=2, purpose=f"{purpose}-state")
        last_devices = clean_command_output(devices)
        state = adb_state_from_devices(devices, target) if code == 0 else ""
        if state != last_state and log:
            log(f"ADB state: {state or 'chưa thấy thiết bị'}")
        last_state = state
        if state == "device":
            return state, last_devices

        if state == "offline":
            run(["adb", "disconnect", target], timeout=2, purpose=f"{purpose}-disconnect")
        run(["adb", "connect", target], timeout=4, purpose=f"{purpose}-connect")
        time.sleep(1.0)

    return last_state, last_devices
