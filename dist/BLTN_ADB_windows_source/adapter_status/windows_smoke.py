import argparse
import os
import platform
import sys
import traceback

from . import host_platform
from .constants import DEFAULT_CONFIG


def status_line(ok, title, detail=""):
    state = "OK" if ok else "FAIL"
    line = f"[{state}] {title}"
    if detail:
        line += f" - {detail}"
    print(line)
    return bool(ok)


def check_imports(require_gtk=False):
    ok = True
    modules = (
        "adapter_status.config",
        "adapter_status.host_platform",
        "adapter_status.processes",
        "adapter_status.adb.executor",
        "adapter_status.services.connection",
        "adapter_status.services.root",
        "adapter_status.services.adb_update",
        "adapter_status.services.files",
        "adapter_status.services.runtime_controls",
        "adapter_status.services.logs",
        "adapter_status.services.video",
        "adapter_status.services.workspace",
        "adapter_status.ui.dashboard",
        "adapter_status.ui.widgets",
        "adapter_status.ui.help_text",
    )
    for module_name in modules:
        try:
            __import__(module_name)
            ok = status_line(True, f"import {module_name}") and ok
        except Exception as exc:
            ok = status_line(False, f"import {module_name}", str(exc)) and ok

    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401

        ok = status_line(True, "GTK import", "Gtk 3 OK") and ok
    except Exception as exc:
        ok = status_line(not require_gtk, "GTK import", str(exc)) and ok
    return ok


def check_windows_command_generation():
    original_is_windows = host_platform.IS_WINDOWS
    original_adapters = host_platform._windows_adapters
    original_ipv4 = host_platform._windows_ipv4
    try:
        host_platform.IS_WINDOWS = True
        host_platform._windows_adapters = lambda: [
            {
                "Name": "USB Ethernet/RNDIS Gadget",
                "Status": "Up",
                "InterfaceDescription": "Remote NDIS Compatible Device",
                "MacAddress": "00-11-22-33-44-55",
            }
        ]
        host_platform._windows_ipv4 = lambda _iface: [
            {"IPAddress": "192.168.244.10", "PrefixLength": 24}
        ]
        config = dict(DEFAULT_CONFIG)
        config["iface"] = "USB Ethernet/RNDIS Gadget"
        commands = host_platform.configure_ip_commands(config)
        ping = host_platform.ping_command(config["device_ip"])
        status = host_platform.interface_status(config)
    finally:
        host_platform._windows_ipv4 = original_ipv4
        host_platform._windows_adapters = original_adapters
        host_platform.IS_WINDOWS = original_is_windows

    ok = (
        commands
        and commands[0][:5] == ["netsh", "interface", "ipv4", "set", "address"]
        and "name=USB Ethernet/RNDIS Gadget" in commands[0]
        and ping == ["ping", "-n", "1", "-w", "1000", "192.168.244.1"]
        and status.get("has_expected_ip") is True
    )
    return status_line(ok, "Windows host commands", f"{commands} | {ping} | {status}")


def check_process_helpers():
    from . import processes

    original_is_windows = host_platform.IS_WINDOWS
    try:
        host_platform.IS_WINDOWS = True
        ok_adb = processes.command_name([r"C:\tools\adb.exe", "devices"]) == "adb"
        ok_mpv = processes.command_name([r"C:\tools\mpv.exe"]) == "mpv"
    finally:
        host_platform.IS_WINDOWS = original_is_windows
    return status_line(ok_adb and ok_mpv, "process command_name Windows exe")


def check_workspace_helpers():
    from .services import workspace

    original = workspace.IS_WINDOWS
    try:
        workspace.IS_WINDOWS = True
        command = workspace.terminal_command(r"C:\BLTN_ADB", r"C:\BLTN_ADB\docs\adb_windows.cmd")
    finally:
        workspace.IS_WINDOWS = original
    ok = command == ["cmd.exe", "/k", r"C:\BLTN_ADB\docs\adb_windows.cmd"]
    return status_line(ok, "workspace terminal command", str(command))


def check_service_helpers():
    from .services import adb_update, files, root, runtime_controls

    ok = True
    ok = status_line(files.normalize_remote_path("etc", "/") == "/etc", "remote path normalize") and ok
    ok = status_line(files.local_pull_path("/mnt/data/a.txt").endswith(os.path.join("ecu-files", "mnt", "data", "a.txt")), "local pull path") and ok
    ok = status_line(root.validate_debug_bin_path("") is not None, "debug bin validation empty") and ok
    ok = status_line(adb_update.push_timeout_seconds(1024) >= adb_update.PUSH_TIMEOUT_MIN_SECONDS, "update push timeout") and ok
    service = runtime_controls.SERVICE_CONTROLS["wifi"]
    command = runtime_controls.service_control_shell_command(service, "start")
    ok = status_line("/ydvrs/bin/hostapd-start" in command and "systemctl" in command, "runtime wifi service command") and ok
    return ok


def write_report(path, exit_code):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("Adapter Status Windows smoke report\n")
        handle.write(f"OS: {platform.platform()}\n")
        handle.write(f"Python: {sys.version}\n")
        handle.write(f"CWD: {os.getcwd()}\n")
        handle.write(f"Exit code: {exit_code}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Non-destructive Windows smoke tests")
    parser.add_argument("--require-gtk", action="store_true")
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)

    print("Adapter Status Windows smoke")
    print(f"OS: {platform.platform()}")
    print(f"Python: {sys.executable}")
    print()

    checks = []
    try:
        checks = [
            check_imports(require_gtk=args.require_gtk),
            check_windows_command_generation(),
            check_process_helpers(),
            check_workspace_helpers(),
            check_service_helpers(),
        ]
    except Exception:
        traceback.print_exc()
        checks.append(False)

    exit_code = 0 if all(checks) else 1
    if args.report:
        write_report(args.report, exit_code)
        print(f"Report: {args.report}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
