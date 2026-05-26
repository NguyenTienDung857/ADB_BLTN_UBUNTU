import ipaddress
import ntpath
import json
import os
import re
import shutil
import subprocess


IS_WINDOWS = os.name == "nt"
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config_dir(app_name="adapter-status"):
    if IS_WINDOWS:
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, app_name)
    return os.path.expanduser(f"~/.config/{app_name}")


def cache_dir(app_name="adapter-status"):
    if IS_WINDOWS:
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, app_name)
    return os.path.expanduser(f"~/.cache/{app_name}")


def bundled_tool_dirs():
    return (
        os.path.join(PROJECT_DIR, "tools", "platform-tools"),
        os.path.join(PROJECT_DIR, "platform-tools"),
        os.path.join(PROJECT_DIR, "docs", "platform-tools"),
        PROJECT_DIR,
    )


def find_executable(name):
    names = [name]
    if IS_WINDOWS and not name.lower().endswith(".exe"):
        names.insert(0, f"{name}.exe")

    for directory in bundled_tool_dirs():
        for candidate_name in names:
            candidate = os.path.join(directory, candidate_name)
            if os.path.isfile(candidate):
                return candidate

    for candidate_name in names:
        path = shutil.which(candidate_name)
        if path:
            return path
    return None


def command_basename(command):
    if not command:
        return ""
    path_text = str(command[0])
    name = (ntpath.basename(path_text) if IS_WINDOWS else os.path.basename(path_text)).lower()
    if IS_WINDOWS and name.endswith(".exe"):
        name = name[:-4]
    return name


def resolve_command(command):
    if not command:
        return command
    if command_basename(command) == "adb":
        adb_path = find_executable("adb")
        if adb_path:
            return [adb_path] + list(command[1:])
    return command


def host_cidr_parts(host_cidr):
    text = str(host_cidr or "").strip()
    if "/" not in text:
        return text, 24
    host, prefix_text = text.split("/", 1)
    try:
        prefix = int(prefix_text)
    except ValueError:
        prefix = 24
    return host.strip(), prefix


def cidr_to_netmask(host_cidr):
    try:
        network = ipaddress.ip_network(str(host_cidr or "192.168.244.10/24"), strict=False)
        return str(network.netmask)
    except ValueError:
        return "255.255.255.0"


def sanitize_iface_value(value, fallback):
    text = str(value or "").strip()
    if IS_WINDOWS:
        if 1 <= len(text) <= 120 and not re.search(r"[\r\n\t\"<>|]", text):
            return text
        return fallback

    if re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", text):
        return text

    match = re.search(r"enx[0-9A-Fa-f]{12}", text)
    if match:
        return match.group(0)
    return fallback


def _run_host_command(command, timeout=4):
    try:
        completed = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return completed.returncode, (completed.stdout or "").strip()
    except Exception as exc:
        return 1, str(exc)


def _read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _ps_quote(value):
    return "'" + str(value or "").replace("'", "''") + "'"


def _powershell_command(script):
    executable = find_executable("powershell") or find_executable("pwsh") or "powershell"
    return [
        executable,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]


def _powershell_json(script, timeout=5):
    code, output = _run_host_command(_powershell_command(script), timeout=timeout)
    if code != 0 or not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _windows_adapters():
    script = (
        "$items = Get-NetAdapter -ErrorAction SilentlyContinue | "
        "Select-Object Name,Status,InterfaceDescription,MacAddress; "
        "if ($items) { $items | ConvertTo-Json -Compress }"
    )
    return [item for item in _as_list(_powershell_json(script)) if isinstance(item, dict)]


def _windows_ipv4(interface_name):
    script = (
        f"$items = Get-NetIPAddress -InterfaceAlias {_ps_quote(interface_name)} "
        "-AddressFamily IPv4 -ErrorAction SilentlyContinue | "
        "Where-Object { $_.IPAddress -and $_.IPAddress -notlike '169.254.*' } | "
        "Select-Object IPAddress,PrefixLength; "
        "if ($items) { $items | ConvertTo-Json -Compress }"
    )
    return [item for item in _as_list(_powershell_json(script)) if isinstance(item, dict)]


def _adapter_score(adapter):
    name = str(adapter.get("Name") or "")
    desc = str(adapter.get("InterfaceDescription") or "")
    status = str(adapter.get("Status") or "")
    text = f"{name} {desc}".lower()
    score = 0
    if status.lower() == "up":
        score += 20
    for token, weight in (
        ("rndis", 12),
        ("usb", 10),
        ("remote ndis", 10),
        ("ethernet", 5),
        ("realtek", 3),
    ):
        if token in text:
            score += weight
    return score


def _windows_find_adapter(configured_iface):
    adapters = _windows_adapters()
    configured_lower = str(configured_iface or "").casefold()
    for adapter in adapters:
        if str(adapter.get("Name") or "").casefold() == configured_lower:
            return adapter

    ranked = sorted(adapters, key=_adapter_score, reverse=True)
    if ranked and _adapter_score(ranked[0]) > 0:
        return ranked[0]
    return None


def detect_usb_iface():
    if IS_WINDOWS:
        adapter = _windows_find_adapter("")
        return str(adapter.get("Name") or "") if adapter else None

    try:
        names = sorted(os.listdir("/sys/class/net"))
    except OSError:
        return None
    for name in names:
        if name.startswith("enx"):
            return name
    return None


def interface_status(config):
    configured_iface = config["iface"]
    host_ip, expected_prefix = host_cidr_parts(config["host_cidr"])

    if IS_WINDOWS:
        adapter = _windows_find_adapter(configured_iface)
        iface = str(adapter.get("Name") or configured_iface) if adapter else configured_iface
        exists = bool(adapter)
        status = str(adapter.get("Status") or "missing") if adapter else "missing"
        ipv4_items = _windows_ipv4(iface) if exists else []
        ip_lines = [
            f"{iface} {item.get('IPAddress')}/{item.get('PrefixLength')}"
            for item in ipv4_items
            if item.get("IPAddress")
        ]
        has_expected_ip = any(
            str(item.get("IPAddress")) == host_ip
            and int(item.get("PrefixLength") or expected_prefix) == expected_prefix
            for item in ipv4_items
        )
        return {
            "configured_iface": configured_iface,
            "iface": iface,
            "detected_iface": iface if iface != configured_iface else None,
            "exists": exists,
            "carrier": "1" if status.lower() == "up" else "0",
            "operstate": status,
            "ip_output": "\n".join(ip_lines),
            "has_expected_ip": has_expected_ip,
        }

    iface = configured_iface
    exists = os.path.exists(f"/sys/class/net/{iface}")
    detected_iface = None
    if not exists:
        detected_iface = detect_usb_iface()
        if detected_iface:
            iface = detected_iface
            exists = os.path.exists(f"/sys/class/net/{iface}")

    carrier = _read_file(f"/sys/class/net/{iface}/carrier") if exists else None
    operstate = _read_file(f"/sys/class/net/{iface}/operstate") if exists else "missing"
    _code, ip_output = _run_host_command(
        ["ip", "-4", "-o", "addr", "show", "dev", iface],
        timeout=1,
    )

    return {
        "configured_iface": configured_iface,
        "iface": iface,
        "detected_iface": detected_iface,
        "exists": exists,
        "carrier": carrier,
        "operstate": operstate,
        "ip_output": ip_output,
        "has_expected_ip": host_ip in ip_output,
    }


def configure_ip_commands(config):
    status = interface_status(config)
    iface = status.get("iface") or config["iface"]

    if IS_WINDOWS:
        host_ip, _prefix = host_cidr_parts(config["host_cidr"])
        netmask = cidr_to_netmask(config["host_cidr"])
        return [
            [
                "netsh",
                "interface",
                "ipv4",
                "set",
                "address",
                f"name={iface}",
                "static",
                host_ip,
                netmask,
            ],
            ["netsh", "interface", "set", "interface", f"name={iface}", "admin=enabled"],
        ]

    return [
        ["sudo", "ip", "addr", "replace", config["host_cidr"], "dev", iface],
        ["sudo", "ip", "link", "set", iface, "up"],
    ]


def ping_command(host):
    if IS_WINDOWS:
        return ["ping", "-n", "1", "-w", "1000", host]
    return ["ping", "-c", "1", "-W", "1", host]
