import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ..services.runtime_controls import CMDTOOL_FEATURES, LOG_LEVELS, SERVICE_CONTROLS
from .widgets import constrain_label_width, make_text_panel


DASHBOARD_LOG_MAX_CHARS = 180000


class DashboardPanel(Gtk.ScrolledWindow):
    def __init__(
        self,
        on_cmdtool_feature,
        on_log_level,
        on_service_feature,
        on_refresh_status,
    ):
        super().__init__()
        self.on_cmdtool_feature = on_cmdtool_feature
        self.on_log_level = on_log_level
        self.on_service_feature = on_service_feature
        self.on_refresh_status = on_refresh_status
        self.command_buttons = []
        self.feature_status_labels = {}
        self.service_status_labels = {}
        self.log_level_status_label = None
        self.busy = False
        self.adb_ready = False
        self._widget_state_classes = {}

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_hexpand(True)
        self.set_vexpand(True)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_border_width(4)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.pack_start(header, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)
        header.pack_start(title_box, True, True, 0)

        title = Gtk.Label(label="Dashboard ECU Runtime")
        title.set_xalign(0)
        title.get_style_context().add_class("title")
        title_box.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label="Điều khiển nhanh logging, log level và runtime service qua ADB.")
        subtitle.set_xalign(0)
        subtitle.get_style_context().add_class("subtitle")
        constrain_label_width(subtitle, max_width_chars=110)
        title_box.pack_start(subtitle, False, False, 0)

        self.adb_pill = Gtk.Label(label="ADB: đang kiểm tra")
        self.adb_pill.set_xalign(0.5)
        self.adb_pill.get_style_context().add_class("dashboard-pill")
        self.adb_pill.get_style_context().add_class("dashboard-warn")
        header.pack_start(self.adb_pill, False, False, 0)

        status_card = self.create_card()
        root.pack_start(status_card, False, False, 0)

        status_grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        status_card.pack_start(status_grid, False, False, 0)

        self.adb_detail_label = Gtk.Label(label="Chưa có dữ liệu ADB.")
        self.adb_detail_label.set_xalign(0)
        self.adb_detail_label.set_hexpand(True)
        self.adb_detail_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.adb_detail_label.get_style_context().add_class("subtitle")
        status_grid.attach(self.adb_detail_label, 0, 0, 1, 1)

        self.command_state_label = Gtk.Label(label="Command: sẵn sàng")
        self.command_state_label.set_xalign(0)
        self.command_state_label.get_style_context().add_class("dashboard-command-state")
        status_grid.attach(self.command_state_label, 0, 1, 1, 1)

        legend_label = Gtk.Label(
            label=(
                "Xanh: ECU đã xác nhận | Cam: đã gửi lệnh nhưng ECU chưa trả trạng thái | "
                "Đỏ: đang tắt"
            )
        )
        legend_label.set_xalign(0)
        legend_label.get_style_context().add_class("dashboard-status-note")
        constrain_label_width(legend_label, max_width_chars=110)
        status_grid.attach(legend_label, 0, 2, 2, 1)

        self.refresh_status_button = self.create_button(
            "Kiểm tra runtime",
            self.on_refresh_status,
            tooltip="Đồng bộ trạng thái runtime trên ECU.",
        )
        status_grid.attach(self.refresh_status_button, 1, 0, 1, 2)

        controls_grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        controls_grid.set_column_homogeneous(True)
        root.pack_start(controls_grid, False, False, 0)

        controls_grid.attach(self.build_logging_card(), 0, 0, 1, 1)
        controls_grid.attach(self.build_services_card(), 1, 0, 1, 1)

        command_card = self.create_card("Trạng thái command")
        root.pack_start(command_card, True, True, 0)

        self.command_title_label = Gtk.Label(label="Chưa chạy command dashboard.")
        self.command_title_label.set_xalign(0)
        self.command_title_label.get_style_context().add_class("dashboard-section-title")
        command_card.pack_start(self.command_title_label, False, False, 0)

        self.command_detail_label = Gtk.Label(label="")
        self.command_detail_label.set_xalign(0)
        self.command_detail_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.command_detail_label.get_style_context().add_class("subtitle")
        command_card.pack_start(self.command_detail_label, False, False, 0)

        self.log_panel, self.log_text = make_text_panel(260, monospace=True, vexpand=True)
        command_card.pack_start(self.log_panel, True, True, 0)
        self.set_log_text("Dashboard sẵn sàng.")

        self.update_control_sensitivity()

    def create_card(self, title=None):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("dashboard-card")
        card.set_hexpand(True)
        if title:
            label = Gtk.Label(label=title)
            label.set_xalign(0)
            label.get_style_context().add_class("dashboard-section-title")
            card.pack_start(label, False, False, 0)
        return card

    def create_button(self, label, callback, *args, tooltip=None):
        button = Gtk.Button(label=label)
        if tooltip:
            button.set_tooltip_text(tooltip)
        button.connect("clicked", lambda _button: callback(*args))
        self.command_buttons.append(button)
        return button

    def build_logging_card(self):
        card = self.create_card("Logging runtime")

        for feature_id, feature in CMDTOOL_FEATURES.items():
            row = self.create_control_row(feature["label"], feature["description"])
            status_label = self.create_status_label("UNKNOWN")
            self.feature_status_labels[feature_id] = status_label
            row.pack_start(status_label, False, False, 0)
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            actions.pack_start(
                self.create_button(
                    "Bật",
                    self.on_cmdtool_feature,
                    feature_id,
                    True,
                    tooltip=f"Chạy cmdtool {feature['command']} on.",
                ),
                False,
                False,
                0,
            )
            actions.pack_start(
                self.create_button(
                    "Tắt",
                    self.on_cmdtool_feature,
                    feature_id,
                    False,
                    tooltip=f"Chạy cmdtool {feature['command']} off.",
                ),
                False,
                False,
                0,
            )
            row.pack_start(actions, False, False, 0)
            card.pack_start(row, False, False, 0)

        level_row = self.create_control_row("Log level", "Chỉnh cmdtool log level từ 1 đến 6.")
        self.log_level_status_label = self.create_status_label("UNKNOWN")
        level_row.pack_start(self.log_level_status_label, False, False, 0)
        level_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.level_combo = Gtk.ComboBoxText()
        for level in LOG_LEVELS:
            self.level_combo.append(str(level), str(level))
        self.level_combo.set_active_id("3")
        level_actions.pack_start(self.level_combo, False, False, 0)
        level_actions.pack_start(
            self.create_button(
                "Áp dụng",
                self.emit_log_level,
                tooltip="Chạy cmdtool log level với giá trị đang chọn.",
            ),
            False,
            False,
            0,
        )
        level_row.pack_start(level_actions, False, False, 0)
        card.pack_start(level_row, False, False, 0)
        return card

    def build_services_card(self):
        card = self.create_card("Runtime service")

        for service_id, service in SERVICE_CONTROLS.items():
            row = self.create_control_row(service["label"], service["description"])
            status_label = self.create_status_label("UNKNOWN")
            self.service_status_labels[service_id] = status_label
            row.pack_start(status_label, False, False, 0)
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            actions.pack_start(
                self.create_button(
                    "Bật",
                    self.on_service_feature,
                    service_id,
                    True,
                    tooltip=f"Bật {service['service']} runtime service.",
                ),
                False,
                False,
                0,
            )
            actions.pack_start(
                self.create_button(
                    "Tắt",
                    self.on_service_feature,
                    service_id,
                    False,
                    tooltip=f"Tắt {service['service']} runtime service.",
                ),
                False,
                False,
                0,
            )
            row.pack_start(actions, False, False, 0)
            card.pack_start(row, False, False, 0)

        return card

    def create_control_row(self, title, description):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.get_style_context().add_class("dashboard-row")

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        row.pack_start(labels, True, True, 0)

        title_label = Gtk.Label(label=title)
        title_label.set_xalign(0)
        title_label.get_style_context().add_class("label")
        labels.pack_start(title_label, False, False, 0)

        desc_label = Gtk.Label(label=description)
        desc_label.set_xalign(0)
        desc_label.get_style_context().add_class("subtitle")
        constrain_label_width(desc_label, max_width_chars=48)
        labels.pack_start(desc_label, False, False, 0)
        return row

    def create_status_label(self, text):
        label = Gtk.Label(label=text)
        label.set_xalign(0.5)
        label.set_size_request(150, -1)
        label.get_style_context().add_class("dashboard-status-badge")
        label.get_style_context().add_class("dashboard-warn")
        return label

    def emit_log_level(self):
        self.on_log_level(self.level_combo.get_active_id() or "3")

    def set_adb_status(self, status):
        status = status or {}
        adb_ok = bool(status.get("adb_ok"))
        root_ok = bool(status.get("root_ok"))
        state = status.get("adb_state") or ("device" if adb_ok else "disconnected")
        target = status.get("target", "")
        self.adb_ready = adb_ok

        if adb_ok and root_ok:
            text = "ADB: ROOT READY"
            css_state = "dashboard-ok"
        elif adb_ok:
            text = "ADB: CONNECTED"
            css_state = "dashboard-ok"
        elif state == "offline":
            text = "ADB: OFFLINE"
            css_state = "dashboard-warn"
        else:
            text = "ADB: DISCONNECTED"
            css_state = "dashboard-bad"

        self.set_state_class(self.adb_pill, css_state)
        self.set_label_text(self.adb_pill, text)
        self.set_label_text(
            self.adb_detail_label,
            f"Target: {target or '--'} | State: {state} | Root: {'uid=0(root)' if root_ok else 'chưa root'}"
        )
        self.update_control_sensitivity()

    def set_busy(self, busy):
        self.busy = bool(busy)
        self.set_label_text(
            self.command_state_label,
            "Command: đang chạy" if self.busy else "Command: sẵn sàng",
        )
        self.set_state_class(self.command_state_label, "dashboard-warn" if self.busy else "dashboard-ok")
        self.update_control_sensitivity()

    def update_control_sensitivity(self):
        enabled = self.adb_ready and not self.busy
        for button in self.command_buttons:
            button.set_sensitive(enabled)

    def show_command_started(self, title, command, auto=False):
        if auto:
            return
        self.set_busy(True)
        self.set_label_text(self.command_title_label, title or "Đang chạy command")
        self.set_label_text(self.command_detail_label, command or "")
        self.append_log(f"[{time.strftime('%H:%M:%S')}] RUN: {title}\n{command}")

    def show_command_result(self, result):
        ok = bool(result.get("ok"))
        title = result.get("title") or "Command dashboard"
        command = result.get("command") or ""
        message = result.get("message") or ""
        timestamp = result.get("timestamp") or time.strftime("%H:%M:%S")
        status_text = "OK" if ok else "LỖI"

        self.apply_runtime_snapshot(result.get("snapshot"))
        if result.get("auto"):
            return

        self.set_busy(False)
        self.set_label_text(self.command_title_label, f"{status_text}: {title}")
        self.set_label_text(self.command_detail_label, command)
        self.set_label_text(self.command_state_label, f"Command: {status_text.lower()}")
        self.set_state_class(self.command_state_label, "dashboard-ok" if ok else "dashboard-bad")
        self.append_log(f"[{timestamp}] {status_text}: {title}\nLệnh: {command}\n{message}")

    def show_local_message(self, title, message, ok=False):
        self.show_command_result(
            {
                "ok": ok,
                "title": title,
                "command": "",
                "message": message,
                "timestamp": time.strftime("%H:%M:%S"),
            }
        )

    def set_log_text(self, text):
        buffer = self.log_text.get_buffer()
        buffer.set_text(text or "")

    def apply_runtime_snapshot(self, snapshot):
        if not snapshot:
            return

        for feature_id, item in snapshot.get("features", {}).items():
            label = self.feature_status_labels.get(feature_id)
            if label:
                self.set_runtime_label_state(
                    label,
                    item.get("state"),
                    item.get("source"),
                    confidence=item.get("confidence"),
                )

        log_level = snapshot.get("log_level", {})
        if self.log_level_status_label:
            self.set_runtime_label_state(
                self.log_level_status_label,
                log_level.get("state"),
                log_level.get("source"),
                value_prefix="LEVEL ",
                confidence=log_level.get("confidence"),
            )

        for service_id, item in snapshot.get("services", {}).items():
            label = self.service_status_labels.get(service_id)
            if label:
                self.set_runtime_label_state(
                    label,
                    item.get("state"),
                    item.get("source"),
                    service=True,
                    confidence=item.get("confidence"),
                )

    def set_runtime_label_state(
        self,
        label,
        state,
        source="",
        value_prefix="",
        service=False,
        confidence="unknown",
    ):
        state = str(state or "unknown").lower()
        local = confidence == "local"
        if state == "on":
            text = "ĐÃ GỬI BẬT" if local else "BẬT"
            css_state = "dashboard-warn" if local else "dashboard-ok"
        elif state == "off":
            text = "ĐÃ GỬI TẮT" if local else "TẮT"
            css_state = "dashboard-warn" if local else "dashboard-bad"
        elif state == "active":
            text = "BẬT"
            css_state = "dashboard-ok"
        elif state == "inactive":
            text = "TẮT"
            css_state = "dashboard-bad"
        elif state in {"1", "2", "3", "4", "5", "6"}:
            text = f"ĐÃ GỬI L{state}" if local else f"{value_prefix}{state}".strip()
            css_state = "dashboard-warn" if local else "dashboard-ok"
        else:
            text = "UNKNOWN"
            css_state = "dashboard-warn"

        self.set_label_text(label, text)
        if local:
            label.set_tooltip_text(
                f"{source or 'ECU chưa trả trạng thái xác nhận.'} Trạng thái này chưa được xác nhận từ ECU."
            )
        else:
            label.set_tooltip_text(source or "Chưa đọc được trạng thái từ ECU.")
        self.set_state_class(label, css_state)

    def append_log(self, text):
        text = str(text or "").strip()
        if not text:
            return
        buffer = self.log_text.get_buffer()
        end_iter = buffer.get_end_iter()
        if buffer.get_char_count() > 0:
            buffer.insert(end_iter, "\n\n")
            end_iter = buffer.get_end_iter()
        buffer.insert(end_iter, text)

        overage = buffer.get_char_count() - DASHBOARD_LOG_MAX_CHARS
        if overage > 0:
            trim_start = buffer.get_start_iter()
            trim_end = buffer.get_iter_at_offset(overage)
            trim_end.forward_line()
            buffer.delete(trim_start, trim_end)

        mark = buffer.create_mark(None, buffer.get_end_iter(), False)
        self.log_text.scroll_mark_onscreen(mark)
        buffer.delete_mark(mark)

    def set_state_class(self, widget, active_class):
        key = id(widget)
        if self._widget_state_classes.get(key) == active_class:
            return
        ctx = widget.get_style_context()
        for css_class in ("dashboard-ok", "dashboard-warn", "dashboard-bad"):
            ctx.remove_class(css_class)
        ctx.add_class(active_class)
        self._widget_state_classes[key] = active_class

    def set_label_text(self, label, text):
        text = text or ""
        if label.get_text() != text:
            label.set_text(text)
