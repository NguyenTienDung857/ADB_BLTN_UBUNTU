import json
import os
import signal
import subprocess
import threading
import time

from .constants import ANSI_ESCAPE_PATTERN, APP_RUN_ID, CACHE_DIR, PROCESS_FILE
from .host_platform import IS_WINDOWS, command_basename

try:
    import psutil
except ImportError:  # pragma: no cover - optional Windows packaging dependency
    psutil = None
    PSUTIL_ERRORS = (Exception,)
else:
    PSUTIL_ERRORS = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error)

PROCESS_LOCK = threading.Lock()

def command_name(command):
    return command_basename(command)


def new_process_group_kwargs():
    if IS_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def command_text(command):
    return " ".join(str(part) for part in command)


def clean_command_output(text):
    cleaned = ANSI_ESCAPE_PATTERN.sub("", text or "")
    cleaned = cleaned.replace("\r", "\n")
    lines = [line.rstrip() for line in cleaned.splitlines()]
    compact = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compact.append(line)
        previous_blank = blank
    return "\n".join(compact).strip()


def proc_cmdline(pid):
    if IS_WINDOWS:
        if not psutil:
            return ""
        try:
            return " ".join(psutil.Process(pid).cmdline())
        except PSUTIL_ERRORS:
            return ""

    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            data = handle.read()
    except OSError:
        return ""
    return data.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()


def proc_argv(pid):
    if IS_WINDOWS:
        if not psutil:
            return []
        try:
            return psutil.Process(pid).cmdline()
        except PSUTIL_ERRORS:
            return []

    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            data = handle.read()
    except OSError:
        return []
    return [
        item.decode("utf-8", errors="replace")
        for item in data.split(b"\0")
        if item
    ]


def proc_start_time(pid):
    if IS_WINDOWS:
        if not psutil:
            return None
        try:
            return str(psutil.Process(pid).create_time())
        except PSUTIL_ERRORS:
            return None

    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as handle:
            data = handle.read()
    except OSError:
        return None

    marker = data.rfind(")")
    if marker < 0:
        return None
    fields = data[marker + 2 :].split()
    if len(fields) <= 19:
        return None
    return fields[19]


def process_exists(pid, start_time=None):
    current_start = proc_start_time(pid)
    if not current_start:
        return False
    return start_time is None or str(start_time) == current_start


def read_process_records():
    try:
        with open(PROCESS_FILE, "r", encoding="utf-8") as handle:
            records = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    return records if isinstance(records, list) else []


def write_process_records(records):
    temp_path = f"{PROCESS_FILE}.{os.getpid()}.tmp"
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2, sort_keys=True)
        os.replace(temp_path, PROCESS_FILE)
    except OSError:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def record_matches_process(record):
    try:
        pid = int(record.get("pid", 0))
    except (TypeError, ValueError):
        return False
    start_time = record.get("start_time")
    return pid > 1 and process_exists(pid, start_time)


def register_process(pid, command, purpose):
    start_time = proc_start_time(pid)
    if not start_time:
        return None
    try:
        pgid = pid if IS_WINDOWS else os.getpgid(pid)
    except OSError:
        pgid = pid

    record = {
        "pid": int(pid),
        "pgid": int(pgid),
        "start_time": start_time,
        "command": command_text(command),
        "purpose": purpose,
        "owner_pid": os.getpid(),
        "owner_run": APP_RUN_ID,
        "created_at": time.time(),
    }

    with PROCESS_LOCK:
        records = [item for item in read_process_records() if record_matches_process(item)]
        already_recorded = any(
            item.get("pid") == record["pid"] and item.get("start_time") == record["start_time"]
            for item in records
        )
        if not already_recorded:
            records.append(record)
            write_process_records(records)
    return record


def unregister_process(pid):
    with PROCESS_LOCK:
        records = [
            item
            for item in read_process_records()
            if record_matches_process(item)
            and not (item.get("pid") == pid and item.get("owner_run") == APP_RUN_ID)
        ]
        write_process_records(records)


def tracked_adb_server_pids():
    pids = set()
    if IS_WINDOWS:
        if not psutil:
            return pids
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or [])
            except PSUTIL_ERRORS:
                continue
            if "adb" in cmdline.lower() and "fork-server" in cmdline and " server" in f" {cmdline} ":
                pids.add(int(proc.info["pid"]))
        return pids

    current_uid = os.getuid()
    try:
        entries = os.listdir("/proc")
    except OSError:
        return pids

    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            if os.stat(f"/proc/{pid}").st_uid != current_uid:
                continue
        except OSError:
            continue
        cmdline = proc_cmdline(pid)
        if "adb" in cmdline and "fork-server" in cmdline and " server" in f" {cmdline} ":
            pids.add(pid)
    return pids


def register_new_adb_servers(existing_pids):
    for pid in tracked_adb_server_pids() - set(existing_pids):
        register_process(pid, ["adb", "fork-server", "server"], "adb-server")


def kill_tracked_record(record, grace_seconds=0.35):
    try:
        pid = int(record.get("pid", 0))
    except (TypeError, ValueError, OSError):
        return False

    if IS_WINDOWS:
        if pid <= 1 or pid == os.getpid() or not record_matches_process(record):
            return False
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
            return True
        except Exception:
            try:
                if psutil:
                    psutil.Process(pid).kill()
                    return True
            except PSUTIL_ERRORS:
                pass
            return False

    try:
        pgid = int(record.get("pgid", 0)) or os.getpgid(pid)
    except (TypeError, ValueError, OSError):
        return False

    if pid <= 1 or pgid <= 1 or pid == os.getpid() or pgid == os.getpgrp():
        return False
    if not record_matches_process(record):
        return False

    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not record_matches_process(record):
            return True
        time.sleep(0.05)

    if record_matches_process(record):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return True


def live_process_record(pid, purpose):
    start_time = proc_start_time(pid)
    if not start_time:
        return None
    try:
        pgid = pid if IS_WINDOWS else os.getpgid(pid)
    except OSError:
        pgid = pid
    return {
        "pid": int(pid),
        "pgid": int(pgid),
        "start_time": start_time,
        "command": proc_cmdline(pid),
        "purpose": purpose,
        "owner_pid": os.getpid(),
        "owner_run": APP_RUN_ID,
        "created_at": time.time(),
    }


def adb_process_purpose(argv, target):
    if not argv or command_name(argv) != "adb":
        return ""
    if "fork-server" in argv and "server" in argv:
        return "adb-server"

    action = argv[1] if len(argv) > 1 else ""
    if action in {"connect", "disconnect", "devices", "kill-server", "start-server"}:
        return f"adb-{action}"

    joined = "\0".join(argv)
    if target and target in joined:
        return "adb-target-client"

    return ""


def kill_adb_processes_for_reconnect(target):
    killed = []
    if IS_WINDOWS:
        if not psutil:
            return killed
        for proc in psutil.process_iter(["pid", "cmdline"]):
            pid = int(proc.info.get("pid") or 0)
            if pid <= 1 or pid == os.getpid():
                continue
            try:
                argv = proc.info.get("cmdline") or []
            except PSUTIL_ERRORS:
                continue
            purpose = adb_process_purpose(argv, target)
            if not purpose:
                continue

            record = live_process_record(pid, purpose)
            if record and kill_tracked_record(record):
                killed.append(record)

        with PROCESS_LOCK:
            remaining = [
                item
                for item in read_process_records()
                if record_matches_process(item)
                and item.get("pid") not in {record["pid"] for record in killed}
            ]
            write_process_records(remaining)
        return killed

    current_uid = os.getuid()
    try:
        entries = os.listdir("/proc")
    except OSError:
        return killed

    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid <= 1 or pid == os.getpid():
            continue
        try:
            if os.stat(f"/proc/{pid}").st_uid != current_uid:
                continue
        except OSError:
            continue

        argv = proc_argv(pid)
        purpose = adb_process_purpose(argv, target)
        if not purpose:
            continue

        record = live_process_record(pid, purpose)
        if record and kill_tracked_record(record):
            killed.append(record)

    with PROCESS_LOCK:
        remaining = [
            item
            for item in read_process_records()
            if record_matches_process(item)
            and item.get("pid") not in {record["pid"] for record in killed}
        ]
        write_process_records(remaining)
    return killed


def cleanup_previous_processes(include_current=False, purpose_prefixes=None):
    killed = []
    killed_keys = set()
    with PROCESS_LOCK:
        records = read_process_records()

    for record in records:
        if not include_current and record.get("owner_run") == APP_RUN_ID:
            continue
        purpose = str(record.get("purpose", ""))
        if purpose_prefixes and not any(purpose.startswith(prefix) for prefix in purpose_prefixes):
            continue
        if not record_matches_process(record):
            continue
        if kill_tracked_record(record):
            killed.append(record)
            killed_keys.add((record.get("pid"), record.get("start_time")))

    with PROCESS_LOCK:
        remaining = [
            item
            for item in read_process_records()
            if record_matches_process(item)
            and (item.get("pid"), item.get("start_time")) not in killed_keys
        ]
        write_process_records(remaining)
    return killed



def terminate_popen(proc, grace_seconds=0.5):
    if not proc or proc.poll() is not None:
        return False
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(1, int(grace_seconds) + 2),
            )
        except Exception:
            try:
                proc.terminate()
            except OSError:
                return False

        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return True
            time.sleep(0.05)
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        return True

    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = proc.pid

    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        try:
            proc.terminate()
        except OSError:
            return False

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return True
        time.sleep(0.05)

    if proc.poll() is None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
    return True
