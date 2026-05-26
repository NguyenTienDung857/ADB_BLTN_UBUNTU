import http.server
import posixpath
import re
import shutil
import subprocess
import threading
import time

from ..adb.executor import adb_env
from ..config import adb_target
from ..constants import VIDEO_STREAM_CHUNK_SIZE
from ..host_platform import IS_WINDOWS, find_executable, resolve_command
from ..processes import (
    cleanup_previous_processes,
    new_process_group_kwargs,
    register_process,
    terminate_popen,
    unregister_process,
)
from .adb_device import ensure_adb_device
from .files import human_size, is_video_path, normalize_remote_path, quote_remote_path, remote_file_size


def mpv_low_latency_command(remote_path, source="-"):
    mpv_path = find_executable("mpv") or shutil.which("mpv")
    if not mpv_path:
        return None

    title = f"ECU Video - {posixpath.basename(normalize_remote_path(remote_path))}"
    return [
        mpv_path,
        "--force-window=yes",
        "--profile=low-latency",
        "--cache=no",
        "--demuxer-readahead-secs=0.1",
        f"--title={title}",
        "--",
        source,
    ]


def video_content_type(remote_path):
    lower = str(remote_path or "").lower()
    if lower.endswith((".mp4", ".m4v")):
        return "video/mp4"
    if lower.endswith(".mkv"):
        return "video/x-matroska"
    if lower.endswith(".webm"):
        return "video/webm"
    if lower.endswith(".ts"):
        return "video/mp2t"
    return "application/octet-stream"


def parse_http_range(range_header, size):
    if not range_header:
        return 200, 0, max(size - 1, 0)

    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
    if not match:
        return 200, 0, max(size - 1, 0)

    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return 200, 0, max(size - 1, 0)

    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            return 416, 0, 0
        start = max(size - suffix, 0)
        end = size - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1

    if start >= size or start < 0:
        return 416, 0, 0

    end = min(end, size - 1)
    if end < start:
        return 416, 0, 0
    return 206, start, end


class AdbRangeVideoServer:
    def __init__(self, config, remote_path, size):
        self.config = dict(config)
        self.remote_path = normalize_remote_path(remote_path)
        self.size = int(size)
        self.active_processes = set()
        self.lock = threading.Lock()
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), self.make_handler())
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        host, port = self.httpd.server_address
        self.url = f"http://{host}:{port}/video"

    def make_handler(self):
        owner = self

        class VideoRangeHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, _format, *_args):
                return

            def do_HEAD(self):
                self.send_range_headers(send_body=False)

            def do_GET(self):
                self.send_range_headers(send_body=True)

            def send_range_headers(self, send_body):
                if self.path.split("?", 1)[0] != "/video":
                    self.send_error(404)
                    return

                status, start, end = parse_http_range(self.headers.get("Range"), owner.size)
                if status == 416:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{owner.size}")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return

                length = end - start + 1 if owner.size else 0
                self.send_response(status)
                self.send_header("Content-Type", video_content_type(owner.remote_path))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{owner.size}")
                self.send_header("Connection", "close")
                self.end_headers()

                if send_body and length > 0:
                    owner.stream_range(self.wfile, start, length)

        return VideoRangeHandler

    def start(self):
        self.thread.start()

    def stop(self):
        with self.lock:
            processes = list(self.active_processes)
        for proc in processes:
            terminate_popen(proc)
        try:
            self.httpd.shutdown()
        except Exception:
            pass
        try:
            self.httpd.server_close()
        except Exception:
            pass

    def stream_range(self, output, start, length):
        command_text = (
            f"tail -c +{int(start) + 1} {quote_remote_path(self.remote_path)} 2>/dev/null "
            f"| head -c {int(length)}"
        )
        command = resolve_command(["adb", "-s", adb_target(self.config), "exec-out", "sh", "-c", command_text])
        proc = None
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=adb_env(),
                **new_process_group_kwargs(),
            )
            register_process(proc.pid, command, "video-stream-range-adb")
            with self.lock:
                self.active_processes.add(proc)

            remaining = int(length)
            while remaining > 0:
                chunk = proc.stdout.read(min(VIDEO_STREAM_CHUNK_SIZE, remaining))
                if not chunk:
                    break
                output.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            if proc:
                if proc.stdout:
                    try:
                        proc.stdout.close()
                    except OSError:
                        pass
                terminate_popen(proc)
                unregister_process(proc.pid)
                with self.lock:
                    self.active_processes.discard(proc)


def start_remote_video_stream(config, remote_path):
    normalized = normalize_remote_path(remote_path)
    if not is_video_path(normalized):
        return {
            "ok": False,
            "path": normalized,
            "message": f"Không nhận diện là file video: {normalized}",
            "processes": {},
        }

    if not (find_executable("mpv") or shutil.which("mpv")):
        return {
            "ok": False,
            "path": normalized,
            "message": (
                "Máy chưa có mpv nên chưa mở video trực tiếp được.\n"
                + (
                    "Trên Windows: đặt mpv.exe trong PATH hoặc trong thư mục tools của package."
                    if IS_WINDOWS
                    else "Cài bằng: sudo apt-get install -y mpv"
                )
            ),
            "processes": {},
        }

    state, devices_output = ensure_adb_device(config)
    if state != "device":
        return {
            "ok": False,
            "path": normalized,
            "message": (
                f"ADB chưa sẵn sàng cho {adb_target(config)}. State: {state or 'not connected'}\n"
                f"{devices_output}"
            ).strip(),
            "processes": {},
        }

    size, size_error = remote_file_size(config, normalized)
    if not size:
        return {
            "ok": False,
            "path": normalized,
            "message": (
                f"Không lấy được size hoặc file không còn tồn tại:\n{normalized}\n"
                f"{size_error}"
            ).strip(),
            "processes": {},
        }

    cleanup_previous_processes(include_current=True, purpose_prefixes=("video-stream",))
    range_server = None
    mpv_proc = None
    try:
        range_server = AdbRangeVideoServer(config, normalized, size)
        range_server.start()
        mpv_command = mpv_low_latency_command(normalized, source=range_server.url)

        mpv_proc = subprocess.Popen(
            mpv_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **new_process_group_kwargs(),
        )
        register_process(mpv_proc.pid, mpv_command, "video-stream-mpv")

        time.sleep(0.8)
        if mpv_proc.poll() is not None:
            range_server.stop()
            cleanup_previous_processes(include_current=True, purpose_prefixes=("video-stream",))
            return {
                "ok": False,
                "path": normalized,
                "message": (
                    "mpv đã thoát ngay sau khi mở stream range. File có thể lỗi, bị xóa, "
                    "hoặc không đọc được qua ADB."
                ),
                "processes": {},
            }

    except Exception as exc:
        if range_server:
            range_server.stop()
        cleanup_previous_processes(include_current=True, purpose_prefixes=("video-stream",))
        return {
            "ok": False,
            "path": normalized,
            "message": f"Không mở được video trực tiếp: {exc}",
            "processes": {},
        }

    return {
        "ok": True,
        "path": normalized,
        "message": (
            f"Đang stream trực tiếp qua ADB:\n{normalized}\n\n"
            f"Size: {human_size(size)}\n"
            f"URL local có hỗ trợ seek/range: {range_server.url}\n"
            "Backend chỉ đọc byte-range cần thiết từ ECU qua ADB, không tải toàn bộ file trước."
        ),
        "processes": {"player": mpv_proc},
        "server": range_server,
    }
