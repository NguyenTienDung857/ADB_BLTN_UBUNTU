# Adapter Status Architecture

## Mục tiêu

Dự án được tách theo 3 lớp chính:

1. UI layer: chỉ xử lý GTK, trạng thái nút, text hiển thị và điều phối worker thread.
2. Business/service layer: điều phối workflow ECU, ADB connect, Get Root, File Explorer, Log realtime, video stream.
3. ADB execution layer: chạy lệnh `adb`, `ip`, `ping`, quản lý process, timeout và cleanup.

UI không gọi `adb` hoặc `subprocess` trực tiếp. UI gọi service, service gọi executor.

## Structure

```text
.
├── adapter-status-ui                 # launcher mỏng, giữ tương thích desktop/script cũ
├── adapter_status/
│   ├── main.py                       # entrypoint Python
│   ├── constants.py                  # hằng số cấu hình, timeout, path, extension
│   ├── config.py                     # load/save config, sanitize interface, build ADB target
│   ├── processes.py                  # process registry, cleanup, terminate an toàn
│   ├── adb/
│   │   └── executor.py               # lớp chạy command/ADB có timeout và env ADB_VENDOR_KEYS
│   ├── services/
│   │   ├── adb_device.py             # helper device: adb state, shell, root check, device info
│   │   ├── connection.py             # configure IP, reconnect ADB, collect status
│   │   ├── root.py                   # Get Root, drop root, cmdtool update cpu, change_file
│   │   ├── files.py                  # remote path, ls parser, pull, preview text/image
│   │   ├── video.py                  # byte-range HTTP server và mpv stream qua ADB
│   │   ├── logs.py                   # journalctl -f qua ADB root
│   │   └── workspace.py              # tìm workdir và mở terminal
│   └── ui/
│       ├── gtk_app.py                # GTK window và event handlers
│       ├── widgets.py                # helper GTK widget/text view
│       └── help_text.py              # help text tiếng Việt
├── docs/
│   ├── ARCHITECTURE.md
│   ├── README_ADB.md
│   ├── command to show log.md
│   ├── how to check version.md
│   ├── hướng dẫn update file debug lấy quyền root.md
│   ├── báo cáo quét sâu built-in cam ADB.md
│   ├── adb.sh                       # script kết nối ADB hiện tại
│   ├── cpu_update.bin               # payload vận hành
│   ├── YOEUK_public.pem             # public key vận hành
│   └── docx/
│       ├── HUONG DAN UPDATE XE CO OEUK.docx
│       └── adb.docx
```

## Responsibility

`adapter-status-ui`
: Launcher shell/Python mỏng. Chỉ import `adapter_status.main.main()` để workflow cũ vẫn chạy.

`adapter_status/main.py`
: Tạo app GTK qua `adapter_status.ui.gtk_app.run()`.

`adapter_status/constants.py`
: Nơi duy nhất giữ timeout, path mặc định, extension, column index, regex và text mặc định.

`adapter_status/config.py`
: Load/save `~/.config/adapter-status/config.json`, sanitize tên interface và tạo `device_ip:adb_port`.

`adapter_status/processes.py`
: Theo dõi process do app mở, cleanup process treo, kill theo process group, chống kill nhầm process khác bằng `pid + start_time`.

`adapter_status/adb/executor.py`
: Boundary duy nhất cho command execution. Mọi lệnh `adb`, `ip`, `ping` đi qua `run()`, `run_binary()` hoặc `run_with_delayed_pty_input()`.

`adapter_status/services/adb_device.py`
: Helper business cấp device: `adb devices`, `adb shell`, root check, parse device version, cache device info có lock.

`adapter_status/services/connection.py`
: Workflow connect/status: cấu hình IP, reconnect ADB trong cửa sổ 60 giây, collect trạng thái UI.

`adapter_status/services/root.py`
: Workflow Get Root: validate debug bin, push payload, chạy `cmdtool update cpu`, chạy `change_file`, chờ reboot/root, và `adb unroot`.

`adapter_status/services/files.py`
: Logic File Explorer chỉ đọc: normalize path, parse `ls -la`, preview text, pull file, đọc ảnh.

`adapter_status/services/video.py`
: Stream video trực tiếp qua ADB bằng local HTTP range server và `mpv`, không tải toàn bộ file trước.

`adapter_status/services/logs.py`
: Mở/dừng process đọc `journalctl -f` qua ADB root.

`adapter_status/services/workspace.py`
: Tìm `adb.sh` ở root hoặc `docs/`, mở terminal có tracking env, và giữ thư mục làm việc chính là root project.

`adapter_status/ui/gtk_app.py`
: Chỉ quản lý GTK widget, event, thread worker và `GLib.idle_add()` để cập nhật UI từ main thread.

## Flow hoạt động

```text
User click button
    ↓
GTK handler trong ui/gtk_app.py
    ↓
Worker thread gọi service tương ứng
    ↓
services/* xử lý nghiệp vụ và gọi adb/executor.py
    ↓
executor chạy subprocess có timeout/process tracking
    ↓
service trả result/message
    ↓
GLib.idle_add cập nhật GTK main thread
```

Ví dụ `ADB Connect`:

```text
connect_adb()
    -> run_adb_reconnect()
    -> services.connection.adb_reconnect()
    -> configure_ip_commands(), ping, adb connect, adb devices
    -> executor.run()
    -> finish_action()
```

Ví dụ `Get Root`:

```text
choose_debug_file_for_root()
    -> run_get_root()
    -> services.root.get_root_with_debug_file()
    -> wait_for_adb_device()
    -> adb push debug bin
    -> cmdtool update cpu
    -> /home/adb/change_file
    -> wait_for_root_after_reboot()
```

## Thread-safe / async-safe

- GTK chỉ được cập nhật trong main thread qua `GLib.idle_add()`.
- Mỗi thao tác dài chạy trong `threading.Thread(..., daemon=True)`.
- `action_running`, `file_running`, `video_session_id`, `live_log_session_id` chặn thao tác chồng và bỏ result cũ.
- `processes.py` dùng `PROCESS_LOCK` khi đọc/ghi process registry.
- `adb_device.py` dùng lock cho cache device info.
- Executor luôn dùng timeout và process group để tránh treo ADB/subprocess.

## Skeleton API

```python
# adapter_status/adb/executor.py
def run(command: list[str], timeout: int = 2, purpose: str = "command") -> tuple[int, str]: ...
def run_binary(command: list[str], timeout: int, purpose: str = "command") -> tuple[int, bytes]: ...
def run_with_delayed_pty_input(command, input_text, prompt_text, completion_texts, timeout, purpose): ...
```

```python
# adapter_status/services/connection.py
def configure_ip(config: dict[str, str]) -> str: ...
def adb_reconnect(config: dict[str, str]) -> str: ...
def clean_reset(config: dict[str, str], include_current: bool = False) -> str: ...
def collect_status(config: dict[str, str]) -> dict: ...
```

```python
# adapter_status/services/root.py
def validate_debug_bin_path(path: str) -> str | None: ...
def get_root_with_debug_file(config: dict[str, str], debug_path: str, log=None) -> str: ...
def drop_adb_root(config: dict[str, str], log=None) -> str: ...
```

```python
# adapter_status/services/files.py
def list_remote_dir(config: dict[str, str], path: str) -> dict: ...
def read_remote_text_head(config: dict[str, str], path: str, limit: int) -> tuple[int, str]: ...
def pull_remote_file(config: dict[str, str], remote_path: str) -> tuple[int, str, str]: ...
def read_remote_image(config: dict[str, str], remote_path: str) -> dict: ...
```

```python
# adapter_status/services/video.py
def start_remote_video_stream(config: dict[str, str], remote_path: str) -> dict: ...
```

```python
# adapter_status/services/logs.py
def start_live_log_process(config: dict[str, str], filter_text: str = "") -> dict: ...
def terminate_live_log_process(proc) -> bool: ...
```

```python
# adapter_status/ui/gtk_app.py
class AdapterStatus(Gtk.Window):
    def refresh_async(self): ...
    def connect_adb(self, _button): ...
    def run_get_root(self, config, debug_path): ...
    def load_remote_dir(self, path, preserve_selection=False, quiet=False): ...
```

## Quy tắc mở rộng sau này

- Thêm workflow mới trong `services/`, không nhét vào `ui/gtk_app.py`.
- Nếu workflow cần chạy command, gọi `adapter_status.adb.executor`, không gọi `subprocess` trực tiếp trong UI.
- Object trả về service nên là `dict` hoặc dataclass có `ok/message/data`, để UI không phải biết chi tiết ADB.
- Text hiển thị cho operator giữ tiếng Việt.
- Với thao tác có thể mất nhiều thời gian, luôn chạy worker thread và trả UI bằng `GLib.idle_add()`.
