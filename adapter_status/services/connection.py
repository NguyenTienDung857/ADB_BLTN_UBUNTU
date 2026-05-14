import os
import time

from ..adb.executor import run
from ..config import adb_target, host_ip_from_cidr
from ..constants import CONNECT_WINDOW_SECONDS, DEVICE_INFO_EMPTY_TEXT
from ..processes import (
    clean_command_output,
    cleanup_previous_processes,
    command_text,
    kill_adb_processes_for_reconnect,
    tracked_adb_server_pids,
)
from .adb_device import (
    adb_state_from_devices,
    collect_device_info_text,
    configure_ip_commands,
    detect_usb_iface,
    is_root_id_output,
    read_file,
)

def append_command_output(outputs, label, code, output):
    if output:
        outputs.append(output)
    if code != 0:
        outputs.append(f"{label} lỗi ({code}).")



def configure_ip(config):
    outputs = []
    for command in configure_ip_commands(config):
        code, output = run(command, timeout=5, purpose="configure-ip")
        append_command_output(outputs, command_text(command), code, output)
        if code != 0:
            break
    return "\n".join(outputs) if outputs else "Đã cấu hình IP adapter."


def run_command_sequence(commands, timeout, purpose="action"):
    outputs = []
    for command in commands:
        code, output = run(command, timeout=timeout, purpose=purpose)
        if output:
            outputs.append(output)
        if code != 0:
            outputs.append(f"Lệnh lỗi ({code}): {' '.join(command)}")
            break
    return "\n".join(outputs) if outputs else "Đã chạy lệnh."

def adb_reconnect(config):
    target = adb_target(config)
    outputs = [f"Đang canh ADB tối đa {int(CONNECT_WINDOW_SECONDS)} giây: {target}"]

    code, output = run(["adb", "disconnect", target], timeout=2, purpose="adb-reconnect-disconnect")
    if output and "no such device" not in output:
        outputs.append(output)
    if code != 0 and "no such device" not in output:
        outputs.append(f"adb disconnect {target} lỗi ({code}).")

    killed = kill_adb_processes_for_reconnect(target)
    if killed:
        outputs.append(f"Đã dọn {len(killed)} tiến trình ADB cũ/treo.")

    code, output = run(["adb", "start-server"], timeout=5, purpose="adb-reconnect-start")
    if output:
        outputs.append(output)
    if code != 0:
        outputs.append(f"adb start-server lỗi ({code}).")

    last_devices = ""
    last_state = ""
    last_connect_output = ""
    last_ip_error = ""
    attempt = 0
    ping_seen = False
    last_ping_ok = False
    next_configure_at = 0.0
    next_ping_at = 0.0
    deadline = time.monotonic() + CONNECT_WINDOW_SECONDS

    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_configure_at:
            for command in configure_ip_commands(config):
                code, output = run(command, timeout=3, purpose="adb-reconnect-ip")
                if code != 0:
                    last_ip_error = output or f"{command_text(command)} lỗi ({code})"
            next_configure_at = now + 1.0

        if now >= next_ping_at:
            ping_code, _ping_output = run(
                ["ping", "-c", "1", "-W", "1", config["device_ip"]],
                timeout=2,
                purpose="adb-reconnect-ping",
            )
            last_ping_ok = ping_code == 0
            ping_seen = ping_seen or last_ping_ok
            next_ping_at = now + 2.0

        attempt += 1
        if last_ping_ok or ping_seen:
            code, output = run(["adb", "connect", target], timeout=5, purpose="adb-reconnect-connect")
            if output:
                last_connect_output = output

        code, devices = run(["adb", "devices"], timeout=2, purpose="adb-reconnect-state")
        last_devices = devices
        last_state = adb_state_from_devices(devices, target)
        if last_state == "device":
            outputs.append(f"ADB Connect OK sau {attempt} lần thử.")
            if last_connect_output:
                outputs.append(last_connect_output)
            outputs.append(last_devices)
            outputs.append("ADB đã sẵn sàng: device.")
            return "\n".join(line for line in outputs if line)
        if last_state == "unauthorized":
            if last_connect_output:
                outputs.append(last_connect_output)
            outputs.append(last_devices)
            outputs.append("ADB unauthorized: ECU chưa chấp nhận key hoặc key không đúng.")
            return "\n".join(line for line in outputs if line)
        if last_state == "offline":
            for _wait_index in range(10):
                time.sleep(0.3)
                code, devices = run(["adb", "devices"], timeout=2, purpose="adb-reconnect-state")
                last_devices = devices
                last_state = adb_state_from_devices(devices, target)
                if last_state == "device":
                    outputs.append(f"ADB Connect OK sau {attempt} lần thử.")
                    if last_connect_output:
                        outputs.append(last_connect_output)
                    outputs.append(last_devices)
                    outputs.append("ADB đã sẵn sàng: device.")
                    return "\n".join(line for line in outputs if line)
                if last_state == "unauthorized":
                    if last_connect_output:
                        outputs.append(last_connect_output)
                    outputs.append(last_devices)
                    outputs.append("ADB unauthorized: ECU chưa chấp nhận key hoặc key không đúng.")
                    return "\n".join(line for line in outputs if line)
                if last_state != "offline":
                    break
            run(["adb", "disconnect", target], timeout=2, purpose="adb-reconnect-disconnect")
            kill_adb_processes_for_reconnect(target)
        time.sleep(0.15)

    if ping_seen:
        outputs.append(f"Ping từng OK: {config['device_ip']}")
    elif last_ip_error:
        outputs.append(f"Chưa cấu hình được IP adapter: {last_ip_error}")

    if last_connect_output:
        outputs.append(last_connect_output)
    if last_devices:
        outputs.append(last_devices)

    if last_state == "offline":
        run(["adb", "disconnect", target], timeout=2, purpose="adb-reconnect-disconnect")
        killed = kill_adb_processes_for_reconnect(target)
        if killed:
            outputs.append(f"Đã dọn {len(killed)} tiến trình ADB offline sau khi thử.")
        outputs.append("ADB vẫn offline. Bấm ADB Connect lại để app dọn transport cũ và canh tiếp.")
    elif not ping_seen:
        outputs.append("Chưa ping được BLTN trong lúc app canh.")
    elif last_state:
        outputs.append(f"ADB state hiện tại: {last_state}.")
    else:
        outputs.append("ADB chưa thấy thiết bị sau khi connect.")

    outputs.append("Nếu bạn reset BLTN trước khi bấm ADB Connect thì có thể đã lỡ cửa sổ ADB.")
    outputs.append("Quy trình đúng: bấm ADB Connect trước, thấy app đang canh, rồi reset BLTN.")
    return "\n".join(line for line in outputs if line)


def clean_reset(config, include_current=False):
    target = adb_target(config)
    outputs = []

    killed_tracked = cleanup_previous_processes(include_current=include_current)
    if killed_tracked:
        outputs.append(f"Đã dọn {len(killed_tracked)} tiến trình do app mở.")

    killed_adb = kill_adb_processes_for_reconnect(target)
    if killed_adb:
        outputs.append(f"Đã reset {len(killed_adb)} tiến trình ADB/server cũ.")

    for command in configure_ip_commands(config):
        code, output = run(command, timeout=5, purpose="clean-reset-ip")
        append_command_output(outputs, command_text(command), code, output)
        if code != 0:
            outputs.append("Reset dừng lại vì chưa cấu hình được IP adapter.")
            return "\n".join(line for line in outputs if line)

    outputs.append("Reset sạch xong. IP adapter đã được gán lại, ADB server cũ đã được dọn.")
    outputs.append("Bấm ADB Connect khi ECU/BLTN sẵn sàng.")
    return "\n".join(line for line in outputs if line)


def collect_status(config):
    configured_iface = config["iface"]
    iface = configured_iface
    host_cidr = config["host_cidr"]
    host_ip = host_ip_from_cidr(host_cidr)
    device_ip = config["device_ip"]
    target = adb_target(config)

    exists = os.path.exists(f"/sys/class/net/{iface}")
    detected_iface = None
    if not exists:
        detected_iface = detect_usb_iface()
        if detected_iface:
            iface = detected_iface
            exists = os.path.exists(f"/sys/class/net/{iface}")

    carrier = read_file(f"/sys/class/net/{iface}/carrier") if exists else None
    operstate = read_file(f"/sys/class/net/{iface}/operstate") if exists else "missing"

    _code, ip_output = run(["ip", "-4", "-o", "addr", "show", "dev", iface], timeout=1, purpose="status")
    has_expected_ip = host_ip in ip_output

    ping_ok = False
    ping_output = "Bỏ qua vì cổng chưa sẵn sàng."
    if exists and carrier == "1" and has_expected_ip:
        ping_code, ping_output = run(
            ["ping", "-c", "1", "-W", "1", device_ip], timeout=2, purpose="status"
        )
        ping_ok = ping_code == 0

    adb_ok = False
    adb_state = ""
    adb_output = "Bỏ qua vì cổng chưa có IP."
    root_ok = False
    root_output = ""
    if exists and carrier == "1" and has_expected_ip:
        if tracked_adb_server_pids():
            _code, adb_output = run(["adb", "devices"], timeout=2, purpose="status")
            adb_state = adb_state_from_devices(adb_output, target)
            adb_ok = adb_state == "device"
        else:
            adb_output = "ADB server chưa chạy."

    if adb_ok:
        root_code, root_output = run(
            ["adb", "-s", target, "shell", "id"],
            timeout=2,
            purpose="status-root",
        )
        root_output = clean_command_output(root_output)
        root_ok = root_code == 0 and is_root_id_output(root_output)
        device_info = collect_device_info_text(config)
    else:
        device_info = DEVICE_INFO_EMPTY_TEXT

    if not exists:
        banner = ("CHƯA THẤY ADAPTER", "bad")
    elif carrier != "1":
        banner = ("CHƯA CẮM / CHƯA CÓ LINK", "bad")
    elif not has_expected_ip:
        banner = (f"CÓ LINK, CHƯA CÓ IP {host_ip} - BẤM ADB CONNECT", "warn")
    elif adb_ok and root_ok:
        banner = ("CONNECTED - ADB ROOT READY", "ok")
    elif adb_ok:
        banner = ("CONNECTED - ADB READY", "ok")
    elif not ping_ok:
        banner = ("ĐANG CHỜ BLTN LÊN MẠNG - BẤM ADB CONNECT ĐỂ CANH", "warn")
    elif adb_state == "offline":
        banner = ("ADB OFFLINE CŨ - BẤM ADB CONNECT", "warn")
    else:
        banner = ("ADB CHƯA CONNECT - BẤM ADB CONNECT", "warn")

    details = [
        f"Tên cổng: {iface}",
        f"Cổng cấu hình: {configured_iface}" if configured_iface != iface else None,
        f"Trạng thái kết nối cổng: {'Đã kết nối' if carrier == '1' else 'Chưa kết nối'}",
        f"Adapter tồn tại: {'Có' if exists else 'Không'}",
        f"Trạng thái OS: {operstate}",
        f"IP mong muốn: {host_cidr}",
        f"IP hiện tại: {ip_output if ip_output else 'Chưa có IPv4'}",
        f"Thiết bị kiểm tra: {device_ip}",
        f"Ping thiết bị: {'OK' if ping_ok else 'Fail'}",
        "ADB port: không probe trực tiếp để tránh làm nhiễu adbd",
        f"ADB target: {target}",
        f"ADB status: {adb_state or ('device' if adb_ok else 'chưa kết nối')}",
        (
            "Root status: "
            + (
                "OK - uid=0(root)"
                if root_ok
                else "Chưa root"
                if adb_ok
                else "Bỏ qua vì ADB chưa device"
            )
        ),
        f"id output: {root_output}" if adb_ok and root_output else None,
        (
            "Gợi ý: "
            + (
                "Bấm ADB Connect để app tự gán IP và canh ADB."
                if not adb_ok
                else "Đã có root; có thể bấm Thoát Root để test Get Root lại."
                if root_ok
                else "Bấm Get Root để chọn file debug và lấy quyền root."
            )
        ),
        f"Cập nhật lúc: {time.strftime('%H:%M:%S')}",
    ]
    details = [line for line in details if line is not None]

    return {
        "banner_text": banner[0],
        "banner_state": banner[1],
        "details": "\n".join(details),
        "device_info": device_info,
        "ping_output": ping_output,
        "adb_output": adb_output,
        "adb_ok": adb_ok,
        "adb_state": adb_state,
        "root_ok": root_ok,
        "root_output": root_output,
        "exists": exists,
        "carrier_ok": carrier == "1",
        "has_expected_ip": has_expected_ip,
        "ping_ok": ping_ok,
        "adb_port_open": False,
        "iface": iface,
        "configured_iface": configured_iface,
        "target": target,
    }
