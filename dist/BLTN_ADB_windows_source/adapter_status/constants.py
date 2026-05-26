import os
import re
import time

from .host_platform import cache_dir, config_dir

CONFIG_DIR = config_dir()
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CACHE_DIR = cache_dir()
PROCESS_FILE = os.path.join(CACHE_DIR, "child-processes.json")
RUNTIME_STATE_CACHE_FILE = os.path.join(CACHE_DIR, "runtime-dashboard-state.json")
APP_RUN_ID = f"{os.getpid()}-{int(time.time())}"

DEFAULT_CONFIG = {
    "iface": "enx1c860b2bbfcf",
    "host_cidr": "192.168.244.10/24",
    "device_ip": "192.168.244.1",
    "adb_port": "4321",
}
CONNECT_WINDOW_SECONDS = 60.0
ROOT_WAIT_SECONDS = 120.0
ROOT_DROP_WAIT_SECONDS = 25.0
ADB_UPDATE_REMOTE_PATH = "/tmp/cpu_update.bin"
ROOT_UPDATE_REMOTE_PATH = ADB_UPDATE_REMOTE_PATH
ROOT_CHANGE_FILE_REMOTE_PATH = "/home/adb/change_file"
ROOT_CHANGE_FILE_COMMAND = "cd /home/adb && ./change_file"
REMOTE_PREVIEW_LIMIT = 32768
FILE_EXPLORER_TIMEOUT = 10
FILE_EXPLORER_AUTO_REFRESH_SECONDS = 30
LIVE_LOG_MAX_CHARS = 400000
LIVE_LOG_COMMAND = "journalctl -f"
CMDTOOL_CONTROL_TIMEOUT = 20
SERVICE_CONTROL_TIMEOUT = 15
DASHBOARD_RUNTIME_AUTO_REFRESH_SECONDS = 15
VIDEO_STREAM_CHUNK_SIZE = 262144
IMAGE_PREVIEW_MAX_BYTES = 50 * 1024 * 1024
IMAGE_PREVIEW_MAX_WIDTH = 1200
IMAGE_PREVIEW_MAX_HEIGHT = 800
IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".webp",
    ".tif",
    ".tiff",
)
VIDEO_EXTENSIONS = (
    ".mp4",
    ".m4v",
    ".mkv",
    ".avi",
    ".mov",
    ".ts",
    ".m2ts",
    ".webm",
    ".3gp",
    ".mpeg",
    ".mpg",
    ".h264",
    ".h265",
    ".264",
    ".265",
)
TEXT_EXTENSIONS = (
    ".txt",
    ".log",
    ".dlt",
    ".conf",
    ".cfg",
    ".ini",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".csv",
    ".sh",
    ".rc",
)
DATABASE_EXTENSIONS = (
    ".db",
    ".sqlite",
    ".sqlite3",
)
FILE_LIST_ICON_SIZE = 24
FILE_GRID_ICON_DEFAULT_SIZE = 88
DEVICE_INFO_TTL_SECONDS = 15

FILE_COL_LIST_ICON = 0
FILE_COL_GRID_ICON = 1
FILE_COL_NAME = 2
FILE_COL_GRID_LABEL = 3
FILE_COL_KIND_LABEL = 4
FILE_COL_SIZE_TEXT = 5
FILE_COL_PERMISSIONS = 6
FILE_COL_OWNER_GROUP = 7
FILE_COL_MODIFIED = 8
FILE_COL_PATH = 9
FILE_COL_IS_DIR = 10
FILE_COL_SIZE = 11
FILE_COL_GROUP = 12
FILE_COL_KIND = 13
FILE_COL_LINK_TARGET = 14
FILE_COL_ICON_NAME = 15

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ADB_WORKDIR = os.path.expanduser("~/BLTN_ADB")
IFACE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,15}$")
USB_IFACE_PATTERN = re.compile(r"enx[0-9A-Fa-f]{12}")
ANSI_ESCAPE_PATTERN = re.compile(r"\[[0-?]*[ -/]*[@-~]")
DEVICE_INFO_LINE_PATTERN = re.compile(
    r">\s*([^\[:]+)\[([^\]]+)\]:\s*HW\[([^\]]+)\],\s*"
    r"SW Ver\[([^\]]+)\],\s*PLATFORM\[([^\]]+)\]"
)
DEVICE_INFO_EMPTY_TEXT = (
    "Model: --   |   HW: --   |   SW Ver: --   |   PLATFORM: --"
)
