# BLTN ADB Docs

Tài liệu vận hành của dự án nằm trong thư mục này.

- `ARCHITECTURE.md`: kiến trúc Python sau khi tách layer UI, service và ADB executor.
- `WINDOWS_PACKAGE.md`: hướng dẫn chạy/đóng gói bản Windows dùng MSYS2 GTK, `adb.exe`, `netsh`.
- `smoke_windows.cmd`, `validate_windows_with_device.cmd` ở thư mục gốc: kiểm runtime/app và kiểm kết nối BLTN thật trên Windows.
- `README_ADB.md`: hướng dẫn ADB/operator chính.
- `hướng dẫn update file debug lấy quyền root.md`: transcript hướng dẫn update debug để lấy root.
- `how to check version.md`: hướng dẫn kiểm tra version.
- `command to show log.md`: lệnh xem log.
- `báo cáo quét sâu built-in cam ADB.md`: báo cáo quét built-in camera qua ADB.
- `adb.sh`: script kết nối ADB hiện tại; app tự tìm file này trong `docs/`.
- `adb_windows.cmd`: script mở ADB shell khi chạy app trên Windows.
- `adbscript_linux.sh`, `adbscript_window.bat`: script setup cũ.
- `cpu_update.bin`, `YOEUK_public.pem`, `vrs_update_info`, `interfaces`: payload/key/config vận hành đã được gom vào `docs/`.
- `docx/`: tài liệu gốc dạng Word.
