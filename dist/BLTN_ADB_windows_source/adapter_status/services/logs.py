import subprocess

from ..adb.executor import adb_env
from ..config import adb_target
from ..constants import LIVE_LOG_COMMAND
from ..host_platform import resolve_command
from ..processes import (
    command_text,
    new_process_group_kwargs,
    register_new_adb_servers,
    register_process,
    terminate_popen,
    tracked_adb_server_pids,
    unregister_process,
)
from .adb_device import ensure_adb_root_device


def live_log_shell_command(_filter_text=""):
    return LIVE_LOG_COMMAND


def start_live_log_process(config, filter_text=""):
    ok, message = ensure_adb_root_device(config, purpose="live-log-root-check")
    if not ok:
        return {"ok": False, "message": message}

    target = adb_target(config)
    shell_command = live_log_shell_command(filter_text)
    command = resolve_command(["adb", "-s", target, "shell", shell_command])
    adb_servers_before = tracked_adb_server_pids()
    try:
        proc = subprocess.Popen(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=adb_env(),
            **new_process_group_kwargs(),
        )
        register_process(proc.pid, command, "live-log")
        register_new_adb_servers(adb_servers_before)
    except Exception as exc:
        return {"ok": False, "message": str(exc)}

    return {
        "ok": True,
        "process": proc,
        "command_display": command_text(command),
        "source_label": LIVE_LOG_COMMAND,
    }


def terminate_live_log_process(proc):
    if not proc:
        return False
    try:
        return terminate_popen(proc)
    finally:
        unregister_live_log_process(proc)


def unregister_live_log_process(proc):
    if proc:
        unregister_process(proc.pid)
    
