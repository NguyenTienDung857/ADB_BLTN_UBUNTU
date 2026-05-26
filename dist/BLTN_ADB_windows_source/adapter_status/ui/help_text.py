HELP_TEXT = """HƯỚNG DẪN SỬ DỤNG ADAPTER STATUS

Mục đích
App này dùng để quan sát trạng thái cổng USB Network Adapter và trạng thái ADB tới thiết bị.
App tự cập nhật mỗi 1 giây và không cần bạn gõ lệnh kiểm tra thủ công.

Thông số đang dùng
- Tên cổng: enx1c860b2bbfcf
- IP adapter trên máy tính: 192.168.244.10/24
- IP thiết bị: 192.168.244.1
- ADB port: 4321
- File lưu cấu hình: ~/.config/adapter-status/config.json
- Script kết nối ADB: /home/bltn/BLTN_ADB/docs/adb.sh

Cách mở app
1. Double-click icon Adapter Status ngoài Desktop.
2. Hoặc mở terminal và chạy:
   /home/bltn/BLTN_ADB/adapter-status-ui
3. Trên Windows, chạy run_windows.cmd bằng Run as administrator sau khi cài MSYS2 GTK/PyGObject và adb.exe.

Ý nghĩa các trường trên app
- Tên cổng: tên network adapter mà app đang theo dõi.
- IP adapter: IP cần gán cho máy tính trên cổng USB Ethernet.
- IP thiết bị: IP của thiết bị ở đầu bên kia.
- ADB port: cổng TCP dùng cho ADB.
- Trạng thái kết nối cổng: Đã kết nối nghĩa là có link vật lý; Chưa kết nối nghĩa là chưa có link hoặc đã rút cổng.
- IP hiện tại: IP thực tế đang có trên cổng.
- Ping thiết bị: OK nghĩa là mạng tới thiết bị thông.
- ADB status: device nghĩa là ADB đã sẵn sàng.

Quy trình khi rút/cắm lại cổng
1. Mở app Adapter Status.
2. Rút/cắm lại cổng USB Network Adapter.
3. Quan sát dòng trạng thái lớn ở giữa app.
4. Nếu thấy đã có link nhưng chưa có IP hoặc chưa ADB, bấm ADB Connect.
5. Nếu cửa sổ ADB ngắn, bấm ADB Connect trước rồi reset BLTN khi app đang canh.
6. Khi thấy CONNECTED - ADB READY, có thể bấm Mở Terminal hoặc dùng adb shell.

Ý nghĩa trạng thái lớn
- CHƯA THẤY ADAPTER: máy chưa nhận cổng USB Network Adapter.
- CHƯA CẮM / CHƯA CÓ LINK: có adapter nhưng link vật lý chưa lên, thường là dây/cổng chưa cắm đúng.
- CÓ LINK, CHƯA CÓ IP - BẤM ADB CONNECT: link vật lý đã lên nhưng cổng chưa có IP 192.168.244.10/24.
- ĐANG CHỜ BLTN LÊN MẠNG: IP trên máy đã có nhưng chưa thấy thiết bị 192.168.244.1.
- ADB CHƯA CONNECT - BẤM ADB CONNECT: mạng đã OK nhưng ADB chưa connect.
- CONNECTED - ADB READY: kết nối đầy đủ, có thể dùng adb shell.
- CONNECTED - ADB ROOT READY: ADB đã connect và adb shell id đang trả uid=0(root).

Các nút thao tác
- Cấu hình IP: gán IP adapter cho cổng đang chọn và bật cổng lên.
- ADB Connect: gán lại IP, dọn ADB cũ/treo, rồi canh bắt ADB trong 60 giây.
- Update ADB: chỉ sáng khi ADB đã connect; chọn file update .bin, app tự push vào /tmp/cpu_update.bin, sync, kiểm tra size rồi chạy cmdtool update cpu. Trong lúc update app khóa các nút khác và hiển thị % trên thanh tiến trình.
- Mở Terminal: chỉ sáng khi ADB đã connect; mở terminal tại thư mục app và chạy docs/adb.sh.
- Get Root: khi ADB đã connect nhưng chưa root, nút màu đỏ; chọn file DEBUG...bin rồi app tự push, chạy update cpu, chạy change_file và chờ thiết bị tự reboot.
- Root OK: khi adb shell id trả uid=0(root), nút Get Root đổi màu xanh để báo thiết bị đã có quyền root.
- Thoát Root: khi đã root, app chạy adb unroot và kiểm tra adb shell id về uid=2000(adb) để test Get Root lại.
- Help: mở hướng dẫn này.

Tab File Explorer
- Chỉ dùng khi ADB status là device.
- Khi bấm tab File Explorer và ADB đang là device, app tự Refresh đường dẫn hiện tại.
- Khi ADB đang là device, app tự đồng bộ lại thư mục hiện tại mỗi 30 giây.
- Có thể nhập đường dẫn như /, /etc, /data, /firmware rồi bấm Refresh hoặc Enter.
- Double-click thư mục để mở, bấm Up để quay lên thư mục cha.
- File/thư mục có icon nhận diện nhanh: thư mục, ảnh, video, text/log, database và file thường.
- Có thể bấm tiêu đề cột Tên/Loại/Size/Sửa lúc để đổi sort nhanh.
- Bấm Focus để ẩn phần phụ, chỉ giữ vùng file/thư mục lớn và thanh Up/đường dẫn/Thoát focus.
- Chọn file thường rồi bấm Xem text để đọc tối đa 32768 bytes đầu tiên.
- Chọn file thường rồi bấm Pull file về máy để tải về thư mục /home/bltn/BLTN_ADB/ecu-files.
- Chọn file ảnh rồi bấm Xem ảnh, hoặc double-click file ảnh để mở ảnh trực tiếp qua ADB.
- Chọn file video rồi bấm Mở video trực tiếp để stream qua ADB bằng mpv. App dùng URL local có hỗ trợ seek/range, không tải toàn bộ file trước.
- Bấm Dừng video để đóng stream nếu cần.
- Tab này chỉ đọc trên ECU. Không có nút xóa/sửa/push/chmod/remount để tránh làm hỏng build.

Tab Log realtime
- Tab này nằm cạnh File Explorer và đọc log hệ thống realtime bằng journalctl -f.
- Nút Start chỉ bật khi ADB status là device và Root status là OK - uid=0(root).
- Tab này in đúng output của journalctl -f: vài dòng gần nhất rồi tiếp tục theo dõi realtime.
- Bấm Stop để dừng stream trước khi disconnect hoặc Thoát Root.

Khi nào cần sửa thông số
Nếu sau khi rút/cắm lại mà tên cổng thay đổi, sửa ô Tên cổng rồi bấm Cấu hình IP hoặc ADB Connect để lưu và dùng cấu hình mới.
Cách xem tên cổng bằng terminal:
   ip -br link
Trên Windows, xem tên adapter trong Control Panel/Network Connections hoặc PowerShell:
   Get-NetAdapter

Với máy hiện tại, cổng đúng đang dùng là:
   enx1c860b2bbfcf

Cách dùng adb.sh
Khi app báo CONNECTED - ADB READY, bấm Mở Terminal hoặc mở terminal tại /home/bltn/BLTN_ADB và chạy:
   bash docs/adb.sh
Trên Windows, Mở Terminal sẽ chạy:
   docs\\adb_windows.cmd

Script adb.sh sẽ:
1. Đọc thông số từ file cấu hình của app.
2. Tự gán IP cho cổng.
3. Tự set ADB_VENDOR_KEYS.
4. Kết nối ADB tới thiết bị.
5. Mở adb shell.

Xử lý lỗi thường gặp
- No such device: tên cổng sai hoặc cổng chưa được máy nhận. Mở app, kiểm tra Tên cổng, hoặc dùng ip -br link để xem tên thật.
- unauthorized: ADB key chưa được thiết bị chấp nhận hoặc ADB server chạy sai key. Chạy source ~/.bashrc rồi bash docs/adb.sh; nếu thiết bị có màn hình xác nhận thì chọn allow.
- offline: ADB server đang giữ transport cũ; bấm ADB Connect để app dọn và bắt lại.
- Connection refused: mạng ping được nhưng ADB service trên thiết bị chưa mở port 4321. Bấm ADB Connect trước rồi reset BLTN trong lúc app đang canh.
- Ping Fail: kiểm tra dây/cổng, sau đó bấm Cấu hình IP.

Lệnh kiểm tra nhanh bằng terminal
   ip -br addr show enx1c860b2bbfcf
   ping -c 3 192.168.244.1
   adb devices
   adb shell

Ghi chú vận hành
Luôn dùng app để xem trạng thái trước. Khi trạng thái đã là CONNECTED - ADB READY thì mới chạy adb shell hoặc bash docs/adb.sh để tránh lỗi kết nối.
Terminal do app mở sẽ truyền ADAPTER_STATUS_TRACK=1 để adb.sh tự ghi PID của session ADB."""
