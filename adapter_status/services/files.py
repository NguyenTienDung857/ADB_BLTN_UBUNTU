import os
import posixpath
import re
import shlex
import time

from ..adb.executor import run, run_binary
from ..config import adb_target
from ..constants import (
    DATABASE_EXTENSIONS,
    FILE_EXPLORER_TIMEOUT,
    IMAGE_EXTENSIONS,
    IMAGE_PREVIEW_MAX_BYTES,
    REMOTE_PREVIEW_LIMIT,
    TEXT_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from .adb_device import adb_shell, ensure_adb_device
from .workspace import adb_workdir

def normalize_remote_path(path, base_path="/"):
    text = str(path or "").strip()
    if not text:
        text = "/"
    if not text.startswith("/"):
        text = posixpath.join(base_path or "/", text)
    normalized = posixpath.normpath(text)
    return "/" if normalized in ("", ".") else normalized


def remote_parent(path):
    normalized = normalize_remote_path(path)
    if normalized == "/":
        return "/"
    parent = posixpath.dirname(normalized.rstrip("/"))
    return parent or "/"


def remote_child_path(parent_path, child_name):
    return normalize_remote_path(posixpath.join(parent_path, child_name))


def quote_remote_path(path):
    return shlex.quote(normalize_remote_path(path))


def human_size(size):
    try:
        value = int(size)
    except (TypeError, ValueError):
        return str(size or "")
    units = ("B", "KB", "MB", "GB")
    current = float(value)
    for unit in units:
        if current < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(current)} {unit}"
            return f"{current:.1f} {unit}"
        current /= 1024
    return f"{value} B"


def remote_item_kind(permissions):
    marker = permissions[0] if permissions else "-"
    if marker == "d":
        return "Thư mục"
    if marker == "l":
        return "Liên kết"
    if marker == "c":
        return "Char device"
    if marker == "b":
        return "Block device"
    if marker == "s":
        return "Socket"
    if marker == "p":
        return "Pipe"
    return "File"


def parse_ls_line(line, parent_path):
    if not line or line.startswith("total "):
        return None

    parts = line.split(None, 7)
    if len(parts) < 8:
        return None

    permissions = parts[0]
    owner = parts[2]
    group = parts[3]
    size_text = parts[4]

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[5]) and re.fullmatch(
        r"\d{2}:\d{2}(?::\d{2})?", parts[6]
    ):
        modified = " ".join(parts[5:7])
        name = parts[7]
    else:
        gnu_parts = line.split(None, 8)
        if len(gnu_parts) < 9:
            return None
        modified = " ".join(gnu_parts[5:8])
        name = gnu_parts[8]

    path_name = name
    link_target = ""
    if permissions.startswith("l") and " -> " in name:
        path_name, link_target = name.split(" -> ", 1)

    if path_name in (".", ".."):
        return None

    try:
        size_value = int(size_text)
    except ValueError:
        size_value = 0

    full_path = remote_child_path(parent_path, path_name)
    kind = remote_item_kind(permissions)
    return {
        "name": name,
        "path_name": path_name,
        "path": full_path,
        "kind": kind,
        "permissions": permissions,
        "owner": owner,
        "group": group,
        "size": size_value,
        "size_text": human_size(size_value),
        "modified": modified,
        "is_dir": permissions.startswith("d"),
        "is_link": permissions.startswith("l"),
        "link_target": link_target,
    }


def parse_ls_output(output, parent_path):
    entries = []
    for line in (output or "").splitlines():
        item = parse_ls_line(line.rstrip(), parent_path)
        if item:
            entries.append(item)
    entries.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))
    return entries


def list_remote_dir(config, path):
    normalized = normalize_remote_path(path)
    state, devices_output = ensure_adb_device(config)
    if state != "device":
        return {
            "ok": False,
            "path": normalized,
            "entries": [],
            "message": (
                f"ADB chưa sẵn sàng cho {adb_target(config)}. State: {state or 'not connected'}\n"
                f"{devices_output}"
            ).strip(),
        }

    command = f"LC_ALL=C ls -la {quote_remote_path(normalized)}"
    code, output = adb_shell(config, command, timeout=FILE_EXPLORER_TIMEOUT)
    if code != 0:
        return {
            "ok": False,
            "path": normalized,
            "entries": [],
            "message": output or f"Không đọc được thư mục: {normalized}",
        }

    return {
        "ok": True,
        "path": normalized,
        "entries": parse_ls_output(output, normalized),
        "message": output,
    }


def read_remote_text_head(config, path, limit=REMOTE_PREVIEW_LIMIT):
    normalized = normalize_remote_path(path)
    command = (
        f"if [ -f {quote_remote_path(normalized)} ]; then "
        f"head -c {int(limit)} {quote_remote_path(normalized)}; "
        "else echo 'Không phải file thường.'; exit 1; fi"
    )
    return adb_shell(config, command, timeout=FILE_EXPLORER_TIMEOUT, purpose="file-preview")


def local_pull_path(remote_path):
    root = os.path.join(adb_workdir(), "ecu-files")
    normalized = normalize_remote_path(remote_path)
    parts = [part for part in normalized.lstrip("/").split("/") if part and part not in (".", "..")]
    if not parts:
        parts = ["root"]
    return os.path.join(root, *parts)


def pull_remote_file(config, remote_path):
    destination = local_pull_path(remote_path)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    code, output = run(
        ["adb", "-s", adb_target(config), "pull", normalize_remote_path(remote_path), destination],
        timeout=120,
        purpose="file-pull",
    )
    if code == 0:
        output = (output + "\n" if output else "") + f"Đã lưu: {destination}"
    return code, output, destination


def is_image_path(path):
    lower = str(path or "").lower()
    return any(lower.endswith(extension) for extension in IMAGE_EXTENSIONS)


def read_remote_binary_file(config, remote_path, timeout=FILE_EXPLORER_TIMEOUT):
    normalized = normalize_remote_path(remote_path)
    command = [
        "adb",
        "-s",
        adb_target(config),
        "exec-out",
        "sh",
        "-c",
        f"cat {quote_remote_path(normalized)}",
    ]
    return run_binary(command, timeout=timeout, purpose="file-binary-read")


def read_remote_image(config, remote_path):
    normalized = normalize_remote_path(remote_path)
    if not is_image_path(normalized):
        return {
            "ok": False,
            "path": normalized,
            "data": b"",
            "message": f"Không nhận diện là file ảnh: {normalized}",
        }

    state, devices_output = ensure_adb_device(config)
    if state != "device":
        return {
            "ok": False,
            "path": normalized,
            "data": b"",
            "message": (
                f"ADB chưa sẵn sàng cho {adb_target(config)}. State: {state or 'not connected'}\n"
                f"{devices_output}"
            ).strip(),
        }

    size, size_error = remote_file_size(config, normalized)
    if not size:
        return {
            "ok": False,
            "path": normalized,
            "data": b"",
            "message": (
                f"Không lấy được size hoặc file không còn tồn tại:\n{normalized}\n"
                f"{size_error}"
            ).strip(),
        }
    if size > IMAGE_PREVIEW_MAX_BYTES:
        return {
            "ok": False,
            "path": normalized,
            "data": b"",
            "message": (
                f"Ảnh quá lớn để preview trực tiếp: {human_size(size)}.\n"
                "Dùng Pull file về máy nếu cần xem bằng trình xem ảnh ngoài."
            ),
        }

    code, data = read_remote_binary_file(config, normalized, timeout=30)
    if code != 0:
        return {
            "ok": False,
            "path": normalized,
            "data": b"",
            "message": data.decode("utf-8", errors="replace") or f"Không đọc được ảnh: {normalized}",
        }
    return {
        "ok": True,
        "path": normalized,
        "data": data,
        "size": size,
        "message": f"Đã đọc ảnh: {normalized}",
    }


def is_video_path(path):
    lower = str(path or "").lower()
    return any(lower.endswith(extension) for extension in VIDEO_EXTENSIONS)


def is_text_path(path):
    lower = str(path or "").lower()
    return any(lower.endswith(extension) for extension in TEXT_EXTENSIONS)


def is_database_path(path):
    lower = str(path or "").lower()
    return any(lower.endswith(extension) for extension in DATABASE_EXTENSIONS)


def remote_item_display_name(item):
    return item.get("path_name") or item.get("name") or posixpath.basename(item.get("path", ""))


def remote_item_kind_label(item):
    if item.get("is_dir"):
        return "Thư mục"
    if item.get("is_link"):
        return "Liên kết"

    kind = item.get("kind", "File")
    path = item.get("path", "")
    if kind != "File":
        return kind
    if is_image_path(path):
        return "Ảnh"
    if is_video_path(path):
        return "Video"
    if is_database_path(path):
        return "Database"
    if is_text_path(path):
        return "Text/Log"
    return "File"


def remote_item_icon_name(item):
    if item.get("is_dir"):
        return "folder"
    if item.get("is_link"):
        return "emblem-symbolic-link"

    kind = item.get("kind", "File")
    path = item.get("path", "")
    if kind in ("Char device", "Block device"):
        return "drive-harddisk"
    if kind == "Socket":
        return "network-server"
    if kind == "Pipe":
        return "media-playback-pause"
    if is_image_path(path):
        return "image-x-generic"
    if is_video_path(path):
        return "video-x-generic"
    if is_database_path(path):
        return "x-office-spreadsheet"
    if is_text_path(path):
        return "text-x-generic"
    return "application-octet-stream"


def remote_item_grid_label(item):
    name = remote_item_display_name(item)
    if item.get("is_dir") or item.get("is_link"):
        return name
    size_text = item.get("size_text")
    return f"{name}\n{size_text}" if size_text else name


def modified_sort_value(modified):
    text = str(modified or "").strip()
    if not text:
        return (1, "")

    iso_match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}(?::\d{2})?)", text)
    if iso_match:
        date_text, time_text = iso_match.groups()
        if len(time_text) == 5:
            time_text = f"{time_text}:00"
        return (0, f"{date_text} {time_text}")

    current_year = time.localtime().tm_year
    for fmt, inject_year in (("%b %d %H:%M", True), ("%b %d %Y", False)):
        try:
            parsed = time.strptime(text, fmt)
        except ValueError:
            continue
        year = current_year if inject_year else parsed.tm_year
        return (
            0,
            f"{year:04d}-{parsed.tm_mon:02d}-{parsed.tm_mday:02d} "
            f"{parsed.tm_hour:02d}:{parsed.tm_min:02d}:00",
        )

    return (1, text.lower())


def remote_entry_sort_key(item, sort_id):
    name = remote_item_display_name(item).lower()
    kind_label = remote_item_kind_label(item).lower()
    if sort_id == "type":
        return (kind_label, name)
    if sort_id == "size":
        return (int(item.get("size") or 0), name)
    if sort_id == "modified":
        return (modified_sort_value(item.get("modified")), name)
    return (name,)


def remote_file_size(config, remote_path):
    normalized = normalize_remote_path(remote_path)
    quoted = quote_remote_path(normalized)
    command = (
        f"if [ -f {quoted} ]; then "
        f"stat -c %s {quoted} 2>/dev/null || wc -c < {quoted}; "
        "else echo '__MISSING_FILE__'; exit 1; fi"
    )
    code, output = adb_shell(config, command, timeout=FILE_EXPLORER_TIMEOUT, purpose="file-size")
    if code != 0:
        return None, output or f"Không lấy được size: {normalized}"

    lines = [line.strip() for line in (output or "").splitlines() if line.strip()]
    if not lines or not re.fullmatch(r"\d+", lines[0]):
        return None, output or f"Không parse được size: {normalized}"
    return int(lines[0]), ""
