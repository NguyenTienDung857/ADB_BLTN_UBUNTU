import argparse
import os
import platform
import time
import traceback

from .config import adb_target, load_config, save_config
from .processes import clean_command_output
from .services import connection
from .services.adb_device import adb_shell, ensure_adb_device
from .services.files import list_remote_dir


def timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def report_path(custom_path=""):
    if custom_path:
        return custom_path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "reports", f"windows-device-validation-{timestamp()}.txt")


def emit(lines, message=""):
    print(message)
    lines.append(str(message))


def emit_section(lines, title):
    emit(lines, "")
    emit(lines, f"===== {title} =====")


def run_validation(report_file=""):
    config = load_config()
    save_config(config)
    target = adb_target(config)
    lines = []

    emit(lines, "Adapter Status Windows device validation")
    emit(lines, f"OS: {platform.platform()}")
    emit(lines, f"CWD: {os.getcwd()}")
    emit(lines, f"ADB target: {target}")
    emit(lines, f"Interface: {config.get('iface')}")
    emit(lines, f"Host IP: {config.get('host_cidr')}")
    emit(lines, f"Device IP: {config.get('device_ip')}")
    emit(lines, f"ADB port: {config.get('adb_port')}")

    ok = True
    try:
        emit_section(lines, "Configure IP")
        message = connection.configure_ip(config)
        emit(lines, message)

        emit_section(lines, "ADB reconnect")
        message = connection.adb_reconnect(config)
        emit(lines, message)

        emit_section(lines, "ADB state")
        state, devices_output = ensure_adb_device(config)
        emit(lines, f"state={state or 'not connected'}")
        emit(lines, clean_command_output(devices_output))
        if state != "device":
            ok = False

        if state == "device":
            emit_section(lines, "adb shell id")
            code, output = adb_shell(config, "id", timeout=5, purpose="windows-validate-id")
            emit(lines, f"exit={code}")
            emit(lines, clean_command_output(output))
            if code != 0:
                ok = False

            emit_section(lines, "File Explorer root list")
            result = list_remote_dir(config, "/")
            emit(lines, f"ok={result.get('ok')}")
            emit(lines, f"path={result.get('path')}")
            emit(lines, f"entries={len(result.get('entries', []))}")
            if result.get("message"):
                emit(lines, clean_command_output(result.get("message")))
            if not result.get("ok"):
                ok = False

            emit_section(lines, "App status snapshot")
            status = connection.collect_status(config)
            for key in ("banner_text", "adb_ok", "adb_state", "root_ok", "target"):
                emit(lines, f"{key}: {status.get(key)}")
            emit(lines, status.get("details", ""))
    except Exception:
        ok = False
        emit_section(lines, "Unhandled error")
        emit(lines, traceback.format_exc())

    emit_section(lines, "Result")
    emit(lines, "PASS" if ok else "FAIL")

    path = report_path(report_file)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")
    emit(lines, f"Report saved: {path}")
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate Adapter Status on a real Windows BLTN setup")
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)
    return run_validation(args.report)


if __name__ == "__main__":
    raise SystemExit(main())
