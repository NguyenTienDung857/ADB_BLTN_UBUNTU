1. Quản lý File và Quyền thực thi
Kiểm tra các script và cấp quyền để chạy các file công cụ:
    • chmod +x adb.sh: Cấp quyền thực thi cho script ADB.
    • chmod 777 adbscript_linux.sh: Cấp quyền toàn diện cho script cấu hình.
    • cd /mnt/hgfs: Truy cập vào thư mục chia sẻ (thường là giữa máy ảo VMware và máy chủ).
2. Cấu hình Mạng (Network Configuration)
Thiết lập IP tĩnh cho interface mạng USB (enx1c86...):
    • ifconfig / ip a: Kiểm tra danh sách các card mạng và địa chỉ IP.
    • sudo ip link set ens33 down: Tắt card mạng chính (có thể để tránh xung đột định tuyến).
    • sudo ifconfig enx1c860b2bbfcf 192.168.244.10 netmask 255.255.255.0 up: Gán IP tĩnh 192.168.244.10 cho adapter USB.
    • sudo dhclient enx1c860b2bbfcf: Cố gắng xin cấp phát IP tự động từ thiết bị.
3. Kiểm tra kết nối vật lý và mạng
    • lsusb: Kiểm tra xem máy tính đã nhận diện được thiết bị/adapter USB hay chưa.
    • ping 192.168.244.1: Kiểm tra thông suốt mạng đến thiết bị đích (gateway/device).
    • arp -n 192.168.244.1: Kiểm tra bảng ARP để xác nhận địa chỉ MAC của thiết bị đích.
    • sudo tcpdump -i ... arp or icmp: Bắt gói tin để chẩn đoán tại sao ping hoặc kết nối không thành công.
4. Thao tác với ADB (Android Debug Bridge)
Bạn thực hiện các lệnh để kết nối với thiết bị qua cổng 4321:
    • adb tcpip 4321: Chuyển ADB sang chế độ lắng nghe qua TCP/IP.
    • adb connect 192.168.244.1:4321: Thực hiện kết nối đến IP của thiết bị.
    • adb devices: Kiểm tra danh sách các thiết bị đã kết nối thành công.
    • adb kill-server / adb start-server: Khởi động lại trình điều khiển ADB khi gặp lỗi.
    • ./adb.sh: Chạy script tự động hóa việc kết nối (lệnh này được bạn lặp lại nhiều lần nhất để thử lại kết nối).
5. Chẩn đoán nâng cao
    • nmap -p 4321 192.168.244.1: Quét xem cổng 4321 trên thiết bị có đang mở (Open) hay không.
    • ss -tuln | grep 4321: Kiểm tra các cổng đang lắng nghe trên máy cục bộ.
