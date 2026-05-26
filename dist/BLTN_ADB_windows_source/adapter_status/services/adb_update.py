import os
import re
import shlex
import time

from ..adb.executor import run, run_streaming
from ..config import adb_target
from ..constants import ADB_UPDATE_REMOTE_PATH
from ..processes import clean_command_output
from .adb_device import adb_shell, wait_for_adb_device
from .files import human_size
from .root import is_transient_adb_disconnect_output, run_cmdtool_update_cpu


PUSH_PROGRESS_START = 0.12
PUSH_PROGRESS_DONE = 0.72
PUSH_ESTIMATE_BYTES_PER_SECOND = 2 * 1024 * 1024
PUSH_TIMEOUT_BYTES_PER_SECOND = 512 * 1024
PUSH_TIMEOUT_MIN_SECONDS = 180
PUSH_TIMEOUT_MAX_SECONDS = 1800
ADB_UPDATE_RECONNECT_SECONDS = 120.0
ADB_UPDATE_FINAL_RECONNECT_SECONDS = 180.0


def validate_update_bin_path(path):
    if not path:
        return "Chưa chọn file update .bin."
    if not os.path.isfile(path):
        return f"Không thấy file: {path}"
    if not path.lower().endswith(".bin"):
        return "File update được chọn không phải .bin."
    if os.path.getsize(path) <= 0:
        return f"File update rỗng: {path}"
    return None


def push_timeout_seconds(file_size):
    estimated = int(file_size / PUSH_TIMEOUT_BYTES_PER_SECOND) + 90
    return min(max(PUSH_TIMEOUT_MIN_SECONDS, estimated), PUSH_TIMEOUT_MAX_SECONDS)


def emit_progress(progress, fraction, message):
    if progress:
        progress(max(0.0, min(1.0, float(fraction))), message)


def emit_log(log, message):
    text = clean_command_output(str(message or ""))
    if text and log:
        log(text)


def parse_first_integer(text):
    match = re.search(r"\b(\d+)\b", str(text or ""))
    return int(match.group(1)) if match else None


def wait_for_update_adb(config, wait_seconds, log=None, progress=None, fraction=0.5, reason="ADB bị mất"):
    emit_log(log, f"{reason}. App đang chờ ADB reconnect tối đa {int(wait_seconds)} giây.")
    emit_progress(progress, fraction, "Đang chờ ADB reconnect")
    state, devices_output = wait_for_adb_device(
        config,
        wait_seconds=wait_seconds,
        log=log,
        purpose="adb-update-reconnect",
    )
    if devices_output:
        emit_log(log, devices_output)
    if state == "device":
        emit_log(log, "ADB đã reconnect: device.")
        return True, devices_output
    emit_log(log, f"ADB chưa quay lại. State: {state or 'not connected'}")
    return False, devices_output


def failed_because_adb_missing(config, output, log=None, purpose="adb-update-failure-probe"):
    if is_transient_adb_disconnect_output(output):
        return True
    state, devices_output = wait_for_adb_device(
        config,
        wait_seconds=1.0,
        log=None,
        purpose=purpose,
    )
    if state == "device":
        return False
    emit_log(log, f"ADB không còn ở trạng thái device sau lỗi. State: {state or 'not connected'}")
    if devices_output:
        emit_log(log, devices_output)
    return True


def run_adb_push(config, update_path, file_size, log=None, progress=None):
    target = adb_target(config)
    command = ["adb", "-s", target, "push", update_path, ADB_UPDATE_REMOTE_PATH]
    timeout = push_timeout_seconds(file_size)
    expected_seconds = max(8.0, file_size / PUSH_ESTIMATE_BYTES_PER_SECOND)
    last_log_second = {"value": 0}

    emit_progress(progress, PUSH_PROGRESS_START, "Đang push file update vào /tmp/cpu_update.bin")
    emit_log(log, f"Lệnh push: adb -s {target} push {update_path} {ADB_UPDATE_REMOTE_PATH}")
    emit_log(log, f"Timeout push: {timeout} giây")

    def on_output(chunk):
        text = clean_command_output(chunk.replace("\r", "\n"))
        if text:
            emit_log(log, text)

    def on_tick(elapsed):
        ratio = min(0.96, elapsed / expected_seconds)
        fraction = PUSH_PROGRESS_START + (PUSH_PROGRESS_DONE - PUSH_PROGRESS_START) * ratio
        emit_progress(progress, fraction, "Đang push file update vào thiết bị")
        elapsed_second = int(elapsed)
        if elapsed_second and elapsed_second - last_log_second["value"] >= 10:
            last_log_second["value"] = elapsed_second
            emit_log(log, f"Push đang chạy: {elapsed_second} giây")

    code, output = run_streaming(
        command,
        timeout=timeout,
        purpose="adb-update-push",
        on_output=on_output,
        on_tick=on_tick,
        tick_interval=1.0,
    )
    output = clean_command_output(output)
    if code != 0:
        return False, code, output or "adb push không trả output."

    emit_progress(progress, 0.75, "Push file update xong")
    return True, code, output


def push_with_reconnect(config, update_path, file_size, log=None, progress=None):
    pushed, code, output = run_adb_push(config, update_path, file_size, log=log, progress=progress)
    if pushed:
        return True, code, output
    if not failed_because_adb_missing(
        config,
        output,
        log=log,
        purpose="adb-update-push-failure-probe",
    ):
        return False, code, output

    connected, devices = wait_for_update_adb(
        config,
        ADB_UPDATE_RECONNECT_SECONDS,
        log=log,
        progress=progress,
        fraction=0.45,
        reason="ADB mất trong lúc push file update",
    )
    if not connected:
        return False, code, f"{output}\n{devices}".strip()

    verified, verify_code, verify_output = verify_remote_update_file(
        config,
        file_size,
        log=log,
        progress=progress,
    )
    if verified:
        emit_log(log, "File remote đã đủ size sau khi ADB reconnect; tiếp tục update.")
        return True, verify_code, verify_output

    emit_log(log, "File remote chưa đủ sau khi reconnect; push lại một lần từ đầu.")
    return run_adb_push(config, update_path, file_size, log=log, progress=progress)


def verify_remote_update_file(config, expected_size, log=None, progress=None):
    remote_path = shlex.quote(ADB_UPDATE_REMOTE_PATH)
    emit_progress(progress, 0.78, "Kiểm tra file update trên thiết bị")
    command = (
        f"if [ ! -f {remote_path} ]; then echo missing_update_file; exit 1; fi; "
        f"wc -c < {remote_path}; "
        f"ls -l {remote_path}; "
        "sync; echo sync_done=$?"
    )
    code, output = adb_shell(config, command, timeout=25, purpose="adb-update-verify-sync")
    output = clean_command_output(output)
    if output:
        emit_log(log, output)
    if code != 0:
        return False, code, output or f"Không kiểm tra được {ADB_UPDATE_REMOTE_PATH}."

    remote_size = parse_first_integer(output)
    if remote_size != expected_size:
        return (
            False,
            1,
            (
                f"Size file trên thiết bị không khớp. "
                f"Host={expected_size}, remote={remote_size or 'không đọc được'}."
            ),
        )
    if "sync_done=0" not in output:
        return False, 1, f"Đã thấy file nhưng sync chưa xác nhận OK.\n{output}"

    emit_progress(progress, 0.86, "Đã kiểm tra file và sync xong")
    return True, code, output


def verify_with_reconnect(config, expected_size, log=None, progress=None):
    verified, code, output = verify_remote_update_file(config, expected_size, log=log, progress=progress)
    if verified:
        return True, code, output
    if not failed_because_adb_missing(
        config,
        output,
        log=log,
        purpose="adb-update-verify-failure-probe",
    ):
        return False, code, output

    connected, devices = wait_for_update_adb(
        config,
        ADB_UPDATE_RECONNECT_SECONDS,
        log=log,
        progress=progress,
        fraction=0.78,
        reason="ADB mất trong lúc kiểm tra/sync file update",
    )
    if not connected:
        return False, code, f"{output}\n{devices}".strip()
    return verify_remote_update_file(config, expected_size, log=log, progress=progress)


def wait_after_update_command(config, log=None, progress=None):
    emit_progress(progress, 0.94, "Kiểm tra ADB sau lệnh update")
    state, devices_output = wait_for_adb_device(
        config,
        wait_seconds=5.0,
        log=None,
        purpose="adb-update-after-command-fast",
    )
    if state == "device":
        emit_log(log, "ADB vẫn đang connected sau lệnh update.")
        return True

    connected, _devices = wait_for_update_adb(
        config,
        ADB_UPDATE_FINAL_RECONNECT_SECONDS,
        log=log,
        progress=progress,
        fraction=0.96,
        reason="ADB mất sau khi ECU nhận lệnh update",
    )
    return connected


def run_adb_update(config, update_path, log=None, progress=None):
    validation_error = validate_update_bin_path(update_path)
    if validation_error:
        emit_progress(progress, 0.0, "File update không hợp lệ")
        return {"ok": False, "message": validation_error}

    target = adb_target(config)
    file_size = os.path.getsize(update_path)

    emit_progress(progress, 0.02, "Chuẩn bị update ADB")
    emit_log(log, "Bắt đầu Update ADB.")
    emit_log(log, f"ADB target: {target}")
    emit_log(log, f"File update: {update_path}")
    emit_log(log, f"Size: {human_size(file_size)}")

    emit_progress(progress, 0.06, "Kiểm tra ADB")
    state, devices_output = wait_for_adb_device(
        config,
        wait_seconds=10.0,
        log=log,
        purpose="adb-update-precheck",
    )
    if devices_output:
        emit_log(log, devices_output)
    if state != "device":
        return {
            "ok": False,
            "message": f"ADB chưa sẵn sàng để update. State: {state or 'not connected'}",
        }

    code, id_output = run(["adb", "-s", target, "shell", "id"], timeout=5, purpose="adb-update-id")
    id_output = clean_command_output(id_output)
    if id_output:
        emit_log(log, f"id hiện tại: {id_output}")
    if code != 0:
        return {"ok": False, "message": f"Không chạy được adb shell id.\n{id_output}"}

    pushed, code, output = push_with_reconnect(config, update_path, file_size, log=log, progress=progress)
    if not pushed:
        return {"ok": False, "message": f"Push file update lỗi ({code}).\n{output}".strip()}

    verified, code, output = verify_with_reconnect(
        config,
        file_size,
        log=log,
        progress=progress,
    )
    if not verified:
        return {"ok": False, "message": f"Kiểm tra/sync file update lỗi ({code}).\n{output}".strip()}

    emit_progress(progress, 0.9, "Chạy cmdtool update cpu")
    emit_log(log, "Chạy cmdtool: update cpu")
    update_ok, code, output = run_cmdtool_update_cpu(
        config,
        log=log,
        purpose_prefix="adb-update",
        retry_transient=False,
    )
    if not update_ok:
        if failed_because_adb_missing(
            config,
            output,
            log=log,
            purpose="adb-update-cmdtool-failure-probe",
        ):
            reconnected = wait_after_update_command(config, log=log, progress=progress)
            reconnect_message = (
                "ADB đã reconnect, nhưng app chưa thấy cmdtool status=0."
                if reconnected
                else "ADB chưa reconnect trong thời gian chờ."
            )
            return {
                "ok": False,
                "message": (
                    "ADB mất trong lúc chạy cmdtool update cpu trước khi app nhận được status=0.\n"
                    f"{reconnect_message}\n"
                    "App không tự chạy lại firmware command để tránh update lặp; kiểm tra SW version rồi quyết định retry."
                ),
            }
        return {"ok": False, "message": f"cmdtool update cpu chưa báo thành công ({code}).\n{output}"}

    reconnected = wait_after_update_command(config, log=log, progress=progress)
    emit_progress(progress, 1.0, "Hoàn tất lệnh update ADB")
    reconnect_message = (
        "ADB đã sẵn sàng sau lệnh update."
        if reconnected
        else (
            "ADB chưa reconnect trong thời gian chờ sau khi ECU nhận lệnh update. "
            "Không tự chạy lại update để tránh lặp firmware command."
        )
    )
    return {
        "ok": True,
        "message": (
            "Update ADB đã gửi lệnh thành công.\n"
            f"File: {update_path}\n"
            f"Remote: {ADB_UPDATE_REMOTE_PATH}\n"
            "cmdtool update cpu đã báo command status = 0.\n"
            f"{reconnect_message}"
        ),
    }
