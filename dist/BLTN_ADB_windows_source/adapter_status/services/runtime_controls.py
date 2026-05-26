import json
import os
import re
import shlex
import time

from ..adb.executor import run_with_delayed_pty_input
from ..config import adb_target
from ..constants import CMDTOOL_CONTROL_TIMEOUT, RUNTIME_STATE_CACHE_FILE, SERVICE_CONTROL_TIMEOUT
from ..processes import clean_command_output, command_text
from .adb_device import adb_shell, ensure_adb_device, ensure_adb_root_device, parse_shell_sections


CMDTOOL_FEATURES = {
    "logging": {
        "label": "Logging tổng",
        "description": "Điều khiển cmdtool log on/off.",
        "command": "log",
    },
    "gsensor": {
        "label": "G-sensor logging",
        "description": "Điều khiển cmdtool log gsensor on/off.",
        "command": "log gsensor",
    },
    "mcu": {
        "label": "MCU logging",
        "description": "Điều khiển cmdtool log mcu on/off.",
        "command": "log mcu",
    },
}

SERVICE_CONTROLS = {
    "dlt": {
        "label": "DLT",
        "description": "Bật/tắt DLT runtime logging.",
        "service": "dlt",
        "unit": "dlt.service",
        "processes": ("dlt-daemon",),
    },
    "dlt-system": {
        "label": "DLT System",
        "description": "Bật/tắt DLT system runtime logging.",
        "service": "dlt-system",
        "unit": "dlt-system.service",
        "processes": ("dlt-system",),
    },
    "wifi": {
        "label": "WiFi",
        "description": "Bật/tắt WiFi AP runtime service.",
        "service": "wifi",
        "unit": "wifi.service",
        "processes": ("hostapd", "udhcpd"),
        "pid_files": ("/var/run/hostapd/uap0.pid", "/var/run/udhcpd/udhcpd.pid"),
        "interface": "uap0",
        "start_command": "/ydvrs/bin/hostapd-start",
        "stop_command": "/ydvrs/bin/hostapd-stop",
    },
}

LOG_LEVELS = tuple(range(1, 7))
RUNTIME_QUERY_COMMANDS = (
    "state show",
    "state gsensor info",
    "state mcu info",
)
STATE_UNKNOWN = "unknown"
STATE_ON = "on"
STATE_OFF = "off"
SERVICE_UNKNOWN = "unknown"
SERVICE_ACTIVE = "active"
SERVICE_INACTIVE = "inactive"


def runtime_result(ok, title, command="", message="", code=0):
    cleaned = clean_command_output(message)
    if not cleaned:
        cleaned = "OK" if ok else "Không có output từ lệnh."
    return {
        "ok": bool(ok),
        "title": title,
        "command": command,
        "message": cleaned,
        "code": int(code or 0),
        "timestamp": time.strftime("%H:%M:%S"),
    }


def snapshot_item(label, state=STATE_UNKNOWN, source="", raw="", confidence="unknown"):
    return {
        "label": label,
        "state": state,
        "source": source,
        "raw": raw,
        "confidence": confidence,
    }


def empty_runtime_snapshot():
    return {
        "features": {
            feature_id: snapshot_item(feature["label"])
            for feature_id, feature in CMDTOOL_FEATURES.items()
        },
        "log_level": snapshot_item("Log level"),
        "services": {
            service_id: snapshot_item(service["label"], state=SERVICE_UNKNOWN)
            for service_id, service in SERVICE_CONTROLS.items()
        },
        "raw": {},
        "summary": "Chưa có snapshot runtime.",
        "timestamp": time.strftime("%H:%M:%S"),
    }


def adb_device_error_result(config, title):
    target = adb_target(config)
    state, devices_output = ensure_adb_device(config)
    if state == "device":
        return None
    message = (
        f"ADB chưa sẵn sàng cho {target}. State: {state or 'not connected'}\n"
        f"{devices_output}"
    )
    return runtime_result(False, title, "adb devices", message, code=1)


def cleanup_cmdtool_session(config):
    adb_shell(
        config,
        "pkill -9 cmdtool 2>/dev/null || true",
        timeout=5,
        purpose="dashboard-cmdtool-cleanup",
    )


def load_runtime_cache():
    try:
        with open(RUNTIME_STATE_CACHE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_runtime_cache(cache):
    temp_path = f"{RUNTIME_STATE_CACHE_FILE}.{os.getpid()}.tmp"
    try:
        os.makedirs(os.path.dirname(RUNTIME_STATE_CACHE_FILE), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, indent=2, sort_keys=True)
        os.replace(temp_path, RUNTIME_STATE_CACHE_FILE)
    except OSError:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def update_runtime_cache(section, key, state):
    cache = load_runtime_cache()
    values = cache.setdefault(section, {})
    values[key] = {
        "state": str(state),
        "updated_at": time.time(),
        "updated_label": time.strftime("%H:%M:%S"),
    }
    save_runtime_cache(cache)


def run_cmdtool_command(config, cmdtool_command, title, timeout=CMDTOOL_CONTROL_TIMEOUT):
    precheck = adb_device_error_result(config, title)
    if precheck:
        return precheck

    cleanup_cmdtool_session(config)
    target = adb_target(config)
    command = ["adb", "-s", target, "shell", "-tt", "cmdtool"]
    try:
        code, output = run_with_delayed_pty_input(
            command,
            f"{cmdtool_command}\n",
            prompt_text="VRS>",
            completion_texts=("command status",),
            timeout=timeout,
            purpose="dashboard-cmdtool",
        )
        output = clean_command_output(output)
    finally:
        cleanup_cmdtool_session(config)
    output_lower = output.lower()
    if "command status" in output_lower:
        ok = "command status = 0" in output_lower
    else:
        ok = code == 0
    display = f"{command_text(command)} << {cmdtool_command}"
    return runtime_result(ok, title, display, output, code=code)


def with_fresh_snapshot(config, result):
    snapshot_result = collect_runtime_status(config)
    result["snapshot"] = snapshot_result.get("snapshot")
    if snapshot_result.get("message"):
        result["message"] = (
            f"{result.get('message', '')}\n\n"
            "----- Trạng thái sau lệnh -----\n"
            f"{snapshot_result['message']}"
        ).strip()
    return result


def set_cmdtool_feature(config, feature_id, enabled):
    feature = CMDTOOL_FEATURES.get(feature_id)
    if not feature:
        return runtime_result(False, "Feature không hợp lệ", feature_id, "Không có feature này.", code=1)

    state = "on" if enabled else "off"
    cmdtool_command = f"{feature['command']} {state}"
    title = f"{feature['label']}: {'Bật' if enabled else 'Tắt'}"
    result = run_cmdtool_command(config, cmdtool_command, title)
    if result.get("ok"):
        update_runtime_cache("features", feature_id, state)
    return with_fresh_snapshot(config, result)


def set_log_level(config, level):
    try:
        value = int(level)
    except (TypeError, ValueError):
        return runtime_result(False, "Log level không hợp lệ", str(level), "Level phải từ 1 đến 6.", code=1)

    if value not in LOG_LEVELS:
        return runtime_result(False, "Log level không hợp lệ", str(value), "Level phải từ 1 đến 6.", code=1)

    result = run_cmdtool_command(config, f"log level {value}", f"Log level: {value}")
    if result.get("ok"):
        update_runtime_cache("log_level", "value", str(value))
    return with_fresh_snapshot(config, result)


def service_control_shell_command(service, action):
    service_name = service["service"]
    unit_name = service.get("unit") or service_name
    fallback_command = service.get("start_command" if action == "start" else "stop_command")
    quoted_service = shlex.quote(service_name)
    quoted_unit = shlex.quote(unit_name)
    quoted_action = shlex.quote(action)
    fallback_block = ""
    if fallback_command:
        quoted_fallback = shlex.quote(fallback_command)
        fallback_block = f"""
if [ -x {quoted_fallback} ]; then
    echo "fallback: {quoted_fallback}"
    {quoted_fallback} 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then
        exit 0
    fi
    echo "fallback rc=$rc"
fi
"""
    return f"""
service_name={quoted_service}
service_unit={quoted_unit}
service_action={quoted_action}
echo "Service: $service_name"
echo "Unit: $service_unit"
echo "Action: $service_action"

if command -v systemctl >/dev/null 2>&1; then
    systemctl "$service_action" "$service_unit" 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then
        exit 0
    fi
    echo "systemctl rc=$rc, thử fallback service/init.d"
fi

if command -v service >/dev/null 2>&1; then
    service "$service_name" "$service_action" 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then
        exit 0
    fi
    echo "service rc=$rc, thử fallback init.d"
fi

if [ -x "/etc/init.d/$service_name" ]; then
    "/etc/init.d/$service_name" "$service_action" 2>&1
    exit $?
fi

{fallback_block}

echo "Không tìm thấy systemctl/service/init.d cho $service_name"
exit 127
"""


def desired_service_state(enabled):
    return SERVICE_ACTIVE if enabled else SERVICE_INACTIVE


def service_state_matches(item, enabled):
    return item and item.get("state") == desired_service_state(enabled)


def collect_single_service_item(config, service_id):
    code, output, services = collect_service_snapshot(config)
    service = SERVICE_CONTROLS.get(service_id, {"label": service_id})
    return code, output, services.get(service_id, snapshot_item(service["label"], state=SERVICE_UNKNOWN))


def set_service_feature(config, service_id, enabled):
    service = SERVICE_CONTROLS.get(service_id)
    if not service:
        return runtime_result(False, "Service không hợp lệ", service_id, "Không có service này.", code=1)

    action = "start" if enabled else "stop"
    state_text_label = "Bật" if enabled else "Tắt"
    title = f"{service['label']}: {state_text_label}"
    precheck = adb_device_error_result(config, title)
    if precheck:
        return precheck

    service_name = service["service"]
    current_code, current_output, current_item = collect_single_service_item(config, service_id)
    if current_code == 0 and service_state_matches(current_item, enabled):
        message = (
            f"{service['label']} đã ở trạng thái {state_text(current_item.get('state')).lower()}.\n"
            f"Nguồn trạng thái: {current_item.get('source') or '--'}"
        )
        return with_fresh_snapshot(
            config,
            runtime_result(True, title, f"status {service_name}", message, code=0),
        )

    root_ok, root_message = ensure_adb_root_device(config, purpose=f"dashboard-service-{service_name}-root-check")
    if not root_ok:
        message = (
            f"Không đổi được {service['label']}: ADB hiện tại chưa có root.\n"
            f"{root_message}\n"
            f"Trạng thái hiện tại: {snapshot_state_text(current_item)} "
            f"({current_item.get('source') or current_output or '--'}).\n"
            "Hãy chạy Get Root trước nếu cần bật/tắt service runtime trên ECU."
        )
        return with_fresh_snapshot(
            config,
            runtime_result(False, title, f"service {service_name} {'on' if enabled else 'off'}", message, code=1),
        )

    command = service_control_shell_command(service, action)
    code, output = adb_shell(
        config,
        command,
        timeout=SERVICE_CONTROL_TIMEOUT,
        purpose=f"dashboard-service-{service_name}-{action}",
    )
    time.sleep(0.5)
    verify_code, verify_output, verify_item = collect_single_service_item(config, service_id)
    verified = verify_code == 0 and service_state_matches(verify_item, enabled)
    message = clean_command_output(output)
    if code != 0:
        message = f"{message}\nLệnh service lỗi ({code}).".strip()
    message = (
        f"{message}\n\n"
        "----- Verify sau lệnh -----\n"
        f"{service['label']}: {snapshot_state_text(verify_item)} "
        f"({verify_item.get('source') or verify_output or '--'})"
    ).strip()
    if not verified:
        expected = "bật" if enabled else "tắt"
        message = f"{message}\nService chưa chuyển sang trạng thái {expected} sau lệnh.".strip()

    return with_fresh_snapshot(
        config,
        runtime_result(
            verified,
            title,
            f"service {service_name} {'on' if enabled else 'off'}",
            message,
            code=0 if verified else (code or 1),
        ),
    )


def parse_on_off_from_text(text, token_groups):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for tokens in token_groups:
        wanted = tuple(token.lower() for token in tokens)
        for line in lines:
            line_lower = line.lower()
            if not all(token in line_lower for token in wanted):
                continue
            negative = re.search(r"\b(off|false|disabled|disable|inactive|stopped|not running)\b", line_lower)
            positive = re.search(r"\b(on|true|enabled|enable|active|running)\b", line_lower)
            if negative:
                return STATE_OFF, line
            if positive:
                return STATE_ON, line
    return STATE_UNKNOWN, ""


def parse_log_level(text):
    for line in str(text or "").splitlines():
        line_lower = line.lower()
        if "log" not in line_lower and "level" not in line_lower:
            continue
        for pattern in (
            r"\blog\s*level\s*[:=\[]?\s*([1-6])\b",
            r"\blevel\s*[:=\[]?\s*([1-6])\b",
        ):
            match = re.search(pattern, line_lower)
            if match:
                return match.group(1), line.strip()
    return STATE_UNKNOWN, ""


def service_status_block(service_id, service):
    service_name = service["service"]
    unit_name = service.get("unit") or service_name
    processes = " ".join(shlex.quote(process) for process in service.get("processes", ()))
    pid_files = " ".join(shlex.quote(path) for path in service.get("pid_files", ()))
    interface = service.get("interface", "")
    return f"""
svc_id={shlex.quote(service_id)}
svc_name={shlex.quote(service_name)}
svc_unit={shlex.quote(unit_name)}
svc_processes="{processes}"
svc_pid_files="{pid_files}"
svc_iface={shlex.quote(interface)}
active="systemctl-not-found"
enabled="systemctl-not-found"
active_rc=127
enabled_rc=127
pids=""
pid_files=""
iface_state=""

if command -v systemctl >/dev/null 2>&1; then
    active=$(systemctl is-active "$svc_unit" 2>&1)
    active_rc=$?
    enabled=$(systemctl is-enabled "$svc_unit" 2>&1)
    enabled_rc=$?
fi

if command -v pidof >/dev/null 2>&1; then
    for proc in $svc_processes; do
        found=$(pidof "$proc" 2>/dev/null || true)
        if [ -n "$found" ]; then
            pids="${{pids}}${{proc}}:${{found}},"
        fi
    done
fi

for pid_file in $svc_pid_files; do
    if [ -s "$pid_file" ]; then
        pid=$(cat "$pid_file" 2>/dev/null || true)
        pid_files="${{pid_files}}${{pid_file}}:${{pid}},"
    fi
done

if [ -n "$svc_iface" ]; then
    iface_state=$(ifconfig "$svc_iface" 2>/dev/null | sed -n '1p' || true)
fi

printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$svc_id" "$active" "$enabled" "$active_rc" "$enabled_rc" "$pids" "$pid_files" "$iface_state" "$svc_name"
"""


def service_status_shell_command():
    blocks = ["printf '__SERVICES__\\n'"]
    for service_id, service in SERVICE_CONTROLS.items():
        blocks.append(service_status_block(service_id, service))
    return "\n".join(blocks)


def normalize_service_state(service_id, active, pids, _iface_state):
    active = str(active or "").strip().lower()
    pids = str(pids or "").strip()
    if service_id == "wifi":
        return SERVICE_ACTIVE if pids else SERVICE_INACTIVE
    if active == "active" or pids:
        return SERVICE_ACTIVE
    if active in {"inactive", "failed", "dead", "deactivating"}:
        return SERVICE_INACTIVE
    if service_id in SERVICE_CONTROLS and not pids:
        return SERVICE_INACTIVE
    return SERVICE_UNKNOWN


def collect_service_snapshot(config):
    code, output = adb_shell(
        config,
        service_status_shell_command(),
        timeout=SERVICE_CONTROL_TIMEOUT,
        purpose="dashboard-runtime-service-status",
    )
    output = clean_command_output(output)
    sections = parse_shell_sections(output)
    service_lines = sections.get("SERVICES", output)
    snapshot = {
        service_id: snapshot_item(service["label"], state=SERVICE_UNKNOWN)
        for service_id, service in SERVICE_CONTROLS.items()
    }
    for line in service_lines.splitlines():
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        service_id, active, enabled, active_rc, enabled_rc, pids, pid_files, iface_state, service_name = [
            part.strip() for part in parts[:9]
        ]
        service = SERVICE_CONTROLS.get(service_id)
        if not service:
            continue
        state = normalize_service_state(service_id, active, pids, iface_state)
        sources = [
            f"systemctl={active or 'unknown'}(rc={active_rc or 'unknown'})",
            f"enabled={enabled or 'unknown'}(rc={enabled_rc or 'unknown'})",
            f"pids={pids or 'none'}",
        ]
        if pid_files:
            sources.append(f"pid_files={pid_files}")
        if iface_state:
            sources.append(f"iface={iface_state}")
        snapshot[service_id] = snapshot_item(
            service["label"],
            state=state,
            source=", ".join(sources),
            raw=line,
            confidence="actual",
        )
    return code, output, snapshot


def collect_cmdtool_raw(config):
    raw = {}
    for command in RUNTIME_QUERY_COMMANDS:
        result = run_cmdtool_command(
            config,
            command,
            f"Query {command}",
            timeout=CMDTOOL_CONTROL_TIMEOUT,
        )
        raw[command] = result.get("message", "")
    return raw


def build_feature_snapshot(raw):
    combined = "\n".join(raw.get(command, "") for command in RUNTIME_QUERY_COMMANDS)
    feature_tokens = {
        "logging": (
            ("log", "enable"),
            ("log", "state"),
            ("logging",),
            ("journal", "log"),
            ("console", "log"),
            ("file", "log"),
        ),
        "gsensor": (
            ("log", "gsensor"),
            ("gsensor", "log"),
            ("evsenstm",),
            ("sensor", "log"),
        ),
        "mcu": (
            ("log", "mcu"),
            ("mcu", "log"),
        ),
    }

    snapshot = {}
    for feature_id, feature in CMDTOOL_FEATURES.items():
        state, source = parse_on_off_from_text(combined, feature_tokens.get(feature_id, ()))
        snapshot[feature_id] = snapshot_item(
            feature["label"],
            state=state,
            source=source or "Không parse được từ cmdtool state.",
            raw=source,
            confidence="actual" if state != STATE_UNKNOWN else "unknown",
        )

    level, source = parse_log_level(combined)
    level_snapshot = snapshot_item(
        "Log level",
        state=level,
        source=source or "Không parse được từ cmdtool state.",
        raw=source,
        confidence="actual" if level != STATE_UNKNOWN else "unknown",
    )
    return snapshot, level_snapshot


def apply_cached_cmdtool_states(snapshot):
    cache = load_runtime_cache()
    for feature_id, cached in cache.get("features", {}).items():
        item = snapshot["features"].get(feature_id)
        if not item or item.get("state") != STATE_UNKNOWN:
            continue
        state = str(cached.get("state") or STATE_UNKNOWN)
        if state not in {STATE_ON, STATE_OFF}:
            continue
        item.update(
            {
                "state": state,
                "source": (
                    "Local last-known từ lệnh Dashboard lúc "
                    f"{cached.get('updated_label', '--')}; ECU chưa trả field xác nhận."
                ),
                "confidence": "local",
            }
        )

    cached_level = cache.get("log_level", {}).get("value", {})
    if snapshot["log_level"].get("state") == STATE_UNKNOWN and isinstance(cached_level, dict):
        value = str(cached_level.get("state") or "")
        if value in {str(level) for level in LOG_LEVELS}:
            snapshot["log_level"].update(
                {
                    "state": value,
                    "source": (
                        "Local last-known từ lệnh Dashboard lúc "
                        f"{cached_level.get('updated_label', '--')}; ECU chưa trả field xác nhận."
                    ),
                    "confidence": "local",
                }
            )


def state_text(state):
    if state == STATE_ON:
        return "Bật"
    if state == STATE_OFF:
        return "Tắt"
    if state == SERVICE_ACTIVE:
        return "Bật"
    if state == SERVICE_INACTIVE:
        return "Tắt"
    return "unknown"


def snapshot_state_text(item):
    state = item.get("state")
    if item.get("confidence") == "local":
        if state == STATE_ON:
            return "Đã gửi bật, chưa xác nhận"
        if state == STATE_OFF:
            return "Đã gửi tắt, chưa xác nhận"
        if str(state) in {str(level) for level in LOG_LEVELS}:
            return f"Level {state}, chưa xác nhận"
    if str(state) in {str(level) for level in LOG_LEVELS}:
        return f"Level {state}"
    return state_text(state)


def build_snapshot_summary(snapshot):
    lines = [f"Snapshot lúc {snapshot['timestamp']}"]
    lines.append("Logging:")
    for feature in snapshot["features"].values():
        lines.append(f"- {feature['label']}: {snapshot_state_text(feature)} ({feature['source']})")
    lines.append(
        f"- Log level: {snapshot_state_text(snapshot['log_level'])} "
        f"({snapshot['log_level']['source']})"
    )
    lines.append("Services:")
    for service in snapshot["services"].values():
        lines.append(f"- {service['label']}: {snapshot_state_text(service)} ({service['source']})")
    return "\n".join(lines)


def collect_runtime_status(config):
    title = "Kiểm tra trạng thái runtime ECU"
    precheck = adb_device_error_result(config, title)
    if precheck:
        snapshot = empty_runtime_snapshot()
        precheck["snapshot"] = snapshot
        return precheck

    snapshot = empty_runtime_snapshot()
    raw = collect_cmdtool_raw(config)
    features, log_level = build_feature_snapshot(raw)
    service_code, service_output, services = collect_service_snapshot(config)
    snapshot.update(
        {
            "features": features,
            "log_level": log_level,
            "services": services,
            "raw": {
                **raw,
                "services": service_output,
            },
            "timestamp": time.strftime("%H:%M:%S"),
        }
    )
    apply_cached_cmdtool_states(snapshot)
    snapshot["summary"] = build_snapshot_summary(snapshot)

    result = runtime_result(
        service_code == 0,
        title,
        "runtime status snapshot",
        snapshot["summary"],
        code=service_code,
    )
    result["snapshot"] = snapshot
    return result
