import glob
import os
import pty
import select
import signal
import subprocess
import time

from ..constants import FILE_EXPLORER_TIMEOUT
from ..processes import (
    command_name,
    command_text,
    clean_command_output,
    kill_tracked_record,
    register_new_adb_servers,
    register_process,
    tracked_adb_server_pids,
    unregister_process,
)

def adb_env():
    env = os.environ.copy()
    keys = []
    default_key = os.path.expanduser("~/.android/adbkey")
    if os.path.exists(default_key):
        keys.append(default_key)
    keys.extend(sorted(glob.glob(os.path.expanduser("~/.android/*/adbkey"))))
    if keys:
        env["ADB_VENDOR_KEYS"] = ":".join(keys)
    return env


def run(command, timeout=2, purpose="command"):
    is_adb_command = command_name(command) == "adb"
    adb_servers_before = tracked_adb_server_pids() if is_adb_command else set()
    proc = None
    record = None
    try:
        proc = subprocess.Popen(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=adb_env(),
            start_new_session=True,
        )
        record = register_process(proc.pid, command, purpose)
        output, _stderr = proc.communicate(timeout=timeout)
        return proc.returncode, (output or "").strip()
    except subprocess.TimeoutExpired:
        if record:
            kill_tracked_record(record)
        elif proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                pass
        try:
            output, _stderr = proc.communicate(timeout=1)
        except Exception:
            output = ""
        text = (output or "").strip()
        if text:
            text += "\n"
        return 124, f"{text}Command timeout: {command_text(command)}"
    except Exception as exc:
        return 1, str(exc)
    finally:
        if is_adb_command:
            register_new_adb_servers(adb_servers_before)
        if proc:
            unregister_process(proc.pid)


def run_with_input(command, input_text, timeout=10, purpose="command"):
    is_adb_command = command_name(command) == "adb"
    adb_servers_before = tracked_adb_server_pids() if is_adb_command else set()
    proc = None
    record = None
    try:
        proc = subprocess.Popen(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=adb_env(),
            start_new_session=True,
        )
        record = register_process(proc.pid, command, purpose)
        output, _stderr = proc.communicate(input=input_text, timeout=timeout)
        return proc.returncode, clean_command_output(output)
    except subprocess.TimeoutExpired:
        if record:
            kill_tracked_record(record)
        elif proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                pass
        try:
            output, _stderr = proc.communicate(timeout=1)
        except Exception:
            output = ""
        text = clean_command_output(output)
        if text:
            text += "\n"
        return 124, f"{text}Command timeout: {command_text(command)}"
    except Exception as exc:
        return 1, str(exc)
    finally:
        if is_adb_command:
            register_new_adb_servers(adb_servers_before)
        if proc:
            unregister_process(proc.pid)


def run_streaming(
    command,
    timeout=60,
    purpose="command",
    on_output=None,
    on_tick=None,
    tick_interval=1.0,
):
    is_adb_command = command_name(command) == "adb"
    adb_servers_before = tracked_adb_server_pids() if is_adb_command else set()
    proc = None
    record = None
    chunks = []
    start_time = time.monotonic()
    deadline = start_time + timeout if timeout else None
    last_tick = start_time
    timed_out = False

    def emit_output(text):
        if on_output and text:
            on_output(text)

    def emit_tick(now):
        if on_tick:
            on_tick(now - start_time)

    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=adb_env(),
            start_new_session=True,
        )
        record = register_process(proc.pid, command, purpose)
        stdout_fd = proc.stdout.fileno()
        os.set_blocking(stdout_fd, False)

        while True:
            now = time.monotonic()
            if deadline and now >= deadline and proc.poll() is None:
                timed_out = True
                if record:
                    kill_tracked_record(record)
                else:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except OSError:
                        pass
                break

            if on_tick and now - last_tick >= tick_interval:
                emit_tick(now)
                last_tick = now

            wait_time = 0.1
            if deadline:
                wait_time = min(wait_time, max(0.01, deadline - now))
            readable, _writable, _error = select.select([stdout_fd], [], [], wait_time)
            if readable:
                while True:
                    try:
                        data = os.read(stdout_fd, 4096)
                    except BlockingIOError:
                        break
                    except OSError:
                        data = b""
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace")
                    chunks.append(text)
                    emit_output(text)

            if proc.poll() is not None:
                drain_deadline = time.monotonic() + 0.5
                while time.monotonic() < drain_deadline:
                    readable, _writable, _error = select.select([stdout_fd], [], [], 0.05)
                    if not readable:
                        break
                    try:
                        data = os.read(stdout_fd, 4096)
                    except (BlockingIOError, OSError):
                        break
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace")
                    chunks.append(text)
                    emit_output(text)
                break

        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

        output = clean_command_output("".join(chunks))
        if timed_out:
            if output:
                output += "\n"
            output += f"Command timeout: {command_text(command)}"
            return 124, output

        return proc.returncode if proc.returncode is not None else 0, output
    except Exception as exc:
        return 1, str(exc)
    finally:
        if is_adb_command:
            register_new_adb_servers(adb_servers_before)
        if proc:
            unregister_process(proc.pid)


def run_with_delayed_pty_input(
    command,
    input_text,
    prompt_text,
    completion_texts,
    timeout=30,
    purpose="command",
):
    is_adb_command = command_name(command) == "adb"
    adb_servers_before = tracked_adb_server_pids() if is_adb_command else set()
    master_fd = None
    slave_fd = None
    proc = None
    record = None
    sent_input = False
    saw_completion = False
    timed_out = False
    chunks = []
    completion_markers = tuple(str(item).lower() for item in completion_texts or ())
    deadline = time.monotonic() + timeout

    try:
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=adb_env(),
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = None
        os.set_blocking(master_fd, False)
        record = register_process(proc.pid, command, purpose)

        while time.monotonic() < deadline:
            wait_time = min(0.25, max(0.01, deadline - time.monotonic()))
            readable, _writable, _error = select.select([master_fd], [], [], wait_time)
            if readable:
                while True:
                    try:
                        data = os.read(master_fd, 4096)
                    except BlockingIOError:
                        break
                    except OSError:
                        data = b""
                    if not data:
                        break
                    chunks.append(data.decode("utf-8", errors="replace"))

            raw_output = "".join(chunks)
            cleaned_output = clean_command_output(raw_output)
            cleaned_lower = cleaned_output.lower()

            if not sent_input and (not prompt_text or prompt_text in raw_output or prompt_text in cleaned_output):
                os.write(master_fd, input_text.encode("utf-8", errors="replace"))
                sent_input = True
            elif sent_input and completion_markers and any(
                marker in cleaned_lower for marker in completion_markers
            ):
                saw_completion = True
                try:
                    os.write(master_fd, b"\x03")
                except OSError:
                    pass
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                break

            if proc.poll() is not None:
                break
        else:
            timed_out = True

        drain_deadline = time.monotonic() + 1.0
        while time.monotonic() < drain_deadline:
            readable, _writable, _error = select.select([master_fd], [], [], 0.05)
            if not readable:
                if proc.poll() is not None:
                    break
                continue
            try:
                data = os.read(master_fd, 4096)
            except (BlockingIOError, OSError):
                break
            if not data:
                break
            chunks.append(data.decode("utf-8", errors="replace"))

        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

        output = clean_command_output("".join(chunks))
        if timed_out and not saw_completion:
            if output:
                output += "\n"
            output += f"Command timeout: {command_text(command)}"
            return 124, output
        return_code = proc.returncode if proc.returncode is not None else 0
        if saw_completion and return_code < 0:
            return_code = 0
        return return_code, output
    except Exception as exc:
        return 1, str(exc)
    finally:
        if slave_fd is not None:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass
        if is_adb_command:
            register_new_adb_servers(adb_servers_before)
        if proc:
            unregister_process(proc.pid)


def run_binary(command, timeout=FILE_EXPLORER_TIMEOUT, purpose="command"):
    is_adb_command = command_name(command) == "adb"
    adb_servers_before = tracked_adb_server_pids() if is_adb_command else set()
    proc = None
    record = None
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=adb_env(),
            start_new_session=True,
        )
        record = register_process(proc.pid, command, purpose)
        output, stderr = proc.communicate(timeout=timeout)
        if proc.returncode == 0:
            return proc.returncode, output or b""
        return proc.returncode, (stderr or output or b"")
    except subprocess.TimeoutExpired:
        if record:
            kill_tracked_record(record)
        elif proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                pass
        try:
            output, stderr = proc.communicate(timeout=1)
        except Exception:
            output, stderr = b"", b""
        return 124, (stderr or output or b"") + b"\nCommand timeout"
    except Exception as exc:
        return 1, str(exc).encode("utf-8", errors="replace")
    finally:
        if is_adb_command:
            register_new_adb_servers(adb_servers_before)
        if proc:
            unregister_process(proc.pid)
