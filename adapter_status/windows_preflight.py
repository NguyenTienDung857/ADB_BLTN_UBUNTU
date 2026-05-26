import argparse
import glob
import os
import platform
import sys

from . import host_platform


DEFAULT_CONFIG = {
    "iface": "USB Ethernet/RNDIS Gadget",
    "host_cidr": "192.168.244.10/24",
    "device_ip": "192.168.244.1",
    "adb_port": "4321",
}


def check_line(ok, title, detail="", fatal=False):
    status = "OK" if ok else ("FAIL" if fatal else "WARN")
    line = f"[{status}] {title}"
    if detail:
        line += f" - {detail}"
    print(line)
    return ok or not fatal


def is_admin_windows():
    if os.name != "nt":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def adb_key_paths():
    root = os.path.expanduser("~/.android")
    paths = []
    direct = os.path.join(root, "adbkey")
    if os.path.isfile(direct):
        paths.append(direct)
    paths.extend(sorted(glob.glob(os.path.join(root, "*", "adbkey"))))
    return list(dict.fromkeys(paths))


def check_python():
    ok = sys.version_info >= (3, 9)
    detail = f"{platform.python_implementation()} {platform.python_version()} ({sys.executable})"
    return check_line(ok, "Python", detail, fatal=True)


def check_gtk(require_runtime):
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gtk  # noqa: F401

        return check_line(True, "GTK/PyGObject", "Gtk 3 import OK")
    except Exception as exc:
        return check_line(
            False,
            "GTK/PyGObject",
            str(exc),
            fatal=require_runtime,
        )


def check_psutil(require_runtime):
    try:
        import psutil

        return check_line(True, "psutil", f"version {getattr(psutil, '__version__', 'unknown')}")
    except Exception as exc:
        return check_line(False, "psutil", str(exc), fatal=require_runtime)


def check_adb(require_runtime):
    adb_path = host_platform.find_executable("adb")
    if adb_path:
        return check_line(True, "adb", adb_path)
    return check_line(
        False,
        "adb",
        "Khong thay adb.exe trong tools\\platform-tools hoac PATH.",
        fatal=require_runtime,
    )


def check_mpv():
    mpv_path = host_platform.find_executable("mpv")
    if mpv_path:
        return check_line(True, "mpv", mpv_path)
    return check_line(
        False,
        "mpv",
        "Chua co mpv.exe; chi anh huong nut Mo video truc tiep.",
        fatal=False,
    )


def check_keys():
    keys = adb_key_paths()
    if keys:
        return check_line(True, "ADB keys", f"{len(keys)} key(s) trong ~/.android")
    return check_line(
        False,
        "ADB keys",
        r"Chua thay adbkey trong %USERPROFILE%\.android; ADB co the unauthorized.",
        fatal=False,
    )


def check_admin(require_admin):
    if os.name != "nt":
        return check_line(False, "Administrator", "Khong phai Windows; bo qua.", fatal=False)
    ok = is_admin_windows()
    return check_line(
        ok,
        "Administrator",
        "Run as administrator OK" if ok else "Can Run as administrator de netsh gan IP.",
        fatal=require_admin,
    )


def check_static_layout():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    required = (
        "adapter-status-ui",
        "adapter_status/host_platform.py",
        "adapter_status/windows_adb_shell.py",
        "docs/adb_windows.cmd",
        "docs/WINDOWS_PACKAGE.md",
        "run_windows.cmd",
        "bootstrap_windows.cmd",
        "check_windows_runtime.cmd",
        "smoke_windows.cmd",
        "validate_windows_with_device.cmd",
        "requirements-windows.txt",
    )
    ok = True
    for rel_path in required:
        exists = os.path.exists(os.path.join(root, rel_path))
        ok = check_line(exists, f"Package file {rel_path}", fatal=True) and ok
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
        commands = host_platform.configure_ip_commands(dict(DEFAULT_CONFIG))
        ping = host_platform.ping_command(DEFAULT_CONFIG["device_ip"])
    finally:
        host_platform._windows_ipv4 = original_ipv4
        host_platform._windows_adapters = original_adapters
        host_platform.IS_WINDOWS = original_is_windows

    ok = (
        commands
        and commands[0][:5] == ["netsh", "interface", "ipv4", "set", "address"]
        and "name=USB Ethernet/RNDIS Gadget" in commands[0]
        and ping[:2] == ["ping", "-n"]
    )
    return check_line(ok, "Windows command generation", f"{commands} | {ping}", fatal=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Adapter Status Windows preflight checks")
    parser.add_argument(
        "--require-runtime",
        action="store_true",
        help="Fail if GTK, psutil, or adb are missing.",
    )
    parser.add_argument(
        "--require-admin",
        action="store_true",
        help="Fail on Windows if not running as administrator.",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Only verify package files and generated Windows commands.",
    )
    args = parser.parse_args(argv)

    print("Adapter Status Windows preflight")
    print(f"OS: {platform.platform()}")
    print(f"CWD: {os.getcwd()}")
    print()

    results = [
        check_static_layout(),
        check_windows_command_generation(),
    ]
    if not args.static_only:
        results.extend(
            [
                check_python(),
                check_gtk(args.require_runtime),
                check_psutil(args.require_runtime),
                check_adb(args.require_runtime),
                check_mpv(),
                check_keys(),
                check_admin(args.require_admin),
            ]
        )

    print()
    if all(results):
        print("Preflight OK.")
        return 0
    print("Preflight co loi bat buoc. Sua cac dong FAIL roi chay lai.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
