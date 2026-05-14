# Báo cáo quét sâu built-in cam qua ADB

Ngày ghi báo cáo: 2026-05-14  
Thư mục lưu: `/home/bltn/BLTN_ADB`  
Thiết bị ADB: `192.168.244.1:4321`  
Phạm vi: quét chức năng, dịch vụ, config, sysfs, GPIO, camera layout, profile VRS và các lệnh có khả năng bật/tắt trên built-in cam.

## 1. Nguyên tắc khi quét

Trong quá trình quét chỉ thực hiện thao tác đọc trạng thái là chính. Không chạy các lệnh có khả năng update firmware, reset cấu hình, clear DTC, ghi GPIO, ghi sysfs hay dừng service camera chính.

Có dọn một số tiến trình `cmdtool` bị kẹt và socket tạm `/dev/shm/.ee` do quá trình gọi `cmdtool` để đọc trạng thái. Việc này nhằm giải phóng lệnh bị treo, không phải thay đổi cấu hình VRS.

Nhóm lệnh nguy hiểm đã phát hiện nhưng chưa chạy:

- `cmdtool update qfil`
- `cmdtool update cpu`
- `cmdtool state dtc clear`
- `cmdtool state wifiPW reset`
- `cmdtool gpio set ...`
- `systemctl stop/disable vrs`
- `systemctl stop/disable preview`
- Ghi vào GPIO, watchdog, power, reset, backlight, camera sysfs

## 2. Thông tin hệ thống thiết bị

ADB:

```text
192.168.244.1:4321 device
```

Quyền shell:

```text
uid=0(root) gid=0(root) groups=0(root),3003(inet)
```

Kernel và OS:

```text
Linux sa6155 5.4.86-perf #1 SMP PREEMPT Mon Jul 7 05:18:54 UTC 2025 aarch64
PRETTY_NAME="auto 202507071411"
VERSION_ID=202507071411
```

Version hệ thống:

```text
/etc/version:
202507071411
SDK=LV20-6p3-r9
ROOTFS=0.67
```

Version VRS/app:

```text
SW Ver: 01.12.00.00
/mnt/data/share/hu/ver/sw_ver.txt: 01.12.00.00
/ydvrs/bin/ver/sw_ver.txt: 01.12.00.00
```

Ghi chú: `getprop` gần như không trả dữ liệu, thiết bị này là Linux automotive chạy ADB, không giống Android chuẩn.

## 3. Tiến trình chính đang chạy

Các tiến trình quan trọng phát hiện qua `ps`:

| Tiến trình | Đường dẫn/lệnh | Vai trò |
| --- | --- | --- |
| `weston` | `/usr/bin/weston --tty=2` | Wayland compositor/display |
| `preview.sh` | `/bin/sh /ydvrs/bin/preview.sh` | script preview |
| `vrs_preview.out` | `/ydvrs/bin/vrs_preview.out` | preview camera/LVDS |
| `yappStarter.sh` | `/bin/sh /ydvrs/bin/yappStarter.sh` | script khởi động VRS main |
| `vrs_main.out` | `/ydvrs/bin/vrs_main.out` | ứng dụng DVR/VRS chính |
| `adbd` | `/sbin/adbd` | ADB daemon |
| `mwd` | `/usr/bin/mwd` | IP Middleware |
| `ais_server` | `/usr/bin/ais_server` | camera/ISP service |
| `diag-router` | `/usr/bin/diag-router` | diagnostic router |
| `dlt-daemon` | `/usr/bin/dlt-daemon` | DLT logging |
| `dlt-system` | `/usr/bin/dlt-system` | DLT system logging |
| `thermal-engine` | `/usr/bin/thermal-engine` | quản lý nhiệt |
| `xinetd` | `/usr/sbin/xinetd -dontfork` | dịch vụ mạng nội bộ |

`vrs_main.out` có lúc dùng CPU cao. Đây nhiều khả năng là trạng thái hoạt động bình thường của app camera/rendering, không kết luận là lỗi.

## 4. Script khởi động VRS và preview

### `/ydvrs/bin/yappStarter.sh`

Script này đặt biến môi trường và chạy app chính:

```sh
VSOMEIP_CONFIGURATION=/ydvrs/bin/vsomeip_bltncam.json
VSOMEIP_APPLICATION_NAME=bltncam
XDG_RUNTIME_DIR=/run/user/0
SDL_VIDEODRIVER=wayland
SDL_RENDER_DRIVER=opengles2
pulseaudio --start &
/ydvrs/bin/vrs_main.out
```

Ý nghĩa:

- `VSOMEIP_CONFIGURATION`: dùng file SOME/IP config riêng của built-in cam.
- `VSOMEIP_APPLICATION_NAME=bltncam`: tên app SOME/IP.
- `SDL_VIDEODRIVER=wayland`: render qua Wayland.
- `SDL_RENDER_DRIVER=opengles2`: render qua OpenGLES2.
- `pulseaudio --start`: bật audio server trước khi chạy app.

### `/ydvrs/bin/preview.sh`

Script preview cũng dùng Wayland/OpenGLES và chạy:

```sh
/ydvrs/bin/vrs_preview.out
```

Trong script có comment liên quan debug video:

```sh
setprop vendor.vidc.debug.turbo 1
```

Dòng này đang là comment, không chạy tự động.

## 5. `cmdtool`: bề mặt điều khiển chính

`cmdtool` là công cụ CLI quan trọng nhất tìm thấy. Nó có các nhóm lệnh có thể bật/tắt hoặc đổi trạng thái runtime.

### 5.1 Recorder/VRS

Các lệnh:

```text
cmdtool rec mode gui|drv|bprk|nprk
cmdtool rec aging mode
cmdtool rec set owd on|off
cmdtool rec set dev on|off
cmdtool rec set owp on|off
cmdtool rec set pev on|off
cmdtool rec set all on|off
cmdtool rec test once|continue|stop
```

Ý nghĩa theo chuỗi và trạng thái VRS:

| Lệnh/mục | Ý nghĩa |
| --- | --- |
| `owd` | Ordinary While Driving, ghi thường khi xe chạy |
| `dev` | Driving Event Video, ghi sự kiện khi xe chạy |
| `owp` | Ordinary While Parked, ghi thường khi đỗ |
| `pev` | Parking Event Video, ghi sự kiện khi đỗ |
| `all` | bật/tắt toàn bộ nhóm ghi trên |
| `gui` | mode điều khiển từ GUI |
| `drv` | driving mode |
| `bprk` | before parking mode |
| `nprk` | normal parking mode |
| `test once` | test ghi một lần |
| `test continue` | test ghi liên tục |
| `test stop` | dừng test |

Chuỗi trong binary còn cho thấy có các bài stress/test nội bộ:

- Drive crash event stress test
- Park-to-drive mode change stress test
- Overload test
- Crash test
- Parking time test

Nhóm test/stress này không nên chạy tùy tiện vì có thể tạo file ghi, event hoặc thay đổi trạng thái recorder.

### 5.2 Camera view, EOL, AS, calibration

Các lệnh:

```text
cmdtool cameraview set fr
cmdtool cameraview set ar
cmdtool cameraview set fr_ver -5~5
cmdtool cameraview set re_ver -5~5
cmdtool cameraview set eol
cmdtool cameraview set eol_stop
cmdtool cameraview set eol_status
cmdtool cameraview set as
cmdtool cameraview set as_stop
cmdtool cameraview set as_status
cmdtool cameraview set roll_up
cmdtool cameraview set roll_down
cmdtool cameraview set pitch_up
cmdtool cameraview set pitch_down
cmdtool cameraview set yaw_up
cmdtool cameraview set yaw_down
cmdtool cameraview set reset
cmdtool cameraview set data values(lhd roll pitch yaw rhd roll pitch yaw)
cmdtool cameraview set factory_info values(factory,line)
cmdtool cameraview set config on|off
cmdtool cameraview set filesrc on|off
cmdtool cameraview set save_raw on|off
```

Ý nghĩa:

| Mục | Chức năng |
| --- | --- |
| `fr` | front camera/view |
| `ar` | around/rear view theo ngữ cảnh binary |
| `fr_ver` | chỉnh vị trí dọc camera trước |
| `re_ver` | chỉnh vị trí dọc camera sau |
| `eol` | bắt đầu EOL calibration |
| `eol_stop` | dừng EOL calibration |
| `eol_status` | đọc trạng thái EOL |
| `as` | bắt đầu AS calibration |
| `as_stop` | dừng AS calibration |
| `as_status` | đọc trạng thái AS |
| `roll/pitch/yaw` | chỉnh góc calibration |
| `reset` | reset thông số calibration |
| `config on|off` | bật/tắt config camera view |
| `filesrc on|off` | bật/tắt dùng file source thay camera thật |
| `save_raw on|off` | bật/tắt lưu raw frame |

Kết quả trạng thái từng thấy trong journal:

```text
CAMERAVIEW_CMD_ID_CALIB_STATUS_RES 4
Permanent] SaveCamInfoCaliStatusValue : 4
```

### 5.3 Log/debug runtime

Các lệnh:

```text
cmdtool log on
cmdtool log off
cmdtool log grep [param]
cmdtool log level 1~6
cmdtool log gsensor on|off
cmdtool log dlt download
cmdtool log mcu on|off
cmdtool log journal on|off
```

Level log:

| Level | Ý nghĩa |
| --- | --- |
| 1 | Error |
| 2 | Warning |
| 3 | Info |
| 4 | Debug |
| 5 | Fault |
| 6 | Trace |

Nhóm này tương đối an toàn nếu chỉ bật/tắt log hoặc đổi level, nhưng bật trace/debug lâu có thể làm đầy log hoặc ảnh hưởng hiệu năng.

### 5.4 MCU/LVDS/power mode

Các lệnh:

```text
cmdtool mcu lvds fr|ar|eng
cmdtool mcu powermode factory|dealer|customer
```

Ý nghĩa:

- `lvds fr|ar|eng`: đổi mode LVDS/front/around hoặc engineering mode.
- `powermode factory|dealer|customer`: đổi power mode theo chế độ nhà máy, đại lý hoặc khách hàng.

Nhóm này có thể ảnh hưởng hiển thị, trạng thái nguồn hoặc cách MCU điều khiển thiết bị. Không nên chạy nếu chưa có mục tiêu rõ.

### 5.5 State/status

Các lệnh:

```text
cmdtool state show
cmdtool state gsensor info
cmdtool state gsensor get threshold
cmdtool state mcu info
cmdtool state permanent info
cmdtool state profile info
cmdtool state cfg info
cmdtool state dtc clear
cmdtool state wifiPW reset
```

An toàn:

- `state show`
- `state ... info`
- `state gsensor get threshold`
- `state profile info`
- `state cfg info`

Nguy hiểm:

- `state dtc clear`: xóa DTC.
- `state wifiPW reset`: reset mật khẩu Wi-Fi.

### 5.6 GPIO qua `cmdtool`

Các lệnh:

```text
cmdtool gpio get devName pin
cmdtool gpio set devName pin val
```

`gpio get` dùng để đọc trạng thái.  
`gpio set` là rủi ro cao vì có thể tắt camera, reset ISP, đổi trạng thái power, Wi-Fi, SerDes, LED hoặc tín hiệu MCU.

### 5.7 Update

Các lệnh:

```text
cmdtool update qfil
cmdtool update cpu
```

Ghi chú:

- `update cpu` có chuỗi liên quan `/tmp/cpu_update.bin`.
- Đây là nhóm lệnh có khả năng flash/update thiết bị. Không chạy nếu chưa chuẩn bị đúng payload và quy trình.

## 6. Trạng thái profile VRS đọc được

Build/info từ journal VRS:

```text
cmdtool Build Date: [Day:2025-07-10][Time:13:55:33]
HW Ver: 100
SW Ver: 01.12.00.00
Permanent user profile: 2
Permanent state: ok
Parked crash event count: 0
```

### 6.1 Cờ global/profile

Các cờ tìm thấy:

| Cờ | Trạng thái đọc được |
| --- | --- |
| `bDebug` | disabled |
| `b10fpsCam` | enabled |
| `bGsensorLog` | disabled |
| `bFrameLog` | disabled |
| `bGsensorUartProtocol` | disabled |
| `bLedBlinker` | disabled |
| `bPq` | enabled |

### 6.2 Profile 0, 1, 3

Các profile này có trạng thái chính giống nhau:

| Mục | Trạng thái |
| --- | --- |
| `OWD` | on |
| `DEV` | on |
| `OWP` | on |
| `PEV` | on |
| Drive Sensitivity | 3 |
| Park Sensitivity | 3 |
| Timelapse Interval | 1 |
| Audio | 1 |
| Wi-Fi | 0 |
| Park Record Time | 20 |
| OPTBAT Exist | attached |
| OPTBAT Install | enabled |
| TML State | stop |
| PEV Message Able | enabled |
| PEV Message | on |
| PEV Message Notify | on |
| OSD Time | 1 |
| OSD Speed | 1 |
| OSD Gear | 1 |
| OSD Direction | 1 |
| OSD ImpactStrength | 1 |
| OSD GPS | 1 |

### 6.3 Profile 2, profile đang dùng

Profile đang dùng là `2`:

| Mục | Trạng thái |
| --- | --- |
| `OWD` | off |
| `DEV` | off |
| `OWP` | off |
| `PEV` | off |
| Drive Sensitivity | 3 |
| Park Sensitivity | 3 |
| Timelapse Interval | 1 |
| Audio | 1 |
| Wi-Fi | 0 |
| Park Record Time | 20 |
| OPTBAT Exist | detached |
| OPTBAT Install | enabled |
| TML State | stop |
| PEV Message Able | enabled |
| PEV Message | on |
| PEV Message Notify | off |
| OSD Time | 1 |
| OSD Speed | 1 |
| OSD Gear | 1 |
| OSD Direction | 1 |
| OSD ImpactStrength | 1 |
| OSD GPS | 1 |

## 7. G-sensor

Trạng thái từ VRS journal:

```text
Gsensor running
device: /dev/input/by-path/platform-a8c000.i2c-event
descriptor: 0x36
calibration x/y/z: 0.00 / 0.00 / 0.00
sampling count: 1
period: 20
crash delay: disabled
crash delay value: 0
conditional period: 1000
current crash threshold: 1.00
```

File threshold:

```text
/mnt/data/systemfile/fGsensSensitivityConfig
```

Nội dung threshold:

| Mode | High | Mid.High | Mid | Mid.Low | Low |
| --- | ---: | ---: | ---: | ---: | ---: |
| Drive | 0.50 | 0.75 | 1.00 | 1.25 | 1.50 |
| Park | 0.10 | 0.13 | 0.15 | 0.23 | 0.30 |

Chuỗi trong binary cho thấy có thể bật/tắt hoặc cấu hình:

- `recSetSensitivityDrivingEvent`
- `recSetSensitivityParkedEvent`
- `evSenStm On/Off`
- `cmdtool log gsensor on|off`
- `cmdtool state gsensor info`
- `cmdtool state gsensor get threshold`

## 8. MCU và DTC/diagnostic

Trạng thái MCU đọc được:

```text
initField = 13a00
userProfile = 2
bltncamGui = 15
seBplusState = 1
seAccState = 1
seIGNState = 1
seCanState = 1
deCpuPowerMode = 2
Car Type = 3
madeDate = 20220914
swVer = 01.12.00.00
hwVer = A.00
doors/hood/trunk/SBCM = 0x00
```

Chuỗi diagnostic và DID trong `vrs_main.out`:

- DTC Setting ON/OFF
- DTC clear
- RDBI DID Supported ID
- RDBI DID Yura Function
- RDBI DID LVDS State
- RDBI DID BLTN DATA
- RDBI DID ECU LOG DATA
- RDBI DID GSensor Info
- RDBI DID State
- RDBI DID LVDS Info
- RDBI DID ECU ID
- MCU JTAG Control
- `0xF012 O_Drv Event Indicate LED`
- `0xF043 O_Drv Factory Reset`
- `0xF044 O_Drv Record Manual`
- `0xF011 O_Drv Front Indicate LED`
- MCU JTAG unlock/lock request
- MCU update strings

Nhóm này liên quan diagnostic, DTC, JTAG, factory reset và manual record. Nên chỉ đọc thông tin, không clear/reset nếu chưa có quy trình.

## 9. Service systemd có thể bật/tắt

### 9.1 Service đang enabled/quan trọng

| Service | Vai trò | Rủi ro khi stop/disable |
| --- | --- | --- |
| `vrs.service` | app DVR/VRS chính | rất cao, dừng chức năng built-in cam |
| `preview.service` | preview/LVDS camera | cao, mất preview |
| `weston.service` | Wayland/display | cao, mất GUI/display |
| `ais_server.service` | camera/ISP server | cao, ảnh hưởng camera |
| `adbd.service` | ADB daemon | cao nếu đang thao tác từ ADB |
| `mwd.service` | IP Middleware | trung bình/cao, ảnh hưởng SOME/IP/mạng |
| `dlt.service` | DLT daemon | thấp/trung bình, ảnh hưởng log |
| `dlt-system.service` | DLT system log | thấp/trung bình |
| `thermal-engine.service` | quản lý nhiệt | cao, không nên tắt |
| `xinetd.service` | service mạng nội bộ | trung bình |
| `systemd-networkd.service` | network | cao, có thể mất kết nối |
| `iptables.service` | rule firewall/network | trung bình/cao |

### 9.2 Service có file nhưng đang disabled hoặc tùy chọn

| Service | File/lệnh chính | Ý nghĩa |
| --- | --- | --- |
| `wifi.service` | `/ydvrs/bin/hostapd-start`, `/ydvrs/bin/hostapd-stop` | bật/tắt Wi-Fi AP |
| `qcarcam_rvc.service` | `/usr/bin/qcarcam_rvc -seconds=3` | rear view camera demo/test |
| `audiod.service` | `/usr/bin/audiod` | audio daemon |
| `diag-router.service` | `/usr/bin/diag-router` | diagnostic router |
| `debug-shell.service` | systemd debug shell | debug service |
| `lighttpd.service` | `/usr/sbin/lighttpd -D -f /etc/lighttpd/lighttpd.conf` | web server nếu bật |
| `video_early_demo.service` | `/usr/sbin/video_dec_demo.sh` | video demo sớm |
| `tc_port_traffic_control.service` | `/usr/bin/tc_port_traffic_control.sh` | traffic control |
| `ab-updater.service` | updater | update A/B |
| `acdb_loader.service` | audio calibration DB | audio |
| `pdmapper.service` | peripheral domain mapper | Qualcomm subsystem |
| `qrtr_ns.service` | QRTR name service | Qualcomm IPC |
| `qseecomd.service` | secure execution daemon | security/TEE |

### 9.3 Nội dung service chính

`vrs.service`:

```text
ExecStart=/ydvrs/bin/yappStarter.sh
After=ais_server.service local-fs.target adsprpcd.service
User=root
```

`preview.service`:

```text
ExecStart=/ydvrs/bin/preview.sh
Before=vrs.service
Restart=always
```

`wifi.service`:

```text
ExecStart=/ydvrs/bin/hostapd-start
ExecStop=/ydvrs/bin/hostapd-stop
Type=oneshot
```

`adbd.service`:

```text
ExecStart=/sbin/adbd
Requires=usb.service
Restart=always
```

`dlt.service`:

```text
ExecStartPre=/usr/bin/check_dlt_logstorage.sh
ExecStart=/usr/bin/dlt-daemon
```

## 10. Wi-Fi/AP

Interface:

```text
mlan0: DOWN
uap0: DOWN
```

Khi bật `wifi.service`, script dùng:

```text
uap0: 192.168.1.1
DHCP range: 192.168.1.100 - 192.168.1.200
DNS: 8.8.8.8, 8.8.4.4, 1.1.1.1
lease: 864000 seconds
```

File liên quan:

```text
/ydvrs/bin/hostapd-start
/ydvrs/bin/hostapd-stop
/ydvrs/bin/hostapd.conf
/ydvrs/bin/udhcpd.conf
/mnt/data/systemfile/hostapd.conf
/mnt/data/systemfile/wifi_ssid
/mnt/data/systemfile/wifi_info
/mnt/data/share/hu/wifi/wifi_ssid.txt
```

SSID đọc được từ `/mnt/data/systemfile/wifi_ssid`:

```text
GRANDEUR_6C-1D-EB-91-21-05
```

Hostapd config có các điểm bật/tắt/cấu hình:

- `ssid`
- `wpa_passphrase`
- `hw_mode=a/g`
- `channel`
- `max_num_sta=1`
- `#WIFI_SPEED=5G`
- `#WIFI_SPEED=2G`

Script `hostapd-start` có logic nếu thấy `#WIFI_SPEED=5G` thì sửa config về 2.4G:

- `hw_mode=g`
- `channel=6`
- bỏ `ieee80211ac`
- bỏ `ieee80211n`
- ghi marker `#WIFI_SPEED=2G`

## 11. Network

Interface và IP:

| Interface | Trạng thái | IP |
| --- | --- | --- |
| `eth0` | `NO-CARRIER` | `10.0.0.32/8` |
| `eth0.129` | `LOWERLAYERDOWN` | `10.0.0.32/8` |
| `eth1` | `UP` | `192.168.244.1/24` |
| `mlan0` | `DOWN` | chưa có |
| `uap0` | `DOWN` | sẽ dùng `192.168.1.1` khi bật AP |

Socket nghe:

| Socket | Process | Ý nghĩa |
| --- | --- | --- |
| `0.0.0.0:4321` | `adbd` | ADB TCP |
| `127.0.0.1:5037` | `adbd` | ADB local/server |
| `eth0.129:13402/13404/13405` | `mwd` | middleware/IP service |
| `eth0.129:13800/udp` | `mwd` | middleware UDP |
| `eth0.129:22` | systemd socket | SSH socket theo interface |

## 12. SOME/IP và API nội bộ

File:

```text
/ydvrs/bin/vsomeip_bltncam.json
```

Cấu hình chính:

```text
unicast: 10.0.0.32
application: bltncam
application id: 0x5D01
logging level: info
console log: true
file log: false
dlt log: false
service discovery: enabled
multicast: 224.244.24.245
port: 30490
```

Service IDs:

```text
0x1041
0x1081
0x10c1
0x1101
0x0002
```

Events:

```text
0xA001
0xA002
```

Interface strings tìm thấy trong `vrs_main.out`:

- `BltnCam.Setting.Wifi:v1_0`
- `BltnCam.Storage.Manager:v1_6`
- `BltnCam.System.Manager:v1_1`
- `BltnCam.ParkingEvent.Manager:v3_1`
- `BltnCam.CameraInfo.Manager`
- `Info.Location.MapMatching:v1_1`
- `Info.Update.Process:v4_6`

Nhóm API/chức năng suy ra:

- Wi-Fi setting
- Storage manager
- System manager
- Parking event manager
- Camera info manager
- Map matching/location proxy
- Update process proxy

## 13. Setting keys trong VRS binary

Các key cấu hình tìm được:

```text
rcdDrvMode
rcdDrvEvtMode
rcdPrkMode
rcdPrkEvtMode
shkSensDrvMode
shkSensPrkMode
rcdEvtAlarm
rcdTimMode
rcdSubBattTime
rcdAudioMode
rcdEvtBeforeTime
rcdEvtAfterTime
rcdTimState
rcdTimeItemV2
rcdTimeItem
rcdEvtBeforeTimeItem
rcdEvtAfterTimeItem
modelType
modelYear
```

Các hàm/chuỗi setting quan trọng:

- `recSetOnWhileDriving On/Off`
- `recSetOnWhileParked On/Off`
- `recSetDrivingEvent On/Off`
- `recSetParkedEvent On/Off`
- `recSetAudio On/Off`
- `recSetParkingOperationTime`
- `recSetSensitivityDrivingEvent`
- `recSetSensitivityParkedEvent`
- `recSetTimeLapseInterval`
- `recSetAfterDrivingEventTime`
- `recSetBeforeDrivingEventTime`
- `setFrVerpos`
- `setRrVerpos`
- `evSenStm On/Off`
- `gearPosStm On/Off`
- `locatnStm On/Off`
- `spdStm On/Off`
- `trnSigStm On/Off`
- `timeStm On/Off`
- `reset REC On/Off`

## 14. Camera, ISP, audio, PQ

Chuỗi camera/ISP tìm được trong binary:

- Camera Sensor Vertical Position Command
- Camera Black Bar Setting
- Camera Black Bar Clear
- ISP input status
- ISP version
- ISP sensor status
- ISP Sensor Normal Mode
- ISP Sensor Standby Mode
- ISP Disable IMX424 Motion Detection
- ISP Enable IMX424 Motion Detection
- ISP Sensor Init Check
- CameraInfo Manager

Audio/microphone:

```text
/sys/devices/platform/soc/a8c000.i2c/i2c-12/12-001a/fcam_mic/enable_device
```

Trạng thái đọc được:

```text
fcam_mic enable_device = 0
```

Chuỗi audio:

- PulseAudio check
- audio input switch
- mute
- audio_src
- audio testsrc

PQ/video encoder:

```text
recorderApisSetPqMode
setprop vendor.vidc.enc.disable.pq %d
```

Trong profile:

```text
bPq enabled
```

## 15. Camera layout XML

Thư mục:

```text
/data/misc/camera
/home/misc/camera
```

Các file layout phát hiện:

```text
1cam*.xml
3cam_rgbir.xml
4loopback_test.xml
8cam.xml
8cam_display0.xml
8cam_v4l2.xml
12cam.xml
14stream_display0.xml
dual_csi_4k.xml
```

Các khả năng cấu hình:

| File/nhóm | Chức năng |
| --- | --- |
| `1cam_*` | một camera, input 0, nhiều format |
| `3cam_rgbir.xml` | layout 3 camera/RGBIR |
| `4loopback_test.xml` | loopback test |
| `8cam.xml` | 8 camera/input, display 0/1, grid 2x2 |
| `8cam_v4l2.xml` | 8 camera qua V4L2, output 1920x1020 |
| `12cam.xml` | layout 12 input |
| `14stream_display0.xml` | 14 stream trên display 0 |
| `dual_csi_4k.xml` | dual CSI 4K, 3840x2160 |

Format/mode tìm thấy:

- `NV12`
- `RGB`
- `I420`
- raw/plain16
- op_mode `0`, `1`, `5`
- input `0,1,2,3,4,5,8,9,50`
- display window/grid layout

## 16. GPIO

`gpioinfo` cho thấy nhiều line có tên rõ ràng. Đây là nhóm thao tác rủi ro cao nếu dùng `set`.

### 16.1 `gpiochip0`

| Line | Tên | Hướng/trạng thái | Nhận xét |
| ---: | --- | --- | --- |
| 20 | `snps,reset-gpios` | output, used | reset liên quan controller |
| 24 | `GPIO_FISP_VSYNC` | input, used | front ISP vsync |
| 25 | `soc:dvrs_fcam` | input, used | event/input front cam |
| 32 | CCI I2C data0 | used | camera I2C |
| 33 | CCI I2C clk0 | used | camera I2C |
| 34 | CCI I2C data1 | used | camera I2C |
| 35 | CCI I2C clk1 | used | camera I2C |
| 38 | `FCAM_ISP_RST` | output, used | reset ISP camera trước |
| 39 | `adb-debug-gpio` | input, used | debug ADB GPIO |
| 40 | `GPIO_S_MCU_SLEEP_WAKEUP` | output, used | MCU sleep/wakeup |
| 41 | `ext_power` | input, active-low | nguồn ngoài |
| 44 | `GPIO_CAM_P_EN` | output, used | camera power enable |
| 47 | `GPIO_SOC_PWR_EN` | output, active-low | SoC power enable |
| 48 | `GPIO_S_BAT_DET` | input | battery detect |
| 53 | `GPIO_FCAM_LED_IND` | output, used | LED camera trước |
| 60 | `GPIO_RCAM_LED_IND` | output, used | LED camera sau |
| 64 | `disp_pwdn_pin` | output, used | display power-down |
| 66 | `GPIO_S_SERDES_3P3V_ONOFF` | output, used | SerDes 3.3V |
| 68 | `GPIO_S_SCAP_ONOFF` | output, used | SCAP on/off |
| 71 | `RCAM_ISP_RST` | output, used | reset ISP camera sau |
| 73 | `GPIO_RISP_VSYNC` | input, used | rear ISP vsync |
| 98 | `GPIO_WIFI_PWDN` | output, used | Wi-Fi power-down |
| 100 | `GPIO_S_PHY_LOCAL_WAKEUP` | output, used | PHY local wakeup |
| 101 | `perst-gpio` | output | PCIe reset |
| 105 | `GPIO_S_STR_LEVEL_SHIFT_OE` | output | level shift output enable |
| 121 | `qcom,phy-intr-redirect` | input | PHY interrupt |

### 16.2 `gpiochip1`

| Line | Tên | Hướng/trạng thái | Nhận xét |
| ---: | --- | --- | --- |
| 5 | `PMA_GPIO_SD_MODULE_IND` | output | SD module indicator |
| 6 | `PMA_GPIO_EVENT_SW_IND` | output | event switch indicator |
| 7 | `PMA_GPIO_USB0_VBUS_DET` | input | USB VBUS detect |
| 8 | `PMA_GPIO_SD_PWR_RST` | output | SD power reset |

### 16.3 Nhóm GPIO theo chức năng

Camera:

- `GPIO_CAM_P_EN`
- `FCAM_ISP_RST`
- `RCAM_ISP_RST`
- `GPIO_FISP_VSYNC`
- `GPIO_RISP_VSYNC`
- `GPIO_FCAM_LED_IND`
- `GPIO_RCAM_LED_IND`

Nguồn/MCU:

- `GPIO_SOC_PWR_EN`
- `GPIO_S_MCU_SLEEP_WAKEUP`
- `GPIO_S_BAT_DET`
- `ext_power`

Wi-Fi:

- `GPIO_WIFI_PWDN`

Display/SerDes:

- `disp_pwdn_pin`
- `GPIO_S_SERDES_3P3V_ONOFF`
- `GPIO_S_SCAP_ONOFF`

Storage/SD:

- `PMA_GPIO_SD_MODULE_IND`
- `PMA_GPIO_EVENT_SW_IND`
- `PMA_GPIO_SD_PWR_RST`

## 17. Sysfs, debugfs, device node

### 17.1 Sysfs bật/tắt đáng chú ý

| Path | Trạng thái | Ý nghĩa |
| --- | --- | --- |
| `/sys/devices/platform/soc/a8c000.i2c/i2c-12/12-001a/fcam_mic/enable_device` | `0` | bật/tắt front camera mic |
| `/sys/devices/platform/soc/17c10000.qcom,wdt/disable` | `0` | watchdog disable flag |
| `/sys/devices/platform/soc/a600000.ssusb/mode` | `host` | USB mode |
| `/sys/devices/system/cpu/online` | `0-7` | CPU online |
| `/sys/class/backlight/panel0-backlight/brightness` | `255/255` | panel 0 brightness |
| `/sys/class/backlight/panel1-backlight/brightness` | `255/255` | panel 1 brightness |
| `/sys/class/backlight/panel2-backlight/brightness` | `255/255` | panel 2 brightness |
| `/sys/class/backlight/panel3-backlight/brightness` | `255/255` | panel 3 brightness |

CPU governor:

```text
policy0: schedutil
policy6: schedutil
```

### 17.2 Trace/debug categories

Debugfs/ftrace có nhiều nhóm `enable`:

- `camera`
- `v4l2`
- `gpio`
- `msm_vidc_events`
- `kgsl`
- `drm`
- `asoc`
- kprobes/perf debug

Nhóm này dùng để bật/tắt tracing. Bật nhiều trace có thể ảnh hưởng hiệu năng hoặc sinh log lớn.

### 17.3 Device node liên quan camera/media

Các node đáng chú ý:

```text
/dev/video0
/dev/video1
/dev/video32 ... /dev/video58
/dev/media0
/dev/media1
/dev/v4l-subdev0 ... /dev/v4l-subdev11
/dev/dvrs_fcam
/dev/iio:device0
/dev/i2c-8 ... /dev/i2c-12
/dev/input/by-path/platform-soc:gpio_keys-event
/dev/input/by-path/platform-soc:dvrs_fcam-event
/dev/input/by-path/platform-a8c000.i2c-event
/dev/shm/front.version
/dev/shm/rear.version
/dev/qseecom
/dev/kgsl-3d0
/dev/ion
```

`/dev/shm/front.version` và `/dev/shm/rear.version` là dữ liệu nhị phân ngắn:

```text
01 00 00 17 01 00 00 03 01 00 00 17 01 00 00 03
```

## 18. Mount và vùng dữ liệu

Mount quan trọng:

| Mount | Trạng thái |
| --- | --- |
| `/` | read-only |
| `/firmware` | read-only |
| `/data` | read-write |
| `/home` | read-write |
| `/mnt/data` | read-write |
| `/var` | read-write |
| `/etc/usb` | overlay read-write |
| `/etc/smack/accesses.d` | overlay read-write |
| `/mnt/data/sdcard/data` | texfat từ `/dev/sda1` |

Ý nghĩa:

- Config runtime/persistent chủ yếu ở `/mnt/data/systemfile`.
- App và binary chính ở `/ydvrs/bin`.
- Root filesystem và firmware partition là read-only.

## 19. File config/trạng thái trong `/mnt/data/systemfile`

Các file quan trọng:

```text
vrs_define_config
event_count
prk_evt_sdcard_count
permanent_cam_info
permanent_cam_info_cali
diag
fGsensSensitivityConfig
videolist.db
recorder_info
vrs_RDBIa221_info
wifi_info
hostapd.conf
vrs_config0
vrs_config1
vrs_config2
vrs_config3
permanent
wifi_ssid
permanent_gps_info
optbat_1st
```

Trạng thái đếm event:

```text
event_count: 0 0 0
prk_evt_sdcard_count: 0
```

`vrs_config0..3` là dạng nhị phân có header:

```text
#@!$%
```

Trong đó có version string:

```text
01.12.00.00
```

`vrs_config2` khớp với profile đang dùng, có các slot OWD/DEV/OWP/PEV ở trạng thái off.

## 20. Xinetd và service mạng phụ

Thư mục:

```text
/etc/xinetd.d
```

Các file:

```text
chargen-dgram
chargen-stream
daytime-dgram
daytime-stream
discard-dgram
discard-stream
echo-dgram
echo-stream
ftp-sensor
tcpmux-server
time-dgram
time-stream
```

Nhiều service trong xinetd đang:

```text
disable = yes
```

`ftp-sensor` là sensor phát hiện kết nối FTP:

```text
flags = SENSOR
deny_time = 120
```

## 21. Phân loại mức rủi ro khi thao tác

### An toàn để đọc

Các lệnh/nhóm này phù hợp để kiểm tra:

```text
adb devices -l
adb shell id
adb shell uname -a
adb shell cat /etc/version
adb shell systemctl status ...
adb shell systemctl list-units --type=service --all
adb shell cmdtool state show
adb shell cmdtool state profile info
adb shell cmdtool state gsensor info
adb shell cmdtool state gsensor get threshold
adb shell cmdtool state mcu info
adb shell cmdtool gpio get ...
adb shell journalctl -u vrs --no-pager
```

### Rủi ro thấp đến trung bình

Chỉ dùng khi cần debug:

```text
cmdtool log on|off
cmdtool log level 1~6
cmdtool log gsensor on|off
cmdtool log mcu on|off
systemctl restart dlt
systemctl restart dlt-system
```

Lưu ý: bật debug/trace lâu có thể sinh nhiều log hoặc ảnh hưởng hiệu năng.

### Rủi ro trung bình đến cao

Chỉ dùng khi biết mục tiêu:

```text
cmdtool rec set ...
cmdtool cameraview set ...
cmdtool mcu lvds ...
cmdtool mcu powermode ...
systemctl start/stop wifi
systemctl restart preview
systemctl restart vrs
```

Các lệnh này có thể ảnh hưởng ghi hình, preview, LVDS, nguồn hoặc trạng thái app.

### Rủi ro cao, không chạy tùy tiện

```text
cmdtool update qfil
cmdtool update cpu
cmdtool state dtc clear
cmdtool state wifiPW reset
cmdtool gpio set ...
systemctl stop/disable adbd
systemctl stop/disable vrs
systemctl stop/disable ais_server
systemctl stop/disable systemd-networkd
ghi vào /sys/.../wdt/disable
ghi GPIO power/reset/camera
```

## 22. Kết luận nhanh

Bề mặt điều khiển built-in cam chia thành 7 nhóm chính:

1. `cmdtool`: recorder, cameraview, log, MCU, state, GPIO, update.
2. `systemctl`: bật/tắt service VRS, preview, Wi-Fi, ADB, DLT, network, thermal.
3. `/mnt/data/systemfile`: profile, Wi-Fi, permanent state, event count, G-sensor threshold.
4. `/ydvrs/bin`: app chính, script khởi động, hostapd, SOME/IP config.
5. GPIO: camera power/reset/LED, Wi-Fi power, MCU wake, display/SerDes, SD power.
6. Sysfs/debugfs: mic enable, watchdog, backlight, CPU governor, tracepoint.
7. Camera XML: layout input/display, V4L2, loopback, 8/12/14 stream, dual CSI 4K.

Nếu cần thao tác tiếp, nên đi theo thứ tự an toàn:

1. Đọc lại `cmdtool state show`.
2. Đọc `cmdtool state profile info`.
3. Đọc `journalctl -u vrs`.
4. Chỉ bật log ngắn hạn nếu cần debug.
5. Không chạy `update`, `gpio set`, `dtc clear`, `wifiPW reset` nếu chưa có mục tiêu và payload chính xác.

