import os

from ..adb.executor import run_streaming
from ..config import adb_target
from ..constants import OEUK_REMOTE_PATH
from ..processes import clean_command_output
from .adb_device import ensure_adb_root_device
from .files import human_size


PUBLIC_KEY_BEGIN = "-----BEGIN PUBLIC KEY-----"
PUBLIC_KEY_END = "-----END PUBLIC KEY-----"


def validate_pem_path(path):
    if not path:
        return "Chưa chọn file PEM."
    if not os.path.isfile(path):
        return f"Không thấy file: {path}"
    if not path.lower().endswith(".pem"):
        return "File được chọn không phải .pem."
    if os.path.getsize(path) <= 0:
        return f"File PEM rỗng: {path}"
    return None


def emit_log(log, message):
    text = clean_command_output(str(message or ""))
    if text and log:
        log(text)


def run_streamed_adb(command, timeout, purpose, log=None):
    def on_output(chunk):
        text = clean_command_output(str(chunk or "").replace("\r", "\n"))
        if text:
            emit_log(log, text)

    return run_streaming(
        command,
        timeout=timeout,
        purpose=purpose,
        on_output=on_output,
        tick_interval=1.0,
    )


def failure_result(reason):
    return {
        "ok": False,
        "message": (
            "================================\n"
            "GET OEUK FAILED\n"
            "===============\n\n"
            f"Reason: {reason}"
        ),
    }


def success_result(pem_path):
    return {
        "ok": True,
        "message": (
            "================================\n"
            "GET OEUK SUCCESS\n"
            "================\n\n"
            f"PEM File: {os.path.basename(pem_path)}\n\n"
            "Target:\n"
            f"{OEUK_REMOTE_PATH}\n\n"
            "Verify:\n"
            "PUBLIC KEY detected\n\n"
            "Result:\n"
            "SUCCESS"
        ),
    }


def get_oeuk_with_pem(config, pem_path, log=None):
    validation_error = validate_pem_path(pem_path)
    if validation_error:
        return failure_result(validation_error)

    ok, root_message = ensure_adb_root_device(config, purpose="get-oeuk-root-check")
    if not ok:
        return failure_result(root_message)

    target = adb_target(config)
    pem_size = os.path.getsize(pem_path)

    emit_log(log, "Bắt đầu Get OEUK.")
    emit_log(log, f"ADB target: {target}")
    emit_log(log, f"PEM file: {pem_path}")
    emit_log(log, f"Size: {human_size(pem_size)}")

    emit_log(log, "Remount / sang read-write.")
    code, output = run_streamed_adb(
        ["adb", "-s", target, "shell", "mount -o rw,remount /"],
        timeout=20,
        purpose="get-oeuk-remount",
        log=log,
    )
    output = clean_command_output(output)
    if code != 0:
        return failure_result(f"Remount / lỗi ({code}).\n{output}".strip())

    emit_log(log, f"Push PEM vào {OEUK_REMOTE_PATH}.")
    code, output = run_streamed_adb(
        ["adb", "-s", target, "push", pem_path, OEUK_REMOTE_PATH],
        timeout=60,
        purpose="get-oeuk-push",
        log=log,
    )
    output = clean_command_output(output)
    if code != 0:
        return failure_result(f"Push PEM lỗi ({code}).\n{output}".strip())

    emit_log(log, "Verify nội dung public key trên thiết bị.")
    code, output = run_streamed_adb(
        ["adb", "-s", target, "shell", f"cat {OEUK_REMOTE_PATH}"],
        timeout=15,
        purpose="get-oeuk-verify",
        log=None,
    )
    output = clean_command_output(output)
    if code != 0:
        return failure_result(f"Verify bằng cat lỗi ({code}).\n{output}".strip())
    if PUBLIC_KEY_BEGIN not in output or PUBLIC_KEY_END not in output:
        return failure_result(
            "Không thấy marker PUBLIC KEY trong file remote.\n"
            f"Output verify:\n{output}"
        )

    emit_log(log, "PUBLIC KEY detected.")
    return success_result(pem_path)
