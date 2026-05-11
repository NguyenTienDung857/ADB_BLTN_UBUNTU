# BLTN ADB - Hướng Dẫn Cài Đặt Và Sử Dụng

Cập nhật: 2026-05-09

Tài liệu này ghi lại toàn bộ cấu hình ADB, USB Network Adapter, app **Adapter Status**, và cách thao tác khi rút/cắm lại cổng.

## 1. Thông Số Đang Dùng

Các thông số hiện tại đã được lưu trong:

```bash
~/.config/adapter-status/config.json
```

Nội dung cấu hình hiện tại:

```json
{
  "adb_port": "4321",
  "device_ip": "192.168.244.1",
  "host_cidr": "192.168.244.10/24",
  "iface": "enx1c860b2bbfcf"
}
```

Ý nghĩa:

- `iface`: tên cổng USB Network Adapter trên máy tính.
- `host_cidr`: IP gán cho adapter trên máy tính.
- `device_ip`: IP thiết bị ở đầu bên kia.
- `adb_port`: cổng TCP dùng cho ADB.

## 2. Các File Quan Trọng

- Thư mục tài liệu và công cụ: `~/BLTN_ADB`
- Script kết nối ADB: `~/BLTN_ADB/adb.sh`
- App quan sát trạng thái cổng: `~/bin/adapter-status-ui`
- Shortcut app ngoài Desktop: `~/Desktop/Adapter Status.desktop`
- File cấu hình app: `~/.config/adapter-status/config.json`
- ADB keys đã cài: `~/.android`
- File cấu hình shell ADB key: `~/.bashrc`

## 3. Cài Đặt ADB Và Công Cụ Mạng

Nếu máy chưa có ADB, cài bằng lệnh:

```bash
sudo apt-get update
sudo apt-get install -y adb net-tools
```

Kiểm tra ADB:

```bash
adb version
```

Kết quả mong muốn tương tự:

```text
Android Debug Bridge version 1.0.41
Version 34.0.5-debian
```

## 4. Cài Đặt ADB Key

ADB key dùng để thiết bị cho phép máy tính kết nối.

Nguồn key trên máy hiện tại:

```bash
~/keys/keys
```

Thư mục đích sau khi cài:

```bash
~/.android
```

Cài key:

```bash
mkdir -p ~/.android
cp -a ~/keys/keys/. ~/.android/
find ~/.android -type f -name adbkey -exec chmod 600 {} +
find ~/.android -type f -name adbkey.pub -exec chmod 644 {} +
find ~/.android -type d -exec chmod 700 {} +
```

Kiểm tra số lượng private key:

```bash
find ~/.android -maxdepth 2 -type f -name adbkey | wc -l
```

Máy hiện tại có khoảng:

```text
61
```

## 5. Cấu Hình ADB_VENDOR_KEYS

ADB server cần biến `ADB_VENDOR_KEYS` để nhận đúng key.

Trong `~/.bashrc` đã có cấu hình:

```bash
if [ -d "$HOME/.android" ]; then
    export ADB_VENDOR_KEYS="$(find "$HOME/.android" -maxdepth 2 -type f -name adbkey | sort | paste -sd: -)"
fi
```

Sau khi sửa `.bashrc`, chạy:

```bash
source ~/.bashrc
```

Kiểm tra:

```bash
printf "%s" "$ADB_VENDOR_KEYS" | tr ":" "\n" | grep -c adbkey
```

## 6. Cấu Hình IP Cho USB Network Adapter

Cổng đang dùng:

```bash
enx1c860b2bbfcf
```

IP adapter cần gán:

```bash
192.168.244.10/24
```

Gán IP thủ công:

```bash
sudo ip addr replace 192.168.244.10/24 dev enx1c860b2bbfcf
sudo ip link set enx1c860b2bbfcf up
```

Kiểm tra:

```bash
ip -br addr show enx1c860b2bbfcf
```

Kết quả mong muốn có:

```text
192.168.244.10/24
```

Kiểm tra link vật lý:

```bash
cat /sys/class/net/enx1c860b2bbfcf/carrier
```

Ý nghĩa:

- `1`: cổng đã có link, dây/cổng đang kết nối.
- `0`: chưa có link, dây/cổng chưa kết nối hoặc thiết bị chưa lên.

## 7. Kiểm Tra Mạng Tới Thiết Bị

Ping thiết bị:

```bash
ping -c 3 192.168.244.1
```

Nếu mạng OK, kết quả sẽ có:

```text
0% packet loss
```

Kiểm tra port ADB `4321`:

```bash
timeout 2 bash -c '</dev/tcp/192.168.244.1/4321'
echo $?
```

Ý nghĩa:

- `0`: port đang mở.
- Khác `0`: port chưa mở hoặc bị từ chối.

## 8. Kết Nối ADB Thủ Công

Kết nối:

```bash
adb connect 192.168.244.1:4321
```

Kiểm tra:

```bash
adb devices
```

Kết quả mong muốn:

```text
192.168.244.1:4321    device
```

Vào shell:

```bash
adb shell
```

Nếu cần reset ADB server:

```bash
adb disconnect 192.168.244.1:4321
adb kill-server
adb start-server
adb connect 192.168.244.1:4321
adb devices
```

## 9. Dùng Script `adb.sh`

Script chính nằm ở:

```bash
~/BLTN_ADB/adb.sh
```

Cách chạy:

```bash
cd ~/BLTN_ADB
./adb.sh
```

Script này sẽ tự làm các việc sau:

- Đọc cấu hình từ `~/.config/adapter-status/config.json`.
- Tự lấy tên cổng, IP adapter, IP thiết bị và ADB port.
- Tự tìm ADB key trong `~/.android`.
- Tự export `ADB_VENDOR_KEYS`.
- Tự gán IP cho cổng adapter.
- Tự kết nối ADB tới `192.168.244.1:4321`.
- Nếu ADB đang `unauthorized`, `offline`, hoặc chưa connect, script sẽ restart ADB server.
- Cuối cùng mở `adb shell`.

Khi chạy thành công sẽ thấy:

```text
Interface: enx1c860b2bbfcf
Host IP:   192.168.244.10/24
ADB:       192.168.244.1:4321
List of devices attached
192.168.244.1:4321    device
```

## 10. App Adapter Status

App dùng để quan sát trực tiếp trạng thái cổng trên giao diện UI.

Mở app bằng terminal:

```bash
/home/bltn/BLTN_ADB/adapter-status-ui
```

Hoặc double-click icon ngoài Desktop:

```bash
~/Desktop/Adapter Status.desktop
```

Nếu Desktop hỏi quyền lần đầu, chọn:

```text
Trust and Launch
```

hoặc:

```text
Allow Launching
```

Khi app khởi động, app chỉ dọn terminal cũ do chính app đã mở ở lần chạy trước, không tự reset ADB/IP. Danh sách PID được lưu tại:

```bash
~/.cache/adapter-status/child-processes.json
```

Cơ chế này dùng PID, process group và start time trong `/proc` để tránh kill nhầm PID đã bị hệ điều hành tái sử dụng.
Nếu bấm **Mở Terminal**, app truyền biến `ADAPTER_STATUS_TRACK=1`; lúc đó `adb.sh` cũng tự ghi PID của terminal session để lần mở app sau có thể dọn `adb shell` cũ nếu nó còn treo.

## 11. Các Trường Trên App

- `Tên cổng`: tên adapter đang theo dõi, hiện là `enx1c860b2bbfcf`.
- `IP adapter`: IP gán cho máy tính, hiện là `192.168.244.10/24`.
- `IP thiết bị`: IP thiết bị, hiện là `192.168.244.1`.
- `ADB port`: port ADB, hiện là `4321`.
- `Trạng thái kết nối cổng`: cho biết cổng đã có link vật lý hay chưa.
- `IP hiện tại`: IP thực tế đang có trên adapter.
- `Ping thiết bị`: cho biết máy có thấy thiết bị qua mạng hay không.
- `ADB port`: app không probe port trực tiếp để tránh làm nhiễu adbd trên BLTN.
- `ADB status`: cho biết ADB đã sẵn sàng hay chưa.

## 12. Ý Nghĩa Trạng Thái Lớn Trên App

`CHƯA THẤY ADAPTER`

Máy chưa nhận USB Network Adapter. Kiểm tra dây, cổng USB hoặc thiết bị.

`CHƯA CẮM / CHƯA CÓ LINK`

Adapter có tồn tại nhưng chưa có link vật lý. Thường là dây/cổng chưa cắm đúng hoặc thiết bị đầu bên kia chưa lên.

`CÓ LINK, CHƯA CÓ IP 192.168.244.10 - BẤM ADB CONNECT`

Cổng đã có link nhưng chưa có IP đúng. Bấm **ADB Connect** để app tự gán IP và canh ADB.

`ĐANG CHỜ BLTN LÊN MẠNG - BẤM ADB CONNECT ĐỂ CANH`

Adapter đã có IP nhưng chưa ping được `192.168.244.1`. Có thể bấm **ADB Connect** trước rồi reset BLTN trong lúc app đang canh.

`ADB CHƯA CONNECT - BẤM ADB CONNECT`

Ping đã OK nhưng ADB chưa kết nối. Bấm **ADB Connect**.

`CONNECTED - ADB READY`

Kết nối hoàn chỉnh. Có thể chạy:

```bash
cd ~/BLTN_ADB
./adb.sh
```

hoặc:

```bash
adb shell
```

## 13. Các Nút Trên App

`Cấu hình IP`

Gán IP adapter cho cổng đang chọn, bật cổng lên và lưu thông số hiện tại vào `~/.config/adapter-status/config.json`.

`ADB Connect`

Gán lại IP adapter, xoá transport/process ADB cũ đang treo, rồi canh bắt ADB trong 60 giây:

```bash
adb connect 192.168.244.1:4321
```

Nếu cửa sổ ADB của BLTN quá ngắn, bấm **ADB Connect** trước, thấy app báo đang canh, rồi reset BLTN trong lúc app đang canh. Reset trước rồi mới bấm có thể đã lỡ cửa sổ ADB.

`Mở Terminal`

Chỉ sáng khi app thấy ADB đã lên `device`. Khi bấm, app mở terminal tại `~/BLTN_ADB` và chạy `./adb.sh`.

`Help`

Mở cửa sổ hướng dẫn chi tiết ngay trong app.

## 14. Tab File Explorer

Tab **File Explorer** dùng để xem cây file/thư mục của ECU qua ADB theo cách trực quan hơn terminal.

Điều kiện:

- App phải thấy `ADB status: device`.
- Nếu chưa thấy `device`, bấm **ADB Connect** trước.

Cách dùng:

- Nhập đường dẫn như `/`, `/etc`, `/data`, `/firmware` rồi bấm **Refresh** hoặc Enter.
- Double-click thư mục để mở.
- Bấm **Up** để quay lên thư mục cha.
- Chọn file thường rồi bấm **Xem text** để preview tối đa 32768 bytes đầu tiên.
- Chọn file thường rồi bấm **Pull file về máy** để tải về `~/BLTN_ADB/ecu-files`.
- Bấm **Copy path** để copy đường dẫn file/thư mục đang chọn.

Giới hạn an toàn:

- Tab này chỉ đọc trên ECU.
- Không có thao tác xóa, sửa, push, chmod hoặc remount.
- File binary chỉ nên pull về máy, không nên preview trực tiếp.

## 15. Quy Trình Khi Rút/Cắm Lại Cổng

1. Mở app **Adapter Status**.
2. Rút hoặc cắm lại cổng USB Network Adapter.
3. Quan sát trạng thái lớn ở giữa app.
4. Nếu thấy có link nhưng chưa IP/chưa ADB, bấm **ADB Connect**.
5. Nếu cửa sổ ADB quá ngắn, bấm **ADB Connect** trước rồi reset BLTN khi app đang canh.
6. Khi thấy `CONNECTED - ADB READY`, bấm **Mở Terminal** hoặc dùng ADB bình thường.

## 16. Nếu Tên Cổng Bị Đổi

Xem danh sách cổng:

```bash
ip -br link
```

Tìm cổng dạng `enx...`, ví dụ:

```text
enx1c860b2bbfcf
```

Nếu tên khác với app:

1. Mở app **Adapter Status**.
2. Sửa ô `Tên cổng`.
3. Bấm **Cấu hình IP** để lưu và gán lại IP.
4. Bấm **ADB Connect** nếu mạng đã OK.

`adb.sh` cũng có cơ chế tự dò cổng `enx...` nếu cổng trong config không tồn tại.

## 17. Xử Lý Lỗi Thường Gặp

### Lỗi `No such device`

Nguyên nhân:

- Tên cổng sai.
- Adapter chưa được máy nhận.
- Vừa rút/cắm lại nên tên cổng thay đổi.

Kiểm tra thủ công khi cần:

```bash
ip -br link
```

Cách xử lý:

- Mở app.
- Sửa `Tên cổng` nếu cần.
- Bấm **Cấu hình IP** để lưu và gán lại IP.

### Lỗi `unauthorized`

Ví dụ:

```text
adb: device unauthorized.
This adb server's $ADB_VENDOR_KEYS is not set
```

Nguyên nhân:

- ADB server chạy khi chưa có `ADB_VENDOR_KEYS`.
- Thiết bị chưa chấp nhận key.

Cách xử lý:

```bash
source ~/.bashrc
adb disconnect 192.168.244.1:4321
adb kill-server
adb start-server
adb connect 192.168.244.1:4321
adb devices
```

Nếu thiết bị có màn hình xác nhận ADB, chọn **Allow**.

Nếu dùng script:

```bash
cd ~/BLTN_ADB
./adb.sh
```

Script sẽ tự set `ADB_VENDOR_KEYS` và restart ADB server khi cần.

### Lỗi `offline`

Nguyên nhân:

- ADB session cũ bị treo.
- Vừa rút/cắm lại cổng.

Cách xử lý:

```bash
adb disconnect 192.168.244.1:4321
adb kill-server
adb start-server
adb connect 192.168.244.1:4321
adb devices
```

Hoặc dùng app:

1. Bấm **ADB Connect** để app dọn transport cũ và canh ADB.
2. Nếu cửa sổ ADB quá ngắn, reset BLTN trong lúc app đang canh.

### Lỗi `Connection refused`

Nguyên nhân:

- Ping tới thiết bị OK nhưng service ADB TCP trên thiết bị chưa mở port `4321`.

Kiểm tra:

```bash
ping -c 3 192.168.244.1
timeout 2 bash -c '</dev/tcp/192.168.244.1/4321'
echo $?
```

Cách xử lý:

- Bấm **ADB Connect** trước.
- Reset BLTN trong lúc app đang canh nếu port chỉ mở trong thời gian ngắn.
- Nếu thiết bị có quy trình bật ADB TCP riêng, bật lại ADB TCP port `4321`.

### Ping Fail

Nguyên nhân:

- Chưa cắm link.
- Chưa có IP adapter.
- Thiết bị chưa lên mạng.

Cách xử lý:

```bash
ip -br addr show enx1c860b2bbfcf
ping -c 3 192.168.244.1
```

Hoặc dùng app:

1. Kiểm tra trạng thái lớn.
2. Bấm **Cấu hình IP**.
3. Kiểm tra lại ping trên app.

## 18. Lệnh Kiểm Tra Nhanh

Kiểm tra cổng:

```bash
ip -br link
```

Kiểm tra IP:

```bash
ip -br addr show enx1c860b2bbfcf
```

Kiểm tra link vật lý:

```bash
cat /sys/class/net/enx1c860b2bbfcf/carrier
```

Kiểm tra ping:

```bash
ping -c 3 192.168.244.1
```

Kiểm tra ADB:

```bash
adb devices
```

Vào shell:

```bash
adb shell
```

Chạy script chuẩn:

```bash
cd ~/BLTN_ADB
./adb.sh
```

## 19. Quy Trình Chuẩn Hằng Ngày

1. Cắm USB Network Adapter vào thiết bị.
2. Mở app **Adapter Status**.
3. Đợi app cập nhật trạng thái.
4. Nếu cần, bấm **Cấu hình IP**.
5. Nếu cần, bấm **ADB Connect**.
6. Khi app hiện `CONNECTED - ADB READY`, bấm **Mở Terminal** hoặc chạy:

```bash
cd ~/BLTN_ADB
./adb.sh
```

## 20. Ghi Chú Quan Trọng

- Luôn kiểm tra app trước khi chạy `adb shell`.
- Nếu app chưa báo `CONNECTED - ADB READY`, nên xử lý trạng thái trên app trước.
- Nếu terminal cũ vẫn báo lỗi key, đóng terminal đó và mở terminal mới.
- Nếu vừa rút/cắm lại cổng, nên bấm **Cấu hình IP** trước rồi mới bấm **ADB Connect**.
- Không cần nhớ nhiều lệnh: app đã có nút **Help** để xem hướng dẫn này ngay trên giao diện.
