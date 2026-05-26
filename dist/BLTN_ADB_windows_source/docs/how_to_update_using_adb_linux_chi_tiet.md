# Hướng dẫn update CPU bằng ADB trên Linux / VMware

Tài liệu này được chuyển và sắp xếp lại từ file PowerPoint **“How to update using adb - Linux.pptx”**.

Mục tiêu: dùng ADB để kết nối tới thiết bị qua địa chỉ IP `192.168.244.1:4321`, đẩy file update `cpu_update.bin` vào thiết bị, sau đó chạy lệnh update CPU.

---

## 1. Chuẩn bị trước khi update

### 1.1. File cần có

Cần chuẩn bị các file sau:

| File | Mục đích | Ghi chú |
|---|---|---|
| `dd.zip` | File/phần dữ liệu dùng cho môi trường Linux | Copy vào thư mục **Home** của Linux |
| `cpu_update.bin` | File firmware/update CPU | Phải đặt đúng tên là `cpu_update.bin` |
| `adb.sh` | Script chạy ADB | Cần chỉnh đúng tên cổng mạng nếu tài liệu/yêu cầu có dùng |
| `adbscript_linux.sh` | Script cấp key/chạy hỗ trợ ADB | Có thể cần cấp quyền trước khi chạy |

> Lưu ý quan trọng: file update CPU phải đúng tên **`cpu_update.bin`**. Nếu sai tên, các lệnh `adb push` hoặc `update cpu` có thể không nhận đúng file.

---

## 2. Cấu hình IP cho máy tính

Trên máy tính, đổi IP của card mạng đang kết nối với thiết bị về cấu hình sau:

```text
IP address: 192.168.244.10
Subnet mask: 255.255.255.0
```

Thiết bị cần kết nối ADB ở địa chỉ:

```text
192.168.244.1:4321
```

### Kiểm tra nhanh

Sau khi đổi IP, nên kiểm tra:

```bash
ping 192.168.244.1
```

Nếu ping không thông, cần kiểm tra lại:

- Dây mạng/cổng mạng đã cắm đúng chưa.
- Card mạng trên máy tính đã đặt đúng IP chưa.
- Máy ảo VMware đã bridge/nhận đúng card mạng chưa.
- Thiết bị đã bật nguồn và đang ở trạng thái cho phép kết nối chưa.

---

## 3. Mở Linux trong VMware

### Bước 1: Mở VMware

Mở phần mềm **VMware Workstation** hoặc VMware đang dùng.

### Bước 2: Bật máy ảo Linux/Ubuntu

Chọn máy ảo Linux/Ubuntu rồi bấm **Power on / Start** để chạy máy ảo.

> Trong slide gốc, phần Step 2 không ghi rõ nội dung chữ, nhưng hình minh họa cho thấy thao tác là mở/chạy máy ảo Linux trong VMware.

---

## 4. Copy file vào thư mục Home của Linux

Sau khi vào Linux, copy các file cần thiết vào thư mục **Home**.

Cần đảm bảo trong thư mục Home có ít nhất:

```text
dd.zip
cpu_update.bin
adb.sh
adbscript_linux.sh
```

Có thể kiểm tra bằng lệnh:

```bash
cd ~
ls
```

---

## 5. Kiểm tra tên cổng mạng trong Linux

Mở Terminal và chạy:

```bash
cd ~
ifconfig
```

Nếu máy không có `ifconfig`, có thể dùng:

```bash
ip addr
```

Xem tên cổng mạng đang kết nối, ví dụ thường gặp:

```text
eth0
enp0s3
ens33
ens160
```

Sau đó thay đúng tên cổng mạng này trong các file cấu hình/script nếu có yêu cầu, cụ thể theo tài liệu gốc là:

```text
interfaces
adb.sh
```

> Chú ý: phải chắc chắn cổng mạng đã **connect** trong VMware. Nếu cổng mạng chưa connect, Linux sẽ không giao tiếp được với thiết bị.

---

## 6. Cấp quyền chạy script

Nếu script chưa chạy được, cấp quyền cho file script.

Theo tài liệu gốc có nhắc:

```bash
chmod 888 adbscript_linux.sh
```

Tuy nhiên, cách thường dùng hơn là:

```bash
chmod +x adbscript_linux.sh
chmod +x adb.sh
```

Nếu cần chạy script cấp key:

```bash
./adbscript_linux.sh
```

Nếu báo lỗi quyền truy cập, kiểm tra lại:

```bash
ls -l adbscript_linux.sh adb.sh
```

---

## 7. Kết nối ADB tới thiết bị

Từ thư mục Home của Linux, chạy:

```bash
cd ~
./adb.sh
adb connect 192.168.244.1:4321
```

Nếu kết nối thành công, thường sẽ thấy thông báo kiểu:

```text
connected to 192.168.244.1:4321
```

Kiểm tra danh sách thiết bị:

```bash
adb devices
```

Kết quả mong muốn là có thiết bị ở dạng:

```text
192.168.244.1:4321    device
```

Nếu không kết nối được, thử:

```bash
adb kill-server
adb start-server
adb connect 192.168.244.1:4321
```

---

## 8. Đẩy file update vào thiết bị

Theo phần Linux trong tài liệu gốc, đẩy file vào thư mục `/tmp`:

```bash
adb push cpu_update.bin /tmp
```

Chờ quá trình push hoàn tất. Không rút nguồn, không ngắt mạng trong lúc đang push file.

Sau khi push xong, vào shell của thiết bị:

```bash
adb shell
```

Đi tới thư mục `/tmp`:

```bash
cd /tmp
ls
```

Kiểm tra có file:

```text
cpu_update.bin
```

Sau đó chạy:

```bash
sync
```

Lệnh `sync` giúp đảm bảo dữ liệu đã được ghi xuống bộ nhớ trước khi update.

---

## 9. Chạy lệnh update CPU

Trong `adb shell`, chạy:

```bash
cmdtool
```

Sau đó chạy lệnh update:

```bash
update cpu
```

Quá trình update sẽ bắt đầu.

> Không tắt nguồn, không reset thiết bị, không rút dây mạng trong lúc update.

---

## 10. Theo dõi quá trình update

Vào **Engineer mode** để xem quá trình update có đang chạy hay không.

Tài liệu gốc có ghi chú: trước đó thiết bị đang không ở chế độ Engineer mode, nên cần vào Engineer mode để kiểm tra trạng thái update.

Nếu có terminal theo dõi log, có thể dùng các lệnh sau:

```bash
journalctl -a | grep MCU
journalctl -a | grep SW
```

Hoặc xem log chạy liên tục:

```bash
journalctl -f
```

Trong slide gốc có dòng:

```bash
journalctl -f grep SOME
```

Dòng này có thể là ghi chú chưa chuẩn cú pháp. Nếu muốn lọc log khi chạy liên tục, có thể dùng dạng:

```bash
journalctl -f | grep SOME
```

---

## 11. Ghi chú xử lý lỗi thường gặp

### 11.1. Không connect được ADB

Thử lần lượt:

```bash
adb kill-server
adb start-server
adb connect 192.168.244.1:4321
adb devices
```

Kiểm tra lại IP máy tính:

```text
192.168.244.10 / 255.255.255.0
```

Kiểm tra thiết bị:

```bash
ping 192.168.244.1
```

Nếu vẫn không được, tài liệu gốc có ghi chú:

```text
Nên reset B+ nếu không được
```

Tức là có thể cần reset nguồn B+ hoặc reset nguồn thiết bị theo quy trình kỹ thuật của hệ thống.

---

### 11.2. Script không chạy được

Cấp quyền lại:

```bash
chmod +x adb.sh
chmod +x adbscript_linux.sh
```

Chạy đúng đường dẫn:

```bash
cd ~
./adb.sh
```

Hoặc:

```bash
./adbscript_linux.sh
```

---

### 11.3. Không thấy file sau khi push

Vào shell:

```bash
adb shell
cd /tmp
ls
```

Nếu không có `cpu_update.bin`, push lại:

```bash
exit
adb push cpu_update.bin /tmp
```

Sau đó kiểm tra lại:

```bash
adb shell
cd /tmp
ls
sync
```

---

## 12. Luồng lệnh Linux tóm tắt

Có thể dùng chuỗi lệnh sau để thao tác nhanh:

```bash
cd ~
chmod +x adb.sh adbscript_linux.sh
./adb.sh
adb kill-server
adb start-server
adb connect 192.168.244.1:4321
adb devices
adb push cpu_update.bin /tmp
adb shell
cd /tmp
ls
sync
cmdtool
update cpu
```

---

## 13. Phần tham khảo: lệnh ADB trong Windows/CMD

Một slide trong tài liệu có phần hướng dẫn mở `cmd` trong thư mục ADB và connect ADB.

Mở Command Prompt trong thư mục ADB, sau đó chạy:

```cmd
adb connect 192.168.244.1:4321
```

Với phiên bản mới:

```cmd
adb push cpu_update.bin /home/adb/
```

Với phiên bản cũ:

```cmd
adb push cpu_update.bin /mnt/data/
```

Sau đó:

```cmd
adb shell
su
```

Nhập password:

```text
dudtkdtjfrP2!@
```

Tiếp tục:

```cmd
cmdtool
update cpu
```

Để quay lại và xem tiến trình update bằng log, bấm:

```text
Ctrl + C
```

Sau đó có thể dùng:

```bash
journalctl -a | grep MCU
journalctl -a | grep SW
journalctl -f
```

---

## 14. Checklist trước khi bấm update

Trước khi chạy `update cpu`, kiểm tra đủ các mục sau:

- [ ] Máy tính đã đặt IP `192.168.244.10`.
- [ ] Subnet mask là `255.255.255.0`.
- [ ] Ping được `192.168.244.1`.
- [ ] ADB connect được tới `192.168.244.1:4321`.
- [ ] File update đúng tên `cpu_update.bin`.
- [ ] File `cpu_update.bin` đã được push vào thiết bị.
- [ ] Đã kiểm tra file bằng `ls` trong thư mục đích.
- [ ] Đã chạy `sync`.
- [ ] Nguồn thiết bị ổn định, không bị mất nguồn trong quá trình update.
- [ ] Có thể vào Engineer mode hoặc xem log để theo dõi tiến trình.

---

## 15. Checklist sau khi update

Sau khi chạy update:

- [ ] Theo dõi Engineer mode xem tiến trình update có chạy không.
- [ ] Theo dõi log nếu cần.
- [ ] Không tắt nguồn khi update chưa hoàn tất.
- [ ] Sau khi update xong, kiểm tra lại phiên bản CPU/MCU/SW theo quy trình của thiết bị.
- [ ] Nếu update lỗi, không tự ý chạy lại nhiều lần khi chưa xác định nguyên nhân.

---

## 16. Ghi chú an toàn

- Không rút nguồn khi đang `adb push` hoặc `update cpu`.
- Không đổi tên file `cpu_update.bin`.
- Không dùng nhầm file update của phiên bản khác.
- Nếu ADB chập chờn, xử lý kết nối trước rồi mới update.
- Nếu thiết bị có yêu cầu reset B+, chỉ thực hiện theo đúng quy trình kỹ thuật của thiết bị.


Step 1 :Copy file dd.zip ra mục Home của linux

Step 2 : Vào Terminal => cd ..(để về đường dẫn Home) =>  Ifconfig => Xem tên cổng rồi thay trong file interfaces và file adb.sh. Chú ý phải  connect cổng 
Step 3 : Copy file Bin vào mục Home, phải đúng tên : cpu_update.bin
Step 4 : Chạy lệnh : 
./adb.sh
adb connect 192.168.244.1:4321
Step 5 :
adb push cpu_update.bin /tmp
Step 6 : Chờ khi push. Khi xong chạy lệnh : 
adb shell
cd /tmp
ls
sync
Step 7 : cmdtool
Step 8 : update cpu
Step 9 : Vào Engineer mode xem quá trình Update có đang chạy không (trước đó đang khôn ở chế độ enginner mode)
Cấp key : 
insert ./adbscript_linux.sh or chmod 888 adbscript_linux.sh (nhớ đúng đường dẫn)
Chú ý nên Reset B+ nếu không được
Cần adb Kill-server
Step 4 : Open "cmd" in abd folder and connect adb 1. Type command: adb connect 192.168.244.1:43212. Type command(with new version): : adb push cpu_update.bin /home/adb/    Type command(with old version): adb push cpu_update.bin /mnt/data/3. Type command: adb shell4. Type command: su5. Type command: Enter password: "dudtkdtjfrP2!@“6. Type command: cmdtool7. Type command: update cpu8. Press "ctrl + c" to back cd of adb journalctl -f (to view progress of update)9. Type command: journalctl -a |grep MCU journalctl -a |grep SW journalctl -f grep SOME