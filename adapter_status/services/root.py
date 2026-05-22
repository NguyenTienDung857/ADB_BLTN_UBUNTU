import os
import re
import shlex
import time

from ..adb.executor import run, run_with_delayed_pty_input
from ..config import adb_target
from ..constants import (
    ROOT_CHANGE_FILE_COMMAND,
    ROOT_CHANGE_FILE_REMOTE_PATH,
    ROOT_DROP_WAIT_SECONDS,
    ROOT_UPDATE_REMOTE_PATH,
    ROOT_WAIT_SECONDS,
)
from ..processes import clean_command_output
from .adb_device import adb_shell, adb_state_from_devices, configure_ip_commands, is_root_id_output
from .adb_device import wait_for_adb_device
from .files import human_size

def validate_debug_bin_path(path):
    if not path:
        return "Chưa chọn file debug .bin."
    if not os.path.isfile(path):
        return f"Không thấy file: {path}"
    if not path.lower().endswith(".bin"):
        return "File được chọn không phải .bin."
    if os.path.getsize(path) <= 0:
        return f"File rỗng: {path}"
    return None


def is_transient_adb_disconnect_output(output):
    output_lower = str(output or "").lower()
    markers = (
        "error: closed",
        "device offline",
        "offline",
        "device not found",
        "no devices/emulators found",
        "cannot connect to daemon",
        "protocol fault",
        "connection reset",
    )
    return any(marker in output_lower for marker in markers)


def is_cmdtool_ipc_error(output):
    output_lower = str(output or "").lower()
    return (
        "command status = -22" in output_lower
        or "failed to create client socket file" in output_lower
        or "/dev/shm/.ee" in output_lower
        or "unitcliipcconnect" in output_lower
    )


def cleanup_cmdtool_ipc(config, purpose_prefix="cmdtool"):
    return adb_shell(
        config,
        "pkill -9 cmdtool 2>/dev/null || true",
        timeout=5,
        purpose=f"{purpose_prefix}-cmdtool-cleanup",
    )


def run_cmdtool_update_cpu(config, log=None, purpose_prefix="get-root", retry_transient=True):
    target = adb_target(config)
    last_code = 1
    last_output = ""

    for attempt in range(1, 3):
        cleanup_cmdtool_ipc(config, purpose_prefix=purpose_prefix)
        time.sleep(0.5)

        if attempt > 1:
            if log:
                log("ADB/cmdtool chưa ổn, thử connect lại rồi chạy update cpu lần nữa.")
            state, devices = wait_for_adb_device(
                config,
                wait_seconds=10.0,
                log=log,
                purpose=f"{purpose_prefix}-cmdtool-retry",
            )
            if state != "device":
                return False, last_code, (
                    f"ADB chưa sẵn sàng để retry cmdtool. State: {state or 'not connected'}\n"
                    f"{devices}"
                ).strip()

        code, output = run_with_delayed_pty_input(
            ["adb", "-s", target, "shell", "-tt", "cmdtool"],
            "update cpu\n",
            prompt_text="VRS>",
            completion_texts=("command status",),
            timeout=35,
            purpose=f"{purpose_prefix}-cmdtool",
        )
        output = clean_command_output(output)
        last_code = code
        last_output = output
        if output and log:
            log(output)

        if "command status = 0" in output.lower():
            if code == 124 and log:
                log("cmdtool đã báo status=0 nhưng không tự thoát; app đã đóng phiên cmdtool.")
            cleanup_cmdtool_ipc(config, purpose_prefix=purpose_prefix)
            return True, code, output

        transient = is_transient_adb_disconnect_output(output)
        ipc_error = is_cmdtool_ipc_error(output)
        cleanup_cmdtool_ipc(config, purpose_prefix=purpose_prefix)
        if ipc_error and attempt == 1 and log:
            log("cmdtool trả lỗi IPC /dev/shm/.ee (-22); đã dọn cmdtool treo và retry một lần.")
        if not (retry_transient and transient) and not (ipc_error and attempt == 1):
            break

    return False, last_code, last_output


def remote_change_file_exists(config):
    code, output = adb_shell(
        config,
        f"test -e {shlex.quote(ROOT_CHANGE_FILE_REMOTE_PATH)}; echo change_file_exists=$?",
        timeout=5,
        purpose="get-root-change-file-exists",
    )
    return code == 0 and "change_file_exists=0" in clean_command_output(output)


def run_root_change_file(config, log=None):
    last_code = 1
    last_output = ""

    def emit(message):
        if log:
            log(message)

    for attempt in range(1, 3):
        if attempt > 1:
            emit("ADB vừa đóng khi chạy change_file; reconnect rồi chạy lại change_file.")

        state, devices_output = wait_for_adb_device(
            config,
            wait_seconds=12.0,
            log=emit,
            purpose=f"get-root-change-file-wait-{attempt}",
        )
        if devices_output:
            emit(devices_output)
        if state != "device":
            last_code = 1
            last_output = f"ADB chưa sẵn sàng để chạy change_file. State: {state or 'not connected'}"
            continue

        code, output = adb_shell(
            config,
            ROOT_CHANGE_FILE_COMMAND,
            timeout=30,
            purpose="get-root-change-file",
        )
        output = clean_command_output(output)
        if output:
            emit(output)

        last_code = code
        last_output = output
        output_lower = output.lower()
        change_ok = (
            "rebooting" in output_lower
            or "setuid/setgid" in output_lower
            or "change_file" in output_lower and "삭제" in output_lower
        )
        if code == 0 or change_ok:
            return True, code, output

        if not is_transient_adb_disconnect_output(output):
            break

        emit("ADB đóng phiên trong lúc chạy change_file; kiểm tra lại root trước khi kết luận lỗi.")
        ok, message = wait_for_root_after_reboot(config, log=emit)
        last_output = "\n".join(line for line in (output, message) if line)
        if ok and (attempt >= 2 or not remote_change_file_exists(config)):
            return True, code, last_output
        if ok:
            emit("ADB đã root nhưng change_file vẫn còn; thử chạy change_file thêm một lần để hoàn tất.")

    return False, last_code, last_output


def drop_adb_root(config, log=None):
    target = adb_target(config)

    def emit(message):
        if log:
            log(message)

    emit("Bắt đầu Thoát Root tạm thời bằng adb unroot.")
    state, devices_output = wait_for_adb_device(
        config,
        wait_seconds=10.0,
        log=emit,
        purpose="drop-root-precheck",
    )
    if devices_output:
        emit(devices_output)
    if state != "device":
        return f"ADB chưa sẵn sàng để Thoát Root. State: {state or 'not connected'}"

    code, id_output = run(["adb", "-s", target, "shell", "id"], timeout=5, purpose="drop-root-id-before")
    id_output = clean_command_output(id_output)
    if id_output:
        emit(f"id trước khi thoát root: {id_output}")
    if code == 0 and not is_root_id_output(id_output):
        return f"Thiết bị đang chưa root.\n{id_output}"

    code, output = run(["adb", "-s", target, "unroot"], timeout=10, purpose="drop-root-unroot")
    output = clean_command_output(output)
    if output:
        emit(output)
    output_lower = output.lower()
    accepted_unroot = (
        "restarting adbd as non root" in output_lower
        or "adbd not running as root" in output_lower
    )
    if code != 0 and not accepted_unroot:
        return f"adb unroot lỗi ({code}).\n{output}"

    deadline = time.monotonic() + ROOT_DROP_WAIT_SECONDS
    next_connect_at = 0.0
    last_state = ""
    last_id_output = ""
    last_devices = ""

    emit(f"Chờ ADB lên lại tối đa {int(ROOT_DROP_WAIT_SECONDS)} giây...")
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_connect_at:
            run(["adb", "connect", target], timeout=4, purpose="drop-root-connect")
            next_connect_at = now + 2.0

        code, devices = run(["adb", "devices"], timeout=2, purpose="drop-root-state")
        last_devices = clean_command_output(devices)
        state = adb_state_from_devices(devices, target) if code == 0 else ""
        if state != last_state:
            emit(f"ADB state: {state or 'chưa thấy thiết bị'}")
            last_state = state

        if state == "device":
            code, id_output = run(
                ["adb", "-s", target, "shell", "id"],
                timeout=5,
                purpose="drop-root-id-after",
            )
            last_id_output = clean_command_output(id_output)
            if last_id_output:
                emit(f"id: {last_id_output}")
            if code == 0 and not is_root_id_output(last_id_output):
                return f"Thoát Root OK: ADB đã về user thường.\n{last_id_output}"

        time.sleep(1.0)

    message = "Thoát Root chưa thành công trong thời gian chờ."
    if last_state:
        message += f"\nADB state cuối: {last_state}"
    if last_id_output:
        message += f"\nid cuối: {last_id_output}"
    if last_devices:
        message += f"\nadb devices cuối:\n{last_devices}"
    return message


def wait_for_root_after_reboot(config, log=None):
    target = adb_target(config)
    deadline = time.monotonic() + ROOT_WAIT_SECONDS
    next_configure_at = 0.0
    next_connect_at = 0.0
    last_state = None
    first_non_root_at = None
    last_id_output = ""
    last_devices = ""

    if log:
        log(f"Chờ thiết bị reboot và ADB lên lại tối đa {int(ROOT_WAIT_SECONDS)} giây...")

    while time.monotonic() < deadline:
        now = time.monotonic()

        if now >= next_configure_at:
            for command in configure_ip_commands(config):
                code, output = run(command, timeout=3, purpose="get-root-ip")
                if code != 0 and output and log:
                    log(f"Cấu hình IP chưa OK: {clean_command_output(output)}")
                    break
            next_configure_at = now + 5.0

        if now >= next_connect_at:
            code, output = run(["adb", "connect", target], timeout=4, purpose="get-root-connect")
            if output and log and code == 0 and "already connected" not in output.lower():
                log(clean_command_output(output))
            next_connect_at = now + 2.0

        code, devices = run(["adb", "devices"], timeout=2, purpose="get-root-state")
        last_devices = devices
        state = adb_state_from_devices(devices, target) if code == 0 else ""
        if state != last_state:
            if log:
                log(f"ADB state: {state or 'chưa thấy thiết bị'}")
            last_state = state

        if state == "device":
            code, id_output = run(
                ["adb", "-s", target, "shell", "id"],
                timeout=5,
                purpose="get-root-id",
            )
            last_id_output = clean_command_output(id_output)
            if last_id_output and log:
                log(f"id: {last_id_output}")
            if code == 0 and is_root_id_output(last_id_output):
                return True, "Get Root thành công: thiết bị đang chạy với uid=0(root)."
            if first_non_root_at is None:
                first_non_root_at = now
            elif now - first_non_root_at > 20:
                return (
                    False,
                    "ADB đã lên lại nhưng chưa có root.\n"
                    f"id cuối cùng: {last_id_output or 'không đọc được'}",
                )

        time.sleep(1.0)

    message = "Hết thời gian chờ thiết bị lên lại sau Get Root."
    if last_state:
        message += f"\nADB state cuối: {last_state}"
    if last_id_output:
        message += f"\nid cuối: {last_id_output}"
    if last_devices:
        message += f"\nadb devices cuối:\n{last_devices}"
    return False, message


def get_root_with_debug_file(config, debug_path, log=None):
    validation_error = validate_debug_bin_path(debug_path)
    if validation_error:
        return validation_error

    target = adb_target(config)
    debug_size = os.path.getsize(debug_path)

    def emit(message):
        if log:
            log(message)

    emit("Bắt đầu Get Root.")
    emit(f"ADB target: {target}")
    emit(f"File debug: {debug_path}")
    emit(f"Size: {human_size(debug_size)}")

    emit("Kiểm tra ADB:")
    state, devices_output = wait_for_adb_device(
        config,
        wait_seconds=10.0,
        log=emit,
        purpose="get-root-precheck",
    )
    if devices_output:
        emit(devices_output)
    if state != "device":
        return f"ADB chưa sẵn sàng. State: {state or 'not connected'}"

    code, id_output = run(["adb", "-s", target, "shell", "id"], timeout=5, purpose="get-root-id-before")
    id_output = clean_command_output(id_output)
    if id_output:
        emit(f"id trước khi chạy: {id_output}")
    if code == 0 and is_root_id_output(id_output):
        return "Thiết bị đã có root sẵn: uid=0(root). Không cần chạy update debug."

    emit(f"Đẩy file debug vào thiết bị: {ROOT_UPDATE_REMOTE_PATH}")
    code, output = run(
        ["adb", "-s", target, "push", debug_path, ROOT_UPDATE_REMOTE_PATH],
        timeout=30,
        purpose="get-root-push-debug",
    )
    output = clean_command_output(output)
    if output:
        emit(output)
    if code != 0:
        return f"Push file debug lỗi ({code}).\n{output}"

    emit("Chạy cmdtool: update cpu")
    update_ok, code, output = run_cmdtool_update_cpu(config, log=emit)
    if not update_ok:
        return f"cmdtool update cpu chưa báo thành công ({code}).\n{output}"

    emit("Chạy /home/adb/change_file để đổi quyền root và reboot.")
    change_ok, code, output = run_root_change_file(config, log=emit)
    if not change_ok:
        return f"change_file lỗi ({code}).\n{output}"

    emit("Nếu change_file báo Rebooting, không cần reset tay; app đang chờ thiết bị tự lên lại.")
    time.sleep(5)
    ok, message = wait_for_root_after_reboot(config, log=emit)
    return message if ok else f"Get Root chưa thành công.\n{message}"
