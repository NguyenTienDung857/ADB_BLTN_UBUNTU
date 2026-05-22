import os
import posixpath
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from ..config import load_config, sanitize_iface, save_config
from ..constants import (
    ADB_UPDATE_REMOTE_PATH,
    ANSI_ESCAPE_PATTERN,
    CONFIG_FILE,
    DASHBOARD_RUNTIME_AUTO_REFRESH_SECONDS,
    DEFAULT_CONFIG,
    DEVICE_INFO_EMPTY_TEXT,
    FILE_COL_GRID_ICON,
    FILE_COL_GRID_LABEL,
    FILE_COL_GROUP,
    FILE_COL_ICON_NAME,
    FILE_COL_IS_DIR,
    FILE_COL_KIND,
    FILE_COL_KIND_LABEL,
    FILE_COL_LINK_TARGET,
    FILE_COL_LIST_ICON,
    FILE_COL_MODIFIED,
    FILE_COL_NAME,
    FILE_COL_OWNER_GROUP,
    FILE_COL_PATH,
    FILE_COL_PERMISSIONS,
    FILE_COL_SIZE,
    FILE_COL_SIZE_TEXT,
    FILE_EXPLORER_AUTO_REFRESH_SECONDS,
    FILE_GRID_ICON_DEFAULT_SIZE,
    FILE_LIST_ICON_SIZE,
    IMAGE_PREVIEW_MAX_HEIGHT,
    IMAGE_PREVIEW_MAX_WIDTH,
    LIVE_LOG_COMMAND,
    LIVE_LOG_MAX_CHARS,
    REMOTE_PREVIEW_LIMIT,
)
from ..processes import clean_command_output, cleanup_previous_processes, terminate_popen
from ..services.adb_device import ensure_adb_device
from ..services.adb_update import run_adb_update, validate_update_bin_path
from ..services.connection import (
    adb_reconnect,
    clean_reset,
    collect_status,
    configure_ip as configure_ip_service,
    run_command_sequence,
)
from ..services.files import (
    human_size,
    is_image_path,
    is_video_path,
    list_remote_dir,
    normalize_remote_path,
    pull_remote_file,
    read_remote_image,
    read_remote_text_head,
    remote_entry_sort_key,
    remote_item_display_name,
    remote_item_grid_label,
    remote_item_icon_name,
    remote_item_kind_label,
    remote_parent,
)
from ..services.logs import (
    start_live_log_process,
    terminate_live_log_process,
    unregister_live_log_process,
)
from ..services.root import drop_adb_root, get_root_with_debug_file, validate_debug_bin_path
from ..services.runtime_controls import (
    CMDTOOL_FEATURES,
    SERVICE_CONTROLS,
    collect_runtime_status,
    set_cmdtool_feature,
    set_log_level,
    set_service_feature,
)
from ..services.video import start_remote_video_stream
from ..services.workspace import adb_workdir, open_terminal_session, preferred_file_dialog_dir
from .dashboard import DashboardPanel
from .help_text import HELP_TEXT
from .widgets import constrain_label_width, make_text_panel, set_text_view

class AdapterStatus(Gtk.Window):
    def __init__(self):
        super().__init__(title="Network Adapter Status")
        self.set_default_size(1120, 760)
        self.set_size_request(900, 640)
        self.set_resizable(True)
        self.set_border_width(18)
        self.config = load_config()
        save_config(self.config)
        cleaned_processes = cleanup_previous_processes(purpose_prefixes=("terminal", "live-log"))
        self.poll_running = False
        self.action_running = False
        self.adb_update_running = False
        self.dashboard_running = False
        self.file_running = False
        self.video_running = False
        self.video_session_id = 0
        self.live_log_running = False
        self.live_log_starting = False
        self.live_log_proc = None
        self.live_log_session_id = 0
        self.live_log_manual_stopped = False
        self.live_log_not_ready_count = 0
        self.selected_remote_item = None
        self.remote_entries = []
        self.file_icon_cache = {}
        self.file_grid_icon_size = FILE_GRID_ICON_DEFAULT_SIZE
        self.file_focus_mode = False
        self.file_sort_id = "name"
        self.file_sort_desc = False
        self.file_dirs_first = True
        self.syncing_file_selection = False
        self.video_processes = {}
        self.video_server = None
        self.last_status = {}
        self.connect("destroy", self.cleanup_video_on_destroy)
        self.connect("destroy", self.cleanup_live_log_on_destroy)
        self.last_action = (
            f"Đã dọn {len(cleaned_processes)} terminal/log cũ do app mở từ lần trước."
            if cleaned_processes
            else "Sẵn sàng. App không tự reset ADB/IP khi mở."
        )
        self.status_details = ""

        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            window { background: #111827; color: #e5e7eb; }
            entry { padding: 8px; border-radius: 8px; }
            .title { font-size: 24px; font-weight: 700; color: #f9fafb; }
            .subtitle { color: #9ca3af; }
            .device-info-line { color: #d1d5db; font-weight: 700; padding: 2px 0; }
            .label { color: #cbd5e1; font-weight: 700; }
            .pill { border-radius: 16px; padding: 14px 16px; font-size: 18px; font-weight: 800; }
            .ok { background: #065f46; color: #d1fae5; }
            .warn { background: #92400e; color: #ffedd5; }
            .bad { background: #7f1d1d; color: #fee2e2; }
            .card { background: #1f2937; border-radius: 14px; padding: 14px; }
            .dashboard-card { background: #18212f; border: 1px solid #334155; border-radius: 8px; padding: 14px; }
            .dashboard-row { border-top: 1px solid #334155; padding: 9px 0; }
            .dashboard-section-title { color: #f9fafb; font-weight: 800; font-size: 15px; }
            .dashboard-pill { border-radius: 16px; padding: 10px 14px; font-weight: 800; }
            .dashboard-command-state { border-radius: 8px; padding: 6px 8px; font-weight: 800; }
            .dashboard-status-badge { border-radius: 10px; padding: 6px 8px; font-weight: 800; font-size: 12px; }
            .dashboard-status-note { color: #cbd5e1; font-size: 12px; padding-top: 2px; }
            .dashboard-ok { background: #065f46; color: #d1fae5; }
            .dashboard-warn { background: #92400e; color: #ffedd5; }
            .dashboard-bad { background: #7f1d1d; color: #fee2e2; }
            .file-focus-bar { background: #0f172a; border-radius: 8px; padding: 3px 6px; }
            .file-focus-path { color: #cbd5e1; font-size: 12px; }
            textview, textview text { background: #1f2937; color: #e5e7eb; }
            treeview { background: #111827; color: #e5e7eb; }
            treeview.view:selected { background: #2563eb; color: #f8fafc; }
            iconview { background: #111827; color: #e5e7eb; }
            iconview.view:selected { background: #2563eb; color: #f8fafc; border-radius: 10px; }
            notebook tab { padding: 8px 14px; }
            button { padding: 10px 14px; border-radius: 10px; }
            button.compact-button { padding: 2px 8px; border-radius: 7px; }
            button.terminal-ready { background-image: none; background-color: #059669; color: #ecfdf5; font-weight: 700; }
            button.terminal-wait { color: #6b7280; }
            button.root-needed { background-image: none; background-color: #b91c1c; color: #fef2f2; font-weight: 700; }
            button.root-ok { background-image: none; background-color: #059669; color: #ecfdf5; font-weight: 700; }
            button.root-wait { color: #6b7280; }
            button.unroot-ready { background-image: none; background-color: #d97706; color: #fff7ed; font-weight: 700; }
            button.unroot-wait { color: #6b7280; }
            button.update-ready { background-image: none; background-color: #2563eb; color: #eff6ff; font-weight: 700; }
            button.update-running { background-image: none; background-color: #7c3aed; color: #f5f3ff; font-weight: 700; }
            button.update-wait { color: #6b7280; }
            """
        )
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        window_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(window_root)

        self.notebook = Gtk.Notebook()
        self.notebook.set_hexpand(True)
        self.notebook.set_vexpand(True)
        self.notebook.connect("switch-page", self.on_notebook_switch_page)
        window_root.pack_start(self.notebook, True, True, 0)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(4)
        self.notebook.append_page(root, Gtk.Label(label="Trạng thái ADB"))

        title = Gtk.Label(label="USB Network Adapter")
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        root.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label=f"Thông số được lưu tại: {CONFIG_FILE}")
        subtitle.set_xalign(0)
        subtitle.get_style_context().add_class("subtitle")
        root.pack_start(subtitle, False, False, 0)

        config_card = Gtk.Grid(column_spacing=10, row_spacing=8)
        config_card.get_style_context().add_class("card")
        root.pack_start(config_card, False, False, 0)

        self.iface_entry = self.add_entry(config_card, 0, 0, "Tên cổng", self.config["iface"])
        self.host_entry = self.add_entry(config_card, 1, 0, "IP adapter", self.config["host_cidr"])
        self.device_entry = self.add_entry(config_card, 0, 1, "IP thiết bị", self.config["device_ip"])
        self.port_entry = self.add_entry(config_card, 1, 1, "ADB port", self.config["adb_port"])

        self.banner = Gtk.Label(label="Đang kiểm tra...")
        self.banner.set_xalign(0.5)
        self.banner.get_style_context().add_class("pill")
        root.pack_start(self.banner, False, False, 0)

        buttons = Gtk.Grid(column_spacing=10, row_spacing=8)
        root.pack_start(buttons, False, False, 0)

        self.configure_button = Gtk.Button(label="Cấu hình IP")
        self.configure_button.connect("clicked", self.configure_ip)
        buttons.attach(self.configure_button, 0, 0, 1, 1)

        self.connect_button = Gtk.Button(label="ADB Connect")
        self.connect_button.connect("clicked", self.connect_adb)
        buttons.attach(self.connect_button, 1, 0, 1, 1)

        self.update_adb_button = Gtk.Button(label="Update ADB")
        self.update_adb_button.set_sensitive(False)
        self.update_adb_button.get_style_context().add_class("update-wait")
        self.update_adb_button.set_tooltip_text("ADB chưa connect.")
        self.update_adb_button.connect("clicked", self.choose_update_file_for_adb)
        buttons.attach(self.update_adb_button, 2, 0, 1, 1)

        self.get_root_button = Gtk.Button(label="Get Root")
        self.get_root_button.set_sensitive(False)
        self.get_root_button.get_style_context().add_class("root-wait")
        self.get_root_button.set_tooltip_text("ADB chưa connect.")
        self.get_root_button.connect("clicked", self.choose_debug_file_for_root)
        buttons.attach(self.get_root_button, 3, 0, 1, 1)

        self.drop_root_button = Gtk.Button(label="Thoát Root")
        self.drop_root_button.set_sensitive(False)
        self.drop_root_button.get_style_context().add_class("unroot-wait")
        self.drop_root_button.set_tooltip_text("Chỉ bật khi thiết bị đang root.")
        self.drop_root_button.connect("clicked", self.drop_root)
        buttons.attach(self.drop_root_button, 4, 0, 1, 1)

        self.open_terminal_button = Gtk.Button(label="Mở Terminal")
        self.open_terminal_button.set_sensitive(False)
        self.open_terminal_button.get_style_context().add_class("terminal-wait")
        self.open_terminal_button.set_tooltip_text("ADB chưa connect.")
        self.open_terminal_button.connect("clicked", self.open_terminal)
        buttons.attach(self.open_terminal_button, 5, 0, 1, 1)

        self.help_button = Gtk.Button(label="Help")
        self.help_button.connect("clicked", self.show_help)
        buttons.attach(self.help_button, 6, 0, 1, 1)

        for child in buttons.get_children():
            child.set_hexpand(True)

        self.device_info_label = Gtk.Label(label=DEVICE_INFO_EMPTY_TEXT)
        self.device_info_label.set_xalign(0)
        self.device_info_label.set_hexpand(True)
        self.device_info_label.set_single_line_mode(True)
        self.device_info_label.set_max_width_chars(150)
        self.device_info_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.device_info_label.get_style_context().add_class("device-info-line")
        root.pack_start(self.device_info_label, False, False, 0)

        self.adb_update_progress = Gtk.ProgressBar()
        self.adb_update_progress.set_show_text(True)
        self.adb_update_progress.set_fraction(0.0)
        self.adb_update_progress.set_text("0% - Update ADB: chờ ADB connected")
        root.pack_start(self.adb_update_progress, False, False, 0)

        self.action_panel, self.action_text = make_text_panel(260, monospace=True, vexpand=True)
        root.pack_start(self.action_panel, True, True, 0)
        if self.last_action:
            self.set_action_text(self.last_action)

        self.dashboard_panel = DashboardPanel(
            self.dashboard_cmdtool_feature,
            self.dashboard_log_level,
            self.dashboard_service_feature,
            self.dashboard_refresh_status,
        )
        self.dashboard_page_num = self.notebook.append_page(
            self.dashboard_panel, Gtk.Label(label="Dashboard ECU")
        )
        self.dashboard_panel.set_adb_status(self.last_status)
        self.file_explorer_page = self.build_file_explorer_page()
        self.file_explorer_page_num = self.notebook.append_page(
            self.file_explorer_page, Gtk.Label(label="File Explorer")
        )
        self.live_log_page = self.build_live_log_page()
        self.live_log_page_num = self.notebook.append_page(
            self.live_log_page, Gtk.Label(label="Log realtime")
        )

        GLib.timeout_add_seconds(1, self.refresh_async)
        GLib.timeout_add_seconds(
            DASHBOARD_RUNTIME_AUTO_REFRESH_SECONDS,
            self.periodic_dashboard_refresh,
        )
        GLib.timeout_add_seconds(FILE_EXPLORER_AUTO_REFRESH_SECONDS, self.periodic_file_explorer_refresh)

    def add_entry(self, grid, column, row, label_text, value):
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.get_style_context().add_class("label")
        grid.attach(label, column * 2, row, 1, 1)

        entry = Gtk.Entry()
        entry.set_width_chars(20)
        entry.set_max_width_chars(32)
        entry.set_hexpand(True)
        entry.set_text(value)
        grid.attach(entry, column * 2 + 1, row, 1, 1)
        return entry

    def on_notebook_switch_page(self, _notebook, _page, page_num):
        if page_num == getattr(self, "dashboard_page_num", -1):
            if hasattr(self, "dashboard_panel"):
                self.dashboard_panel.set_adb_status(self.last_status)
            GLib.idle_add(self.dashboard_refresh_status, True)
        elif page_num == getattr(self, "file_explorer_page_num", -1):
            GLib.idle_add(self.auto_refresh_file_explorer)
        elif page_num == getattr(self, "live_log_page_num", -1):
            GLib.idle_add(self.update_live_log_idle_status, None, True)
        return False

    def adb_ready_for_file_refresh(self):
        status = getattr(self, "last_status", {})
        return bool(status.get("adb_ok") or status.get("adb_state") == "device")

    def dashboard_ready_for_refresh(self):
        status = getattr(self, "last_status", {})
        return bool(status.get("adb_ok") or status.get("adb_state") == "device")

    def periodic_dashboard_refresh(self):
        if (
            self.notebook.get_current_page() == getattr(self, "dashboard_page_num", -1)
            and self.dashboard_ready_for_refresh()
            and not self.dashboard_running
            and not self.action_running
        ):
            self.dashboard_refresh_status(auto=True)
        return True

    def periodic_file_explorer_refresh(self):
        if self.file_running or not self.adb_ready_for_file_refresh():
            return True
        if hasattr(self, "remote_path_entry") and self.remote_path_entry.has_focus():
            return True

        self.load_remote_dir(
            getattr(self, "current_remote_path", "/"),
            preserve_selection=True,
            quiet=True,
        )
        return True

    def auto_refresh_file_explorer(self):
        if self.file_running:
            return False

        if self.adb_ready_for_file_refresh():
            self.load_remote_dir(self.remote_path_entry.get_text() or self.current_remote_path)
            return False

        config = self.current_config()
        self.set_file_info_text("Đang kiểm tra ADB để tự refresh File Explorer...")

        def worker():
            state, _devices_output = ensure_adb_device(config)
            GLib.idle_add(self.finish_file_explorer_auto_refresh_check, state)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def finish_file_explorer_auto_refresh_check(self, state):
        if state == "device":
            self.load_remote_dir(self.remote_path_entry.get_text() or self.current_remote_path)
        else:
            self.set_file_info_text(
                f"ADB chưa ở trạng thái device nên chưa tự refresh File Explorer. State: {state or 'not connected'}"
            )
        return False

    def build_file_explorer_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(4)

        title = Gtk.Label(label="ADB File Explorer - chỉ đọc trên ECU")
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        page.pack_start(title, False, False, 0)
        self.file_title = title

        note = Gtk.Label(
            label=(
                "Duyệt file/thư mục qua ADB. App chỉ đọc trên ECU; Pull tải file về "
                f"{os.path.join(adb_workdir(), 'ecu-files')}. Video được stream trực tiếp bằng mpv."
            )
        )
        note.set_xalign(0)
        note.get_style_context().add_class("subtitle")
        constrain_label_width(note, max_width_chars=120)
        page.pack_start(note, False, False, 0)
        self.file_note = note

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        page.pack_start(nav, False, False, 0)
        self.file_nav = nav

        self.remote_path_entry = Gtk.Entry()
        self.remote_path_entry.set_text("/")
        self.remote_path_entry.set_hexpand(True)
        self.remote_path_entry.connect("activate", self.browse_remote_path)
        nav.pack_start(self.remote_path_entry, True, True, 0)

        up_button = Gtk.Button(label="Up")
        up_button.connect("clicked", self.go_remote_parent)
        nav.pack_start(up_button, False, False, 0)
        self.file_up_button = up_button

        root_button = Gtk.Button(label="Root /")
        root_button.connect("clicked", self.go_remote_root)
        nav.pack_start(root_button, False, False, 0)
        self.file_root_button = root_button

        refresh_button = Gtk.Button(label="Refresh")
        refresh_button.connect("clicked", self.browse_remote_path)
        nav.pack_start(refresh_button, False, False, 0)
        self.file_refresh_button = refresh_button

        self.file_focus_toggle = Gtk.ToggleButton(label="Focus")
        self.file_focus_toggle.set_tooltip_text("Ẩn phần phụ để vùng file/thư mục rộng hơn.")
        self.file_focus_toggle.connect("toggled", self.on_file_focus_toggled)
        nav.pack_start(self.file_focus_toggle, False, False, 0)

        self.file_count_label = Gtk.Label(label="Chưa đọc thư mục.")
        self.file_count_label.set_xalign(0)
        self.file_count_label.get_style_context().add_class("subtitle")
        page.pack_start(self.file_count_label, False, False, 0)

        self.file_focus_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.file_focus_bar.get_style_context().add_class("file-focus-bar")
        self.file_focus_bar.set_no_show_all(True)
        page.pack_start(self.file_focus_bar, False, False, 0)

        focus_up_button = Gtk.Button(label="↑")
        focus_up_button.set_tooltip_text("Lên thư mục cha")
        focus_up_button.get_style_context().add_class("compact-button")
        focus_up_button.connect("clicked", self.go_remote_parent)
        self.file_focus_bar.pack_start(focus_up_button, False, False, 0)
        self.file_focus_up_button = focus_up_button

        self.file_focus_path_label = Gtk.Label(label="/")
        self.file_focus_path_label.set_xalign(0)
        self.file_focus_path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.file_focus_path_label.set_hexpand(True)
        self.file_focus_path_label.get_style_context().add_class("file-focus-path")
        self.file_focus_bar.pack_start(self.file_focus_path_label, True, True, 0)

        self.file_focus_exit_button = Gtk.Button(label="Thoát")
        self.file_focus_exit_button.set_tooltip_text("Thoát chế độ Focus")
        self.file_focus_exit_button.get_style_context().add_class("compact-button")
        self.file_focus_exit_button.connect("clicked", self.disable_file_focus)
        self.file_focus_bar.pack_start(self.file_focus_exit_button, False, False, 0)

        self.file_store = Gtk.ListStore(
            GdkPixbuf.Pixbuf,
            GdkPixbuf.Pixbuf,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            bool,
            int,
            str,
            str,
            str,
            str,
        )
        self.file_tree = Gtk.TreeView(model=self.file_store)
        self.file_tree.set_headers_visible(True)
        self.file_tree.set_search_column(FILE_COL_NAME)
        self.file_tree.connect("row-activated", self.open_remote_row)
        self.file_tree.get_selection().connect("changed", self.on_remote_selection_changed)

        self.add_file_name_column(self.file_tree)
        self.add_file_column(self.file_tree, "Loại", FILE_COL_KIND_LABEL, sort_id="type", width=110)
        self.add_file_column(self.file_tree, "Size", FILE_COL_SIZE_TEXT, sort_id="size", width=90)
        self.add_file_column(self.file_tree, "Quyền", FILE_COL_PERMISSIONS, width=110)
        self.add_file_column(self.file_tree, "Owner/Group", FILE_COL_OWNER_GROUP, width=130)
        self.add_file_column(self.file_tree, "Sửa lúc", FILE_COL_MODIFIED, sort_id="modified", width=150)

        tree_scrolled = Gtk.ScrolledWindow()
        tree_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        tree_scrolled.set_hexpand(True)
        tree_scrolled.set_vexpand(True)
        tree_scrolled.get_style_context().add_class("card")
        tree_scrolled.add(self.file_tree)

        self.file_grid = Gtk.IconView(model=self.file_store)
        self.file_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.file_grid.set_margin(12)
        self.file_grid.set_spacing(12)
        self.file_grid.set_row_spacing(16)
        self.file_grid.set_column_spacing(18)
        self.file_grid.connect("item-activated", self.open_remote_grid_item)
        self.file_grid.connect("selection-changed", self.on_remote_grid_selection_changed)

        grid_icon_renderer = Gtk.CellRendererPixbuf()
        grid_icon_renderer.set_property("xalign", 0.5)
        self.file_grid.pack_start(grid_icon_renderer, False)
        self.file_grid.add_attribute(grid_icon_renderer, "pixbuf", FILE_COL_GRID_ICON)

        self.file_grid_text_renderer = Gtk.CellRendererText()
        self.file_grid_text_renderer.set_property("xalign", 0.5)
        self.file_grid_text_renderer.set_property("wrap-mode", Pango.WrapMode.WORD_CHAR)
        self.file_grid_text_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        self.file_grid.pack_start(self.file_grid_text_renderer, False)
        self.file_grid.add_attribute(self.file_grid_text_renderer, "text", FILE_COL_GRID_LABEL)
        self.update_file_grid_layout()

        grid_scrolled = Gtk.ScrolledWindow()
        grid_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        grid_scrolled.set_hexpand(True)
        grid_scrolled.set_vexpand(True)
        grid_scrolled.get_style_context().add_class("card")
        grid_scrolled.add(self.file_grid)

        self.file_stack = Gtk.Stack()
        self.file_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.file_stack.set_transition_duration(120)
        self.file_stack.set_hexpand(True)
        self.file_stack.set_vexpand(True)
        self.file_stack.add_named(tree_scrolled, "list")
        self.file_stack.add_named(grid_scrolled, "grid")
        self.file_stack.set_visible_child_name("list")
        page.pack_start(self.file_stack, True, True, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        page.pack_start(actions, False, False, 0)
        self.file_actions = actions

        open_button = Gtk.Button(label="Mở thư mục")
        open_button.connect("clicked", self.open_selected_remote_item)
        actions.pack_start(open_button, False, False, 0)
        self.open_remote_button = open_button

        self.preview_button = Gtk.Button(label="Xem text")
        self.preview_button.connect("clicked", self.preview_selected_remote_file)
        actions.pack_start(self.preview_button, False, False, 0)

        self.pull_button = Gtk.Button(label="Pull file về máy")
        self.pull_button.connect("clicked", self.pull_selected_remote_file)
        actions.pack_start(self.pull_button, False, False, 0)

        self.image_button = Gtk.Button(label="Xem ảnh")
        self.image_button.connect("clicked", self.view_selected_remote_image)
        actions.pack_start(self.image_button, False, False, 0)

        self.video_button = Gtk.Button(label="Mở video trực tiếp")
        self.video_button.connect("clicked", self.open_selected_remote_video)
        actions.pack_start(self.video_button, False, False, 0)

        self.stop_video_button = Gtk.Button(label="Dừng video")
        self.stop_video_button.connect("clicked", self.stop_remote_video)
        actions.pack_start(self.stop_video_button, False, False, 0)

        self.copy_path_button = Gtk.Button(label="Copy path")
        self.copy_path_button.connect("clicked", self.copy_selected_remote_path)
        actions.pack_start(self.copy_path_button, False, False, 0)

        self.file_info_panel, self.file_info_text = make_text_panel(150, monospace=True)
        page.pack_start(self.file_info_panel, False, False, 0)
        self.set_file_info_text(
            "Bấm Refresh để đọc thư mục /. Double-click thư mục để mở.\n"
            "Khi ADB đã connect, app tự refresh khi mở tab và tự đồng bộ mỗi "
            f"{FILE_EXPLORER_AUTO_REFRESH_SECONDS} giây. Bấm Focus để xem file rộng hơn."
        )
        self.update_file_buttons()
        self.current_remote_path = "/"
        return page

    def build_live_log_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(4)

        title = Gtk.Label(label="Log hệ thống realtime")
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        page.pack_start(title, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        page.pack_start(toolbar, False, False, 0)

        self.live_log_start_button = Gtk.Button(label="Start")
        self.live_log_start_button.set_tooltip_text("Bắt đầu theo dõi log hệ thống realtime.")
        self.live_log_start_button.connect("clicked", self.start_live_log)
        toolbar.pack_start(self.live_log_start_button, False, False, 0)

        self.live_log_stop_button = Gtk.Button(label="Stop")
        self.live_log_stop_button.set_tooltip_text("Dừng stream log realtime.")
        self.live_log_stop_button.connect("clicked", self.stop_live_log)
        toolbar.pack_start(self.live_log_stop_button, False, False, 0)

        clear_button = Gtk.Button(label="Clear")
        clear_button.connect("clicked", self.clear_live_log)
        toolbar.pack_start(clear_button, False, False, 0)

        self.live_log_status_label = Gtk.Label(label="Chờ CONNECTED - ADB ROOT READY.")
        self.live_log_status_label.set_xalign(0)
        self.live_log_status_label.set_hexpand(True)
        self.live_log_status_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.live_log_status_label.get_style_context().add_class("subtitle")
        toolbar.pack_start(self.live_log_status_label, True, True, 0)

        self.live_log_panel, self.live_log_text = make_text_panel(500, monospace=True, vexpand=True)
        page.pack_start(self.live_log_panel, True, True, 0)
        set_text_view(
            self.live_log_text,
            f"Chưa chạy log. Bấm Start để chạy {LIVE_LOG_COMMAND}.",
        )
        self.update_live_log_controls()
        return page

    def add_file_name_column(self, tree):
        icon_renderer = Gtk.CellRendererPixbuf()
        text_renderer = Gtk.CellRendererText()
        text_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)

        column = Gtk.TreeViewColumn("Tên")
        column.pack_start(icon_renderer, False)
        column.add_attribute(icon_renderer, "pixbuf", FILE_COL_LIST_ICON)
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", FILE_COL_NAME)
        column.set_resizable(True)
        column.set_expand(True)
        column.set_min_width(330)
        column.set_clickable(True)
        column.connect("clicked", self.on_file_column_clicked, "name")
        tree.append_column(column)

    def add_file_column(self, tree, title, index, expand=False, width=None, sort_id=None):
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        column = Gtk.TreeViewColumn(title, renderer, text=index)
        column.set_resizable(True)
        column.set_expand(expand)
        if sort_id:
            column.set_clickable(True)
            column.connect("clicked", self.on_file_column_clicked, sort_id)
        if width:
            column.set_min_width(width)
        tree.append_column(column)

    def on_file_column_clicked(self, _column, sort_id):
        if self.file_sort_id == sort_id:
            self.file_sort_desc = not self.file_sort_desc
        else:
            self.file_sort_id = sort_id
            self.file_sort_desc = False
        self.refresh_file_store(preserve_selection=True)
        return False

    def load_icon_pixbuf(self, icon_name, size):
        safe_name = icon_name or "application-octet-stream"
        safe_size = max(16, int(size or FILE_LIST_ICON_SIZE))
        cache_key = (safe_name, safe_size)
        if cache_key in self.file_icon_cache:
            return self.file_icon_cache[cache_key]

        theme = Gtk.IconTheme.get_default()
        for candidate in (safe_name, "text-x-generic", "application-octet-stream"):
            try:
                pixbuf = theme.load_icon(candidate, safe_size, Gtk.IconLookupFlags.FORCE_SIZE)
                self.file_icon_cache[cache_key] = pixbuf
                return pixbuf
            except GLib.Error:
                continue

        self.file_icon_cache[cache_key] = None
        return None

    def sorted_remote_entries(self):
        entries = list(getattr(self, "remote_entries", []))
        sort_id = getattr(self, "file_sort_id", "name")
        reverse = bool(getattr(self, "file_sort_desc", False))
        dirs_first = bool(getattr(self, "file_dirs_first", True))

        if dirs_first:
            dirs = [item for item in entries if item.get("is_dir")]
            rest = [item for item in entries if not item.get("is_dir")]
            return (
                sorted(dirs, key=lambda item: remote_entry_sort_key(item, sort_id), reverse=reverse)
                + sorted(rest, key=lambda item: remote_entry_sort_key(item, sort_id), reverse=reverse)
            )
        return sorted(entries, key=lambda item: remote_entry_sort_key(item, sort_id), reverse=reverse)

    def refresh_file_store(self, preserve_selection=False, selected_path=None, update_info=True):
        if preserve_selection and not selected_path and self.selected_remote_item:
            selected_path = self.selected_remote_item.get("path")

        self.syncing_file_selection = True
        try:
            self.file_store.clear()
            grid_icon_size = int(getattr(self, "file_grid_icon_size", FILE_GRID_ICON_DEFAULT_SIZE))
            for item in self.sorted_remote_entries():
                icon_name = remote_item_icon_name(item)
                self.file_store.append(
                    [
                        self.load_icon_pixbuf(icon_name, FILE_LIST_ICON_SIZE),
                        self.load_icon_pixbuf(icon_name, grid_icon_size),
                        remote_item_display_name(item),
                        remote_item_grid_label(item),
                        remote_item_kind_label(item),
                        item["size_text"],
                        item["permissions"],
                        f"{item['owner']}/{item['group']}",
                        item["modified"],
                        item["path"],
                        item["is_dir"],
                        int(item["size"]),
                        item["group"],
                        item["kind"],
                        item.get("link_target", ""),
                        icon_name,
                    ]
                )
        finally:
            self.syncing_file_selection = False

        if selected_path:
            restored_item = self.item_from_remote_path(selected_path)
            if restored_item:
                self.selected_remote_item = restored_item
                if update_info:
                    self.set_file_info_text(self.describe_remote_item(restored_item))
                self.select_remote_path_in_views(selected_path)
            else:
                self.selected_remote_item = None
                if update_info:
                    self.set_file_info_text("Mục đã chọn không còn trong thư mục hiện tại.")
            self.update_file_buttons()

    def on_file_focus_toggled(self, toggle):
        self.set_file_focus(toggle.get_active())
        return False

    def disable_file_focus(self, _button=None):
        if hasattr(self, "file_focus_toggle") and self.file_focus_toggle.get_active():
            self.file_focus_toggle.set_active(False)
        else:
            self.set_file_focus(False)
        return False

    def set_file_focus(self, enabled):
        self.file_focus_mode = bool(enabled)
        hidden_widgets = [
            getattr(self, "file_title", None),
            getattr(self, "file_note", None),
            getattr(self, "file_nav", None),
            getattr(self, "file_count_label", None),
            getattr(self, "file_actions", None),
            getattr(self, "file_info_panel", None),
        ]

        if self.file_focus_mode:
            for widget in hidden_widgets:
                if widget:
                    widget.hide()
            self.update_file_focus_path()
            self.file_focus_bar.set_no_show_all(False)
            self.file_focus_bar.show_all()
        else:
            self.file_focus_bar.hide()
            self.file_focus_bar.set_no_show_all(True)
            for widget in hidden_widgets:
                if widget:
                    widget.show_all()

        return False

    def update_file_focus_path(self):
        if hasattr(self, "file_focus_path_label"):
            self.file_focus_path_label.set_text(getattr(self, "current_remote_path", "/"))
        return False

    def update_file_grid_layout(self):
        size = int(getattr(self, "file_grid_icon_size", FILE_GRID_ICON_DEFAULT_SIZE))
        item_width = max(116, size + 74)
        self.file_grid.set_item_width(item_width)
        if hasattr(self, "file_grid_text_renderer"):
            self.file_grid_text_renderer.set_property("wrap-width", max(96, item_width - 16))
            self.file_grid_text_renderer.set_property("width", max(96, item_width - 16))

    def current_config(self):
        config = {
            "iface": sanitize_iface(self.iface_entry.get_text()),
            "host_cidr": self.host_entry.get_text().strip() or DEFAULT_CONFIG["host_cidr"],
            "device_ip": self.device_entry.get_text().strip() or DEFAULT_CONFIG["device_ip"],
            "adb_port": self.port_entry.get_text().strip() or DEFAULT_CONFIG["adb_port"],
        }
        return config

    def set_action_text(self, text):
        self.last_action = text or ""
        self.render_main_log()

    def set_details_text(self, text):
        self.status_details = text or ""
        self.render_main_log()

    def render_main_log(self):
        if not hasattr(self, "action_text"):
            return
        sections = []
        status_details = str(getattr(self, "status_details", "") or "").strip()
        last_action = str(getattr(self, "last_action", "") or "").strip()
        if status_details:
            sections.append(status_details)
        if last_action:
            sections.append(last_action)
        set_text_view(self.action_text, "\n\n".join(sections))

    def set_device_info_line(self, text):
        text = text or DEVICE_INFO_EMPTY_TEXT
        self.device_info_label.set_text(text)
        self.device_info_label.set_tooltip_text(text)

    def set_file_info_text(self, text):
        set_text_view(self.file_info_text, text)

    def set_live_log_status(self, text):
        if hasattr(self, "live_log_status_label"):
            text = text or ""
            if self.live_log_status_label.get_text() != text:
                self.live_log_status_label.set_text(text)

    def live_log_root_ready(self, status=None):
        status = status if status is not None else getattr(self, "last_status", {})
        return bool(status.get("adb_ok") and status.get("root_ok"))

    def selected_live_log_filter(self):
        return ""

    def update_live_log_controls(self, status=None):
        if not hasattr(self, "live_log_start_button"):
            return

        root_ready = self.live_log_root_ready(status)
        self.live_log_start_button.set_label("Start")
        self.live_log_start_button.set_sensitive(
            root_ready
            and not self.live_log_starting
            and not self.live_log_running
            and not self.action_running
        )
        self.live_log_stop_button.set_sensitive(self.live_log_running or self.live_log_starting)

    def clear_live_log(self, _button=None):
        if hasattr(self, "live_log_text"):
            set_text_view(self.live_log_text, "")
        return False

    def update_live_log_idle_status(self, status=None, force=False):
        if self.live_log_running or self.live_log_starting:
            return False

        current_text = ""
        if hasattr(self, "live_log_status_label"):
            current_text = self.live_log_status_label.get_text() or ""

        may_replace = force or not current_text or current_text.startswith(("Chờ", "Sẵn sàng"))
        if not may_replace and self.live_log_root_ready(status):
            return False

        if self.live_log_root_ready(status):
            self.set_live_log_status("Sẵn sàng. Bấm Start để theo dõi log hệ thống realtime.")
        else:
            self.set_live_log_status("Chờ CONNECTED - ADB ROOT READY để đọc log hệ thống realtime.")
        return False

    def start_live_log(self, _button=None, auto=False):
        if not hasattr(self, "live_log_text"):
            return False

        self.live_log_manual_stopped = False
        if self.action_running:
            self.set_live_log_status("Đang có thao tác ADB khác, chưa mở Log realtime.")
            self.update_live_log_controls()
            return False
        if self.live_log_starting:
            return False
        if self.live_log_running:
            self.set_live_log_status("Log realtime đang chạy. Bấm Stop trước nếu muốn chạy lại.")
            self.update_live_log_controls()
            return False

        if not self.live_log_root_ready():
            self.set_live_log_status("ADB phải ở trạng thái device và uid=0(root) trước khi show log.")
            self.update_live_log_controls()
            return False

        self.store_current_config()
        config = dict(self.config)
        filter_text = self.selected_live_log_filter()
        self.live_log_session_id += 1
        session_id = self.live_log_session_id
        self.live_log_starting = True
        self.set_live_log_status("Đang kiểm tra root và chạy journalctl -f...")
        set_text_view(
            self.live_log_text,
            (
                f"[{time.strftime('%H:%M:%S')}] Start log hệ thống realtime\n"
                f"Lệnh: {LIVE_LOG_COMMAND}\n"
                "journalctl -f có thể in vài dòng gần nhất rồi tiếp tục theo dõi realtime.\n"
            ),
        )
        self.update_live_log_controls()

        def worker():
            self.live_log_worker(config, filter_text, session_id)

        threading.Thread(target=worker, daemon=True).start()
        return False if auto else True

    def live_log_worker(self, config, filter_text, session_id):
        proc = None
        error = ""
        return_code = 0

        try:
            result = start_live_log_process(config, filter_text)
            if not result.get("ok"):
                GLib.idle_add(
                    self.finish_live_log_start_failed,
                    session_id,
                    result.get("message", "Không mở được Log realtime."),
                )
                return

            proc = result["process"]
            self.live_log_proc = proc

            if session_id != self.live_log_session_id:
                terminate_live_log_process(proc)
                return

            GLib.idle_add(
                self.mark_live_log_started,
                session_id,
                result.get("command_display", ""),
                result.get("source_label", LIVE_LOG_COMMAND),
            )

            for line in proc.stdout or []:
                if session_id != self.live_log_session_id:
                    break
                GLib.idle_add(self.append_live_log_line, session_id, line)

            if session_id != self.live_log_session_id and proc.poll() is None:
                terminate_live_log_process(proc)

            try:
                return_code = proc.wait(timeout=1)
            except Exception:
                terminate_live_log_process(proc)
                return_code = proc.returncode if proc.returncode is not None else -1
        except Exception as exc:
            error = str(exc)
            return_code = 1
        finally:
            if proc:
                unregister_live_log_process(proc)

        if session_id == self.live_log_session_id:
            GLib.idle_add(self.finish_live_log_process, session_id, return_code, error)

    def mark_live_log_started(self, session_id, command_display, source_label):
        if session_id != self.live_log_session_id:
            return False
        self.live_log_starting = False
        self.live_log_running = True
        self.set_live_log_status(f"Đang đọc log hệ thống realtime | {source_label}")
        self.update_live_log_controls()
        self.append_live_log_line(
            session_id,
            f"[{time.strftime('%H:%M:%S')}] Lệnh đang chạy: {command_display}\n",
        )
        return False

    def append_live_log_line(self, session_id, line):
        if session_id != self.live_log_session_id or not hasattr(self, "live_log_text"):
            return False

        text = ANSI_ESCAPE_PATTERN.sub("", str(line or "")).replace("\r", "\n")
        if not text:
            return False
        if not text.endswith("\n"):
            text += "\n"

        buffer = self.live_log_text.get_buffer()
        start_iter, end_iter = buffer.get_bounds()
        current_text = buffer.get_text(start_iter, end_iter, True).strip()
        if current_text.startswith("Chưa có log."):
            buffer.set_text("")

        end_iter = buffer.get_end_iter()
        buffer.insert(end_iter, text)

        overage = buffer.get_char_count() - LIVE_LOG_MAX_CHARS
        if overage > 0:
            trim_start = buffer.get_start_iter()
            trim_end = buffer.get_iter_at_offset(overage)
            trim_end.forward_line()
            buffer.delete(trim_start, trim_end)

        end_iter = buffer.get_end_iter()
        mark = buffer.create_mark(None, end_iter, False)
        self.live_log_text.scroll_mark_onscreen(mark)
        buffer.delete_mark(mark)
        return False

    def finish_live_log_start_failed(self, session_id, message):
        if session_id != self.live_log_session_id:
            return False
        self.live_log_starting = False
        self.live_log_running = False
        self.live_log_proc = None
        self.set_live_log_status(message)
        self.update_live_log_controls()
        return False

    def finish_live_log_process(self, session_id, return_code, error):
        if session_id != self.live_log_session_id:
            return False
        self.live_log_starting = False
        self.live_log_running = False
        self.live_log_proc = None
        if error:
            self.set_live_log_status(f"Log realtime lỗi: {error}")
        elif return_code == 0:
            self.set_live_log_status("Log realtime đã dừng.")
        else:
            self.set_live_log_status(f"Log realtime đã dừng, mã lỗi {return_code}.")
        self.update_live_log_controls()
        return False

    def stop_live_log(self, _button=None):
        return self.stop_live_log_process("Đã dừng Log realtime.", manual=True)

    def stop_live_log_process(self, message=None, manual=False):
        if manual:
            self.live_log_manual_stopped = True
        self.live_log_not_ready_count = 0
        self.live_log_session_id += 1
        proc = self.live_log_proc
        self.live_log_proc = None
        was_active = self.live_log_running or self.live_log_starting or proc is not None
        self.live_log_running = False
        self.live_log_starting = False
        if proc:
            terminate_live_log_process(proc)
        if message and hasattr(self, "live_log_status_label"):
            self.set_live_log_status(message if was_active else "Không có Log realtime đang chạy.")
        self.update_live_log_controls()
        return False

    def cleanup_live_log_on_destroy(self, _window):
        self.stop_live_log_process(manual=False)

    def update_file_buttons(self):
        item = self.selected_remote_item
        has_item = item is not None
        is_directory_like = has_item and (item.get("is_dir") or item.get("kind") == "Liên kết")
        is_regular_file = has_item and item.get("kind") == "File"
        is_image_file = is_regular_file and is_image_path(item.get("path", ""))
        is_video_file = is_regular_file and is_video_path(item.get("path", ""))
        can_file_action = not self.file_running and not self.action_running

        for widget in (
            getattr(self, "remote_path_entry", None),
            getattr(self, "file_up_button", None),
            getattr(self, "file_root_button", None),
            getattr(self, "file_refresh_button", None),
            getattr(self, "file_focus_toggle", None),
            getattr(self, "file_focus_up_button", None),
            getattr(self, "file_focus_exit_button", None),
        ):
            if widget is not None:
                widget.set_sensitive(can_file_action)

        if hasattr(self, "open_remote_button"):
            self.open_remote_button.set_sensitive(bool(is_directory_like) and can_file_action)
        if hasattr(self, "preview_button"):
            self.preview_button.set_sensitive(bool(is_regular_file) and can_file_action)
        if hasattr(self, "pull_button"):
            self.pull_button.set_sensitive(bool(is_regular_file) and can_file_action)
        if hasattr(self, "image_button"):
            self.image_button.set_sensitive(bool(is_image_file) and can_file_action)
        if hasattr(self, "video_button"):
            self.video_button.set_sensitive(bool(is_video_file) and can_file_action)
        if hasattr(self, "stop_video_button"):
            self.stop_video_button.set_sensitive(self.video_running and not self.action_running)
        if hasattr(self, "copy_path_button"):
            self.copy_path_button.set_sensitive(has_item and can_file_action)

    def selected_item_from_row(self, row):
        return {
            "name": row[FILE_COL_NAME],
            "kind_label": row[FILE_COL_KIND_LABEL],
            "kind": row[FILE_COL_KIND],
            "size_text": row[FILE_COL_SIZE_TEXT],
            "permissions": row[FILE_COL_PERMISSIONS],
            "owner_group": row[FILE_COL_OWNER_GROUP],
            "modified": row[FILE_COL_MODIFIED],
            "path": row[FILE_COL_PATH],
            "is_dir": bool(row[FILE_COL_IS_DIR]),
            "size": int(row[FILE_COL_SIZE]),
            "group": row[FILE_COL_GROUP],
            "link_target": row[FILE_COL_LINK_TARGET],
            "icon_name": row[FILE_COL_ICON_NAME],
        }

    def describe_remote_item(self, item):
        if not item:
            return "Chưa chọn file/thư mục."
        link_line = f"Link tới: {item['link_target']}" if item.get("link_target") else None
        lines = [
            f"Path: {item['path']}",
            f"Tên: {item['name']}",
            f"Loại: {item.get('kind_label') or item['kind']}",
            f"Size: {item['size_text']}",
            f"Quyền: {item['permissions']}",
            f"Owner/Group: {item['owner_group']}",
            f"Sửa lúc: {item['modified']}",
        ]
        if link_line:
            lines.append(link_line)
        lines.extend(
            [
                "",
                (
                    "Đây là file ảnh: có thể bấm Xem ảnh hoặc double-click để mở."
                    if item.get("kind") == "File" and is_image_path(item["path"])
                    else
                    "Đây là file video: có thể bấm Mở video trực tiếp."
                    if item.get("kind") == "File" and is_video_path(item["path"])
                    else "Double-click thư mục để mở. File thường có thể Xem text hoặc Pull về máy."
                ),
            ]
        )
        return "\n".join(
            lines
        )

    def browse_remote_path(self, _widget=None):
        path = self.remote_path_entry.get_text()
        self.load_remote_dir(path)

    def go_remote_parent(self, _button):
        self.load_remote_dir(remote_parent(getattr(self, "current_remote_path", "/")))

    def go_remote_root(self, _button):
        self.load_remote_dir("/")

    def load_remote_dir(self, path, preserve_selection=False, quiet=False):
        if self.file_running:
            if not quiet:
                self.set_file_info_text("Đang có thao tác file chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        if quiet:
            config = self.current_config()
        else:
            self.store_current_config()
            config = dict(self.config)
        base_path = getattr(self, "current_remote_path", "/")
        normalized = normalize_remote_path(path, base_path)
        selected_path = (
            self.selected_remote_item.get("path")
            if preserve_selection and self.selected_remote_item
            else None
        )
        self.remote_path_entry.set_text(normalized)
        if hasattr(self, "file_focus_path_label"):
            self.file_focus_path_label.set_text(normalized)
        self.file_running = True
        if not preserve_selection:
            self.selected_remote_item = None
        self.update_file_buttons()
        self.file_count_label.set_text(
            f"Đang tự đồng bộ: {normalized}" if quiet else f"Đang đọc: {normalized}"
        )
        if not quiet:
            self.set_file_info_text(f"Đang đọc thư mục qua ADB: {normalized}")

        def worker():
            result = list_remote_dir(config, normalized)
            result["preserve_selection"] = bool(preserve_selection)
            result["selected_path"] = selected_path
            result["quiet"] = bool(quiet)
            GLib.idle_add(self.apply_remote_dir, result)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def apply_remote_dir(self, result):
        self.file_running = False
        quiet = bool(result.get("quiet"))
        preserve_selection = bool(result.get("preserve_selection"))
        selected_path = result.get("selected_path")

        if not result.get("ok"):
            if quiet:
                current_path = getattr(self, "current_remote_path", result.get("path", "/"))
                self.file_count_label.set_text(
                    f"{current_path}: tự đồng bộ lỗi lúc {time.strftime('%H:%M:%S')}"
                )
                if not getattr(self, "remote_entries", []):
                    self.set_file_info_text(result.get("message", "Không đọc được thư mục."))
            else:
                self.file_store.clear()
                self.selected_remote_item = None
                self.remote_entries = []
                self.file_count_label.set_text(f"Không đọc được: {result.get('path', '/')}")
                self.set_file_info_text(result.get("message", "Không đọc được thư mục."))
            self.update_file_buttons()
            return False

        if not preserve_selection:
            self.selected_remote_item = None
        self.current_remote_path = result["path"]
        self.remote_path_entry.set_text(self.current_remote_path)
        self.update_file_focus_path()
        entries = result.get("entries", [])
        self.remote_entries = entries
        self.refresh_file_store(
            preserve_selection=preserve_selection,
            selected_path=selected_path,
            update_info=not quiet,
        )

        self.file_count_label.set_text(
            f"{self.current_remote_path}: {len(entries)} mục - cập nhật {time.strftime('%H:%M:%S')}"
        )
        if not quiet:
            self.set_file_info_text(
                "Đã đọc thư mục. Chọn một dòng để xem thông tin, double-click thư mục để mở."
                if entries
                else "Thư mục trống hoặc không có mục đọc được."
            )
        self.update_file_buttons()
        return False

    def on_remote_selection_changed(self, selection):
        if self.syncing_file_selection:
            return False

        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            self.apply_remote_selection(None, sync_views=False)
        else:
            self.apply_remote_selection(self.selected_item_from_row(model[tree_iter]), sync_views=True)
        return False

    def open_remote_row(self, tree, path, _column):
        model = tree.get_model()
        item = self.selected_item_from_model_path(model, path)
        self.open_remote_item(item)
        return False

    def on_remote_grid_selection_changed(self, icon_view):
        if self.syncing_file_selection:
            return False

        paths = icon_view.get_selected_items()
        if not paths:
            self.apply_remote_selection(None, sync_views=False)
            return False

        item = self.selected_item_from_model_path(icon_view.get_model(), paths[0])
        self.apply_remote_selection(item, sync_views=True)
        return False

    def open_remote_grid_item(self, icon_view, path):
        item = self.selected_item_from_model_path(icon_view.get_model(), path)
        self.open_remote_item(item)
        return False

    def item_from_remote_path(self, remote_path):
        tree_iter = self.file_store.get_iter_first()
        while tree_iter is not None:
            if self.file_store[tree_iter][FILE_COL_PATH] == remote_path:
                return self.selected_item_from_row(self.file_store[tree_iter])
            tree_iter = self.file_store.iter_next(tree_iter)
        return None

    def selected_item_from_model_path(self, model, path):
        try:
            tree_iter = model.get_iter(path)
        except (TypeError, ValueError):
            return None
        return self.selected_item_from_row(model[tree_iter])

    def apply_remote_selection(self, item, sync_views=True):
        self.selected_remote_item = item
        if item is None:
            self.set_file_info_text("Chưa chọn file/thư mục.")
        else:
            self.set_file_info_text(self.describe_remote_item(item))
            if sync_views:
                self.select_remote_path_in_views(item.get("path"))
        self.update_file_buttons()

    def select_remote_path_in_views(self, remote_path):
        if not remote_path:
            return False

        tree_iter = self.file_store.get_iter_first()
        while tree_iter is not None:
            if self.file_store[tree_iter][FILE_COL_PATH] == remote_path:
                tree_path = self.file_store.get_path(tree_iter)
                self.syncing_file_selection = True
                try:
                    self.file_tree.get_selection().select_path(tree_path)
                    self.file_tree.scroll_to_cell(tree_path, None, False, 0.0, 0.0)
                    self.file_grid.unselect_all()
                    self.file_grid.select_path(tree_path)
                    self.file_grid.scroll_to_path(tree_path, False, 0.0, 0.0)
                finally:
                    self.syncing_file_selection = False
                return True
            tree_iter = self.file_store.iter_next(tree_iter)
        return False

    def open_remote_item(self, item):
        if not item:
            return False
        if item.get("is_dir") or item.get("kind") == "Liên kết":
            self.load_remote_dir(item["path"])
        elif item.get("kind") == "File" and is_image_path(item.get("path", "")):
            self.selected_remote_item = item
            self.view_selected_remote_image(None)
        elif item.get("kind") == "File" and is_video_path(item.get("path", "")):
            self.selected_remote_item = item
            self.open_selected_remote_video(None)
        return False

    def open_selected_remote_item(self, _button):
        item = self.selected_remote_item
        if item and (item.get("is_dir") or item.get("kind") == "Liên kết"):
            self.load_remote_dir(item["path"])

    def preview_selected_remote_file(self, _button):
        item = self.selected_remote_item
        if not item or item.get("kind") != "File":
            self.set_file_info_text("Chỉ preview file thường.")
            return False
        if self.file_running:
            self.set_file_info_text("Đang có thao tác file chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        self.store_current_config()
        self.file_running = True
        self.update_file_buttons()
        self.set_file_info_text(f"Đang đọc tối đa {REMOTE_PREVIEW_LIMIT} bytes: {item['path']}")
        config = dict(self.config)
        remote_path = item["path"]

        def worker():
            code, output = read_remote_text_head(config, remote_path)
            if code == 0:
                message = (
                    f"Preview: {remote_path}\n"
                    f"Giới hạn: {REMOTE_PREVIEW_LIMIT} bytes đầu tiên\n"
                    "----------------------------------------\n"
                    f"{output}"
                )
            else:
                message = f"Không preview được: {remote_path}\n{output}"
            GLib.idle_add(self.finish_file_operation, message)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def pull_selected_remote_file(self, _button):
        item = self.selected_remote_item
        if not item or item.get("kind") != "File":
            self.set_file_info_text("Chỉ pull file thường ở giai đoạn này.")
            return False
        if self.file_running:
            self.set_file_info_text("Đang có thao tác file chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        self.store_current_config()
        self.file_running = True
        self.update_file_buttons()
        self.set_file_info_text(f"Đang pull file về máy: {item['path']}")
        config = dict(self.config)
        remote_path = item["path"]

        def worker():
            code, output, destination = pull_remote_file(config, remote_path)
            if code == 0:
                message = output
            else:
                message = f"Pull lỗi ({code}): {remote_path}\nĐích local: {destination}\n{output}"
            GLib.idle_add(self.finish_file_operation, message)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def view_selected_remote_image(self, _button):
        item = self.selected_remote_item
        if not item or item.get("kind") != "File" or not is_image_path(item.get("path", "")):
            self.set_file_info_text("Chỉ xem trực tiếp file ảnh được nhận diện theo đuôi file.")
            return False
        if self.file_running:
            self.set_file_info_text("Đang có thao tác file chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        self.store_current_config()
        self.file_running = True
        self.update_file_buttons()
        self.set_file_info_text(f"Đang đọc ảnh qua ADB:\n{item['path']}")
        config = dict(self.config)
        remote_path = item["path"]

        def worker():
            result = read_remote_image(config, remote_path)
            GLib.idle_add(self.finish_remote_image_read, result)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def finish_remote_image_read(self, result):
        self.file_running = False
        if not result.get("ok"):
            self.set_file_info_text(result.get("message", "Không đọc được ảnh."))
            self.update_file_buttons()
            return False

        try:
            pixbuf = self.pixbuf_from_image_data(result.get("data", b""))
        except Exception as exc:
            self.set_file_info_text(f"Không decode được ảnh:\n{result.get('path', '')}\n{exc}")
            self.update_file_buttons()
            return False

        self.show_image_window(result["path"], pixbuf, result.get("size", len(result.get("data", b""))))
        self.set_file_info_text(
            f"Đã mở ảnh:\n{result['path']}\n"
            f"Kích thước file: {human_size(result.get('size', 0))}\n"
            f"Độ phân giải: {pixbuf.get_width()}x{pixbuf.get_height()}"
        )
        self.update_file_buttons()
        return False

    def pixbuf_from_image_data(self, data):
        loader = GdkPixbuf.PixbufLoader()
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
        if not pixbuf:
            raise ValueError("GdkPixbuf không đọc được dữ liệu ảnh.")
        return pixbuf

    def scaled_image_pixbuf(self, pixbuf):
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if width <= IMAGE_PREVIEW_MAX_WIDTH and height <= IMAGE_PREVIEW_MAX_HEIGHT:
            return pixbuf

        scale = min(IMAGE_PREVIEW_MAX_WIDTH / width, IMAGE_PREVIEW_MAX_HEIGHT / height)
        scaled_width = max(1, int(width * scale))
        scaled_height = max(1, int(height * scale))
        return pixbuf.scale_simple(scaled_width, scaled_height, GdkPixbuf.InterpType.BILINEAR)

    def show_image_window(self, remote_path, pixbuf, size):
        display_pixbuf = self.scaled_image_pixbuf(pixbuf)
        dialog = Gtk.Window(title=f"Xem ảnh - {posixpath.basename(normalize_remote_path(remote_path))}")
        dialog.set_transient_for(self)
        dialog.set_default_size(980, 720)
        dialog.set_border_width(12)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        dialog.add(root)

        title = Gtk.Label(label=posixpath.basename(normalize_remote_path(remote_path)))
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        root.pack_start(title, False, False, 0)

        details = Gtk.Label(
            label=(
                f"Path: {normalize_remote_path(remote_path)}\n"
                f"File: {human_size(size)} | Ảnh gốc: {pixbuf.get_width()}x{pixbuf.get_height()} | "
                f"Hiển thị: {display_pixbuf.get_width()}x{display_pixbuf.get_height()}"
            )
        )
        details.set_xalign(0)
        details.get_style_context().add_class("subtitle")
        constrain_label_width(details, max_width_chars=140)
        root.pack_start(details, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.get_style_context().add_class("card")
        root.pack_start(scrolled, True, True, 0)

        image = Gtk.Image.new_from_pixbuf(display_pixbuf)
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        scrolled.add(image)

        close_button = Gtk.Button(label="Đóng")
        close_button.connect("clicked", lambda _button: dialog.destroy())
        root.pack_start(close_button, False, False, 0)

        dialog.show_all()

    def open_selected_remote_video(self, _button):
        item = self.selected_remote_item
        if not item or item.get("kind") != "File" or not is_video_path(item.get("path", "")):
            self.set_file_info_text("Chỉ mở trực tiếp file video được nhận diện theo đuôi file.")
            return False
        if self.file_running:
            self.set_file_info_text("Đang có thao tác file chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        self.store_current_config()
        self.file_running = True
        self.video_running = False
        self.video_session_id += 1
        session_id = self.video_session_id
        self.update_file_buttons()
        self.set_file_info_text(f"Đang mở video trực tiếp qua ADB:\n{item['path']}")
        config = dict(self.config)
        remote_path = item["path"]

        def worker():
            result = start_remote_video_stream(config, remote_path)
            GLib.idle_add(self.finish_video_start, result, session_id)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def finish_video_start(self, result, session_id):
        if session_id != self.video_session_id:
            return False

        self.file_running = False
        if result.get("ok"):
            self.video_running = True
            self.video_processes = result.get("processes", {})
            self.video_server = result.get("server")
            self.set_file_info_text(result.get("message", "Đã mở video trực tiếp."))
            threading.Thread(
                target=self.watch_video_stream,
                args=(session_id, self.video_processes, self.video_server, result.get("path", "")),
                daemon=True,
            ).start()
        else:
            self.video_running = False
            self.video_processes = {}
            self.video_server = None
            self.set_file_info_text(result.get("message", "Không mở được video trực tiếp."))

        self.update_file_buttons()
        return False

    def watch_video_stream(self, session_id, processes, video_server, remote_path):
        player_proc = processes.get("player")
        if player_proc:
            try:
                player_proc.wait()
            except Exception:
                pass

        if video_server:
            video_server.stop()

        GLib.idle_add(self.finish_video_stream, session_id, remote_path)

    def finish_video_stream(self, session_id, remote_path):
        if session_id != self.video_session_id:
            return False
        self.video_running = False
        self.video_processes = {}
        self.video_server = None
        self.update_file_buttons()
        self.set_file_info_text(f"Video đã đóng hoặc stream đã dừng:\n{remote_path}")
        return False

    def stop_remote_video(self, _button=None):
        killed = cleanup_previous_processes(include_current=True, purpose_prefixes=("video-stream",))
        if self.video_server:
            self.video_server.stop()
        for proc in self.video_processes.values():
            terminate_popen(proc)
        self.video_running = False
        self.video_processes = {}
        self.video_server = None
        self.video_session_id += 1
        self.update_file_buttons()
        message = f"Đã dừng {len(killed)} tiến trình video stream." if killed else "Không có video stream đang chạy."
        self.set_file_info_text(message)
        return False

    def cleanup_video_on_destroy(self, _window):
        if self.video_running or self.video_processes:
            self.stop_remote_video()

    def copy_selected_remote_path(self, _button):
        item = self.selected_remote_item
        path = item["path"] if item else self.remote_path_entry.get_text()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(path, -1)
        clipboard.store()
        self.set_file_info_text(f"Đã copy path:\n{path}")

    def finish_file_operation(self, message):
        self.file_running = False
        self.set_file_info_text(message)
        self.update_file_buttons()
        return False

    def store_current_config(self):
        self.config = self.current_config()
        if self.iface_entry.get_text().strip() != self.config["iface"]:
            self.iface_entry.set_text(self.config["iface"])
        save_config(self.config)

    def save_current_config(self, _button=None):
        self.store_current_config()
        self.last_action = "Đã lưu thông số cổng cho lần mở sau."
        self.set_action_text(self.last_action)
        self.refresh_async()

    def set_banner(self, text, state):
        ctx = self.banner.get_style_context()
        for css_class in ("ok", "warn", "bad"):
            ctx.remove_class(css_class)
        ctx.add_class(state)
        self.banner.set_text(text)

    def configure_ip(self, _button):
        self.store_current_config()
        self.run_service_action("Đang cấu hình IP...", lambda: configure_ip_service(self.config))

    def connect_adb(self, _button):
        self.store_current_config()
        self.run_adb_reconnect(self.config)

    def choose_update_file_for_adb(self, _button):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False
        if self.file_running or self.video_running or self.dashboard_running:
            self.set_action_text("Đang có thao tác khác chạy. Dừng thao tác đó trước khi Update ADB.")
            return False
        if not self.adb_ready_for_file_refresh():
            self.set_action_text("ADB chưa ở trạng thái device nên chưa thể Update ADB.")
            return False

        dialog = Gtk.FileChooserDialog(
            title="Chọn file update ADB .bin",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.set_modal(True)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            "Chọn file update",
            Gtk.ResponseType.OK,
        )
        home_dir = os.path.expanduser("~")
        dialog.set_current_folder(home_dir if os.path.isdir(home_dir) else preferred_file_dialog_dir())

        update_filter = Gtk.FileFilter()
        update_filter.set_name("Update bin (*.bin)")
        update_filter.add_pattern("*.bin")
        update_filter.add_pattern("*.BIN")
        dialog.add_filter(update_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("Tất cả file")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        response = dialog.run()
        update_path = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        if not update_path:
            return False

        self.store_current_config()
        return self.run_adb_update_action(self.config, update_path)

    def choose_debug_file_for_root(self, _button):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False
        if self.file_running or self.video_running:
            self.set_action_text("Đang có thao tác file/video chạy. Dừng thao tác đó trước khi Get Root.")
            return False
        if not self.adb_ready_for_file_refresh():
            self.set_action_text("ADB chưa ở trạng thái device nên chưa thể Get Root.")
            return False
        if self.last_status.get("root_ok"):
            root_output = self.last_status.get("root_output") or "uid=0(root)"
            self.set_action_text(f"Thiết bị đã có quyền root.\n{root_output}")
            return False

        dialog = Gtk.FileChooserDialog(
            title="Chọn file debug .bin để Get Root",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.set_modal(True)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            "Chọn file",
            Gtk.ResponseType.OK,
        )
        dialog.set_current_folder(preferred_file_dialog_dir())

        debug_filter = Gtk.FileFilter()
        debug_filter.set_name("Debug bin (*.bin)")
        debug_filter.add_pattern("*.bin")
        debug_filter.add_pattern("*.BIN")
        dialog.add_filter(debug_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("Tất cả file")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        response = dialog.run()
        debug_path = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        if not debug_path:
            return False

        self.store_current_config()
        return self.run_get_root(self.config, debug_path)

    def run_adb_update_action(self, config, update_path):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        validation_error = validate_update_bin_path(update_path)
        if validation_error:
            self.set_action_text(validation_error)
            self.set_update_progress(0.0, "File update không hợp lệ")
            return False

        if self.live_log_running or self.live_log_starting:
            self.stop_live_log_process("Đã dừng Log realtime trước khi Update ADB.", manual=False)

        self.action_running = True
        self.adb_update_running = True
        self.set_banner("ĐANG UPDATE ADB...", "warn")
        self.set_update_progress(0.0, "Chuẩn bị update ADB")
        self.set_action_text("Đang chuẩn bị Update ADB...")
        self.refresh_action_controls()
        if hasattr(self, "dashboard_panel"):
            self.dashboard_panel.set_busy(True)

        log_lines = []

        def append_log(message):
            text = clean_command_output(str(message or ""))
            if not text:
                return
            log_lines.append(f"[{time.strftime('%H:%M:%S')}] {text}")
            GLib.idle_add(self.set_action_text, "\n".join(log_lines))

        def update_progress(fraction, message):
            GLib.idle_add(self.set_update_progress, fraction, message)

        append_log("Đang chuẩn bị quy trình Update ADB...")
        append_log(f"Remote path: {ADB_UPDATE_REMOTE_PATH}")

        def worker():
            try:
                result = run_adb_update(config, update_path, log=append_log, progress=update_progress)
            except Exception as exc:
                result = {"ok": False, "message": f"Lỗi không xử lý khi Update ADB: {exc}"}
            status = "OK" if result.get("ok") else "LỖI"
            append_log(f"Kết quả {status}: {result.get('message', '')}")
            GLib.idle_add(self.finish_adb_update_action, result, "\n".join(log_lines))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def drop_root(self, _button):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False
        if self.file_running or self.video_running:
            self.set_action_text("Đang có thao tác file/video chạy. Dừng thao tác đó trước khi Thoát Root.")
            return False
        if not self.adb_ready_for_file_refresh():
            self.set_action_text("ADB chưa ở trạng thái device nên chưa thể Thoát Root.")
            return False
        if not self.last_status.get("root_ok"):
            root_output = self.last_status.get("root_output") or "uid khác 0"
            self.set_action_text(f"Thiết bị đang chưa root.\n{root_output}")
            return False

        self.store_current_config()
        return self.run_drop_root(self.config)

    def run_get_root(self, config, debug_path):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        validation_error = validate_debug_bin_path(debug_path)
        if validation_error:
            self.set_action_text(validation_error)
            return False

        self.action_running = True
        self.set_banner("ĐANG GET ROOT...", "warn")
        self.set_get_root_button_ready(False, False)
        self.set_drop_root_button_ready(False, False)
        self.set_terminal_button_ready(False)

        log_lines = []

        def append_log(message):
            text = clean_command_output(str(message or ""))
            if not text:
                return
            log_lines.append(f"[{time.strftime('%H:%M:%S')}] {text}")
            GLib.idle_add(self.set_action_text, "\n".join(log_lines))

        append_log("Đang chuẩn bị quy trình Get Root...")

        def worker():
            try:
                result = get_root_with_debug_file(config, debug_path, log=append_log)
            except Exception as exc:
                result = f"Lỗi không xử lý khi Get Root: {exc}"
            append_log(f"Kết quả: {result}")
            GLib.idle_add(self.finish_action, "\n".join(log_lines))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def run_drop_root(self, config):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        if self.live_log_running or self.live_log_starting:
            self.stop_live_log_process("Đã dừng Log realtime trước khi Thoát Root.", manual=False)

        self.action_running = True
        self.set_banner("ĐANG THOÁT ROOT...", "warn")
        self.set_get_root_button_ready(False, False)
        self.set_drop_root_button_ready(False, False)
        self.set_terminal_button_ready(False)

        log_lines = []

        def append_log(message):
            text = clean_command_output(str(message or ""))
            if not text:
                return
            log_lines.append(f"[{time.strftime('%H:%M:%S')}] {text}")
            GLib.idle_add(self.set_action_text, "\n".join(log_lines))

        append_log("Đang chuẩn bị Thoát Root...")

        def worker():
            try:
                result = drop_adb_root(config, log=append_log)
            except Exception as exc:
                result = f"Lỗi không xử lý khi Thoát Root: {exc}"
            append_log(f"Kết quả: {result}")
            GLib.idle_add(self.finish_action, "\n".join(log_lines))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def reset_all(self, _button=None):
        self.store_current_config()
        self.run_clean_reset(self.config, include_current=True, startup=False)

    def startup_reset(self):
        self.run_clean_reset(self.current_config(), include_current=False, startup=True)
        return False

    def run_clean_reset(self, config, include_current=False, startup=False):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        self.action_running = True
        self.set_banner("ĐANG RESET SẠCH ADB/IP...", "warn")
        self.set_action_text("Đang dọn ADB cũ và gán lại IP adapter...")

        def worker():
            message = clean_reset(config, include_current=include_current)
            if startup:
                message = f"Reset khi mở app:\n{message}"
            GLib.idle_add(self.finish_action, message)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def run_adb_reconnect(self, config):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        if self.live_log_running or self.live_log_starting:
            self.stop_live_log_process("Đã dừng Log realtime trước khi reconnect ADB.", manual=False)

        self.action_running = True
        self.set_banner("ĐANG CONNECT ADB...", "warn")
        self.set_action_text("Đang canh ADB trong 60 giây. Có thể reset BLTN ngay bây giờ.")

        def worker():
            message = adb_reconnect(config)
            GLib.idle_add(self.finish_action, message)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def open_terminal(self, _button):
        _ok, message = open_terminal_session()
        self.last_action = message
        self.set_action_text(message)

    def dashboard_cmdtool_feature(self, feature_id, enabled):
        feature = CMDTOOL_FEATURES.get(feature_id, {})
        state = "on" if enabled else "off"
        title = f"{feature.get('label', feature_id)}: {'Bật' if enabled else 'Tắt'}"
        command = f"cmdtool {feature.get('command', feature_id)} {state}"
        return self.run_dashboard_task(
            title,
            command,
            lambda config: set_cmdtool_feature(config, feature_id, enabled),
        )

    def dashboard_log_level(self, level):
        title = f"Log level: {level}"
        return self.run_dashboard_task(
            title,
            f"cmdtool log level {level}",
            lambda config: set_log_level(config, level),
        )

    def dashboard_service_feature(self, service_id, enabled):
        service = SERVICE_CONTROLS.get(service_id, {})
        service_name = service.get("service", service_id)
        state_label = "Bật" if enabled else "Tắt"
        title = f"{service.get('label', service_id)}: {state_label}"
        return self.run_dashboard_task(
            title,
            f"service {service_name} {'on' if enabled else 'off'}",
            lambda config: set_service_feature(config, service_id, enabled),
        )

    def dashboard_refresh_status(self, auto=False):
        return self.run_dashboard_task(
            "Kiểm tra trạng thái runtime ECU",
            "runtime status snapshot",
            collect_runtime_status,
            auto=auto,
        )

    def run_dashboard_task(self, title, command_label, action, auto=False):
        if not hasattr(self, "dashboard_panel"):
            return False
        if self.dashboard_running:
            if auto:
                return False
            self.dashboard_panel.show_local_message(
                "Dashboard đang bận",
                "Đang có command dashboard chạy, bỏ qua lệnh mới để tránh chạy chồng.",
                ok=False,
            )
            return False
        if self.action_running:
            if auto:
                return False
            self.dashboard_panel.show_local_message(
                "ADB đang bận",
                "Đang có thao tác ADB khác chạy, chờ thao tác đó xong rồi thử lại.",
                ok=False,
            )
            return False

        self.store_current_config()
        if not self.last_status.get("adb_ok"):
            if auto:
                return False
            self.dashboard_panel.show_local_message(
                "ADB chưa connected",
                "Dashboard cần ADB ở trạng thái device. Bấm ADB Connect trước.",
                ok=False,
            )
            return False

        self.dashboard_running = True
        if not auto:
            self.action_running = True
            self.set_banner("ĐANG CHẠY DASHBOARD COMMAND...", "warn")
            self.set_get_root_button_ready(False, False)
            self.set_drop_root_button_ready(False, False)
            self.set_terminal_button_ready(False)
            self.update_live_log_controls()
        self.dashboard_panel.show_command_started(title, command_label, auto=auto)
        config = dict(self.config)

        def worker():
            try:
                result = action(config)
            except Exception as exc:
                result = {
                    "ok": False,
                    "title": title,
                    "command": command_label,
                    "message": f"Lỗi không xử lý khi chạy dashboard command: {exc}",
                    "code": 1,
                    "timestamp": time.strftime("%H:%M:%S"),
                }
            result["auto"] = bool(auto)
            GLib.idle_add(self.finish_dashboard_task, result)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def finish_dashboard_task(self, result):
        was_auto = bool(result.get("auto")) if isinstance(result, dict) else False
        self.dashboard_running = False
        if not was_auto:
            self.action_running = False
        if not isinstance(result, dict):
            result = {
                "ok": False,
                "title": "Dashboard command",
                "command": "",
                "message": str(result),
                "code": 1,
                "timestamp": time.strftime("%H:%M:%S"),
            }
        self.dashboard_panel.show_command_result(result)
        if not was_auto:
            self.refresh_async()
        return False

    def run_service_action(self, start_message, action):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        self.action_running = True
        self.set_banner("ĐANG CHẠY LỆNH...", "warn")
        self.set_action_text(start_message)

        def worker():
            try:
                message = action()
            except Exception as exc:
                message = f"Lỗi không xử lý khi chạy thao tác: {exc}"
            GLib.idle_add(self.finish_action, message)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def run_action(self, start_message, commands, timeout):
        if self.action_running:
            self.set_action_text("Đang có lệnh chạy, bỏ qua lệnh mới để tránh chạy chồng.")
            return False

        self.action_running = True
        self.set_banner("ĐANG CHẠY LỆNH...", "warn")
        self.set_action_text(start_message)

        def worker():
            message = run_command_sequence(commands, timeout, purpose="action")
            GLib.idle_add(self.finish_action, message)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def finish_action(self, message):
        self.action_running = False
        self.last_action = message
        self.set_action_text(message)
        self.refresh_action_controls()
        self.refresh_async()
        return False

    def finish_adb_update_action(self, result, message):
        self.adb_update_running = False
        self.action_running = False
        ok = bool(result.get("ok")) if isinstance(result, dict) else False
        self.last_action = message
        self.set_action_text(message)
        self.set_update_progress(
            1.0 if ok else 0.0,
            "Update ADB hoàn tất" if ok else "Update ADB lỗi - xem log",
        )
        if hasattr(self, "dashboard_panel"):
            self.dashboard_panel.set_busy(False)
        self.refresh_action_controls()
        self.refresh_async()
        return False

    def show_help(self, _button):
        dialog = Gtk.Window(title="Adapter Status Help")
        dialog.set_transient_for(self)
        dialog.set_default_size(760, 640)
        dialog.set_border_width(12)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        dialog.add(root)

        title = Gtk.Label(label="Hướng Dẫn Adapter Status")
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        root.pack_start(title, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        root.pack_start(scrolled, True, True, 0)

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_monospace(False)
        text_view.get_buffer().set_text(HELP_TEXT)
        scrolled.add(text_view)

        close_button = Gtk.Button(label="Đóng")
        close_button.connect("clicked", lambda _button: dialog.destroy())
        root.pack_start(close_button, False, False, 0)

        dialog.show_all()

    def refresh_async(self):
        if self.action_running:
            return True
        if self.poll_running:
            return True

        self.poll_running = True
        config = self.current_config()

        def worker():
            try:
                status = collect_status(config)
            except Exception as exc:
                status = {
                    "banner_text": "LỖI KIỂM TRA TRẠNG THÁI",
                    "banner_state": "bad",
                    "details": f"Polling worker lỗi: {exc}",
                    "device_info": DEVICE_INFO_EMPTY_TEXT,
                    "adb_ok": False,
                    "adb_state": "",
                    "root_ok": False,
                    "root_output": "",
                }
            GLib.idle_add(self.apply_status, status)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def apply_status(self, status):
        self.poll_running = False
        self.last_status = dict(status)
        self.set_banner(status["banner_text"], status["banner_state"])
        self.refresh_action_controls(status)
        if hasattr(self, "dashboard_panel"):
            self.dashboard_panel.set_adb_status(status)
        if self.live_log_running or self.live_log_starting:
            if self.live_log_root_ready(status):
                self.live_log_not_ready_count = 0
            else:
                self.live_log_not_ready_count += 1
                if self.live_log_not_ready_count >= 3:
                    self.stop_live_log_process(
                        "ADB/root mất liên tiếp, đã dừng Log realtime.",
                        manual=False,
                    )
        elif self.notebook.get_current_page() == getattr(self, "live_log_page_num", -1):
            self.live_log_not_ready_count = 0
            self.update_live_log_idle_status(status)

        self.set_details_text(status["details"])
        self.set_device_info_line(status.get("device_info", DEVICE_INFO_EMPTY_TEXT))
        return False

    def refresh_action_controls(self, status=None):
        status = status if status is not None else getattr(self, "last_status", {})
        adb_ready = bool(status.get("adb_ok") or status.get("adb_state") == "device")
        root_ok = bool(status.get("root_ok"))
        self.set_config_controls_locked(self.action_running)
        self.set_terminal_button_ready(adb_ready)
        self.set_update_adb_button_ready(adb_ready)
        self.set_get_root_button_ready(adb_ready, root_ok)
        self.set_drop_root_button_ready(adb_ready, root_ok)
        self.update_file_buttons()
        self.update_live_log_controls(status)

    def set_config_controls_locked(self, locked):
        ready = not bool(locked)
        for widget in (
            getattr(self, "iface_entry", None),
            getattr(self, "host_entry", None),
            getattr(self, "device_entry", None),
            getattr(self, "port_entry", None),
            getattr(self, "configure_button", None),
            getattr(self, "connect_button", None),
            getattr(self, "help_button", None),
        ):
            if widget is not None:
                widget.set_sensitive(ready)

    def set_update_progress(self, fraction, message):
        if not hasattr(self, "adb_update_progress"):
            return False
        fraction = max(0.0, min(1.0, float(fraction or 0.0)))
        percent = int(round(fraction * 100))
        self.adb_update_progress.set_fraction(fraction)
        self.adb_update_progress.set_text(f"{percent}% - {message or 'Update ADB'}")
        return False

    def set_update_adb_button_ready(self, adb_ready):
        if not hasattr(self, "update_adb_button"):
            return
        blocked_by_action = self.action_running
        running = self.adb_update_running
        ready = bool(adb_ready) and not blocked_by_action

        self.update_adb_button.set_sensitive(ready)
        if running:
            tooltip = "Đang chạy Update ADB."
        elif blocked_by_action:
            tooltip = "Đang chạy thao tác khác."
        elif not adb_ready:
            tooltip = "ADB chưa connect."
        else:
            tooltip = f"Chọn file .bin, push vào {ADB_UPDATE_REMOTE_PATH}, sync rồi chạy update cpu."
        self.update_adb_button.set_tooltip_text(tooltip)

        ctx = self.update_adb_button.get_style_context()
        for css_class in ("update-ready", "update-running", "update-wait"):
            ctx.remove_class(css_class)
        if running:
            ctx.add_class("update-running")
        elif ready:
            ctx.add_class("update-ready")
        else:
            ctx.add_class("update-wait")

    def set_get_root_button_ready(self, adb_ready, root_ok=False):
        if not hasattr(self, "get_root_button"):
            return
        blocked_by_action = self.action_running
        adb_ready = bool(adb_ready)
        root_ok = bool(root_ok) and adb_ready
        ready = adb_ready and not blocked_by_action

        self.get_root_button.set_label("Root OK" if root_ok else "Get Root")
        self.get_root_button.set_sensitive(ready)
        if blocked_by_action:
            tooltip = "Đang chạy thao tác khác."
        elif not adb_ready:
            tooltip = "ADB chưa connect."
        elif root_ok:
            tooltip = "Thiết bị đã có quyền root."
        else:
            tooltip = "Chọn file DEBUG...bin và chạy quy trình lấy root."
        self.get_root_button.set_tooltip_text(tooltip)

        ctx = self.get_root_button.get_style_context()
        for css_class in ("root-ready", "root-needed", "root-ok", "root-wait"):
            ctx.remove_class(css_class)
        if not ready:
            ctx.add_class("root-wait")
        elif root_ok:
            ctx.add_class("root-ok")
        else:
            ctx.add_class("root-needed")

    def set_drop_root_button_ready(self, adb_ready, root_ok=False):
        if not hasattr(self, "drop_root_button"):
            return
        blocked_by_action = self.action_running
        adb_ready = bool(adb_ready)
        root_ok = bool(root_ok) and adb_ready
        ready = adb_ready and root_ok and not blocked_by_action

        self.drop_root_button.set_sensitive(ready)
        if blocked_by_action:
            tooltip = "Đang chạy thao tác khác."
        elif not adb_ready:
            tooltip = "ADB chưa connect."
        elif not root_ok:
            tooltip = "Thiết bị đang chưa root."
        else:
            tooltip = "Chạy adb unroot để về user adb và test Get Root lại."
        self.drop_root_button.set_tooltip_text(tooltip)

        ctx = self.drop_root_button.get_style_context()
        for css_class in ("unroot-ready", "unroot-wait"):
            ctx.remove_class(css_class)
        ctx.add_class("unroot-ready" if ready else "unroot-wait")

    def set_terminal_button_ready(self, ready):
        blocked_by_action = self.action_running
        ready = bool(ready) and not blocked_by_action
        self.open_terminal_button.set_sensitive(ready)
        self.open_terminal_button.set_tooltip_text(
            "Mở terminal và chạy ./adb.sh"
            if ready
            else "Đang chạy thao tác khác."
            if blocked_by_action
            else "ADB chưa connect."
        )
        ctx = self.open_terminal_button.get_style_context()
        for css_class in ("terminal-ready", "terminal-wait"):
            ctx.remove_class(css_class)
        ctx.add_class("terminal-ready" if ready else "terminal-wait")




def run():
    app = AdapterStatus()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()
