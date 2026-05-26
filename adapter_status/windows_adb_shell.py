import os
import subprocess

from .adb.executor import adb_env, run
from .config import adb_target, load_config
from .host_platform import configure_ip_commands, resolve_command
from .processes import command_text, new_process_group_kwargs


def main():
    config = load_config()
    target = adb_target(config)

    print("Adapter Status - Windows ADB shell")
    print(f"Interface: {config['iface']}")
    print(f"Host IP:   {config['host_cidr']}")
    print(f"ADB:       {target}")
    print()

    for command in configure_ip_commands(config):
        print(f"> {command_text(command)}")
        code, output = run(command, timeout=15, purpose="terminal-configure-ip")
        if output:
            print(output)
        if code != 0:
            print(f"Lenh cau hinh IP loi ({code}). Neu dang tren Windows, hay mo app bang Run as administrator.")
            print("Tiep tuc thu adb connect vi adapter co the da duoc cau hinh san.")
            break

    env = adb_env()
    if not env.get("ADB_VENDOR_KEYS"):
        print()
        print(r"Canh bao: chua thay ADB key trong %USERPROFILE%\.android")
        print("Neu adb unauthorized, hay copy adbkey dung vao thu muc nay roi chay lai.")

    print()
    run(["adb", "disconnect", target], timeout=2, purpose="terminal-adb-disconnect")
    code, output = run(["adb", "start-server"], timeout=8, purpose="terminal-adb-start")
    if output:
        print(output)
    code, output = run(["adb", "connect", target], timeout=10, purpose="terminal-adb-connect")
    if output:
        print(output)
    code, output = run(["adb", "devices"], timeout=5, purpose="terminal-adb-devices")
    if output:
        print(output)

    print()
    print("Mo adb shell. Go exit de thoat.")
    command = resolve_command(["adb", "-s", target, "shell"])
    try:
        subprocess.call(command, env=env, **new_process_group_kwargs())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Khong mo duoc adb shell: {exc}")

    print()
    os.system("pause" if os.name == "nt" else "true")


if __name__ == "__main__":
    main()
