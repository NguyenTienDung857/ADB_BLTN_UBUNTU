# Version phần mềm chính của built-in cam

## Xem nhanh software version
```bash
adb shell cat /ydvrs/bin/ver/sw_ver.txt
adb shell cat /mnt/data/share/hu/ver/sw_ver.txt
```

## Log có dòng đầy đủ HW / SW Ver / PLATFORM
```bash
adb shell 'grep -a "PLATFORM" /mnt/data/logs/dvrs_* | tail -n 20'
```

## Platform/SoC Qualcomm
```bash
adb shell cat /sys/devices/soc0/chip_name
adb shell cat /sys/devices/soc0/images
adb shell cat /proc/device-tree/model
adb shell 'cat /proc/device-tree/compatible | tr "\000" "\n"'
```

## OS/rootfs build
```bash
adb shell cat /etc/version
adb shell cat /etc/os-release
```

## Qualcomm firmware/metabuild
```bash
adb shell cat /firmware/verinfo/ver_info.txt
```

## Built-in cam app nằm ở đây
- /etc/systemd/system/vrs.service
- /ydvrs/bin/yappStarter.sh
- /ydvrs/bin/vrs_main.out
- /ydvrs/bin/preview.sh
- /ydvrs/bin/vrs_preview.out
- /ydvrs/bin/vsomeip_bltncam.json

vrs_main.out là binary chính. Trong binary này có sẵn chuỗi:
- 01.12.00.00
- 21c6b54
- 22.23.A0.08.00

Mở bằng:
```bash
adb shell 'strings /ydvrs/bin/vrs_main.out | grep -E "01\.12|21c6b54|22\.23|PLATFORM|GRANDEUR"'
```

## Config/camera/calibration nằm ở
- /data/misc/camera/*.xml
- /home/misc/camera/*.xml
- /mnt/data/systemfile/permanent_cam_info
- /mnt/data/systemfile/permanent_cam_info_cali
- /ydvrs/bin/fcamlensdata.calib
- /firmware/isp/*.bin
- /firmware/mcu/mcu.bin

Ghi chú chính: nếu cần xem “software version” nhanh thì mở /ydvrs/bin/ver/sw_ver.txt. Nếu cần dòng đầy đủ có cả platform thì xem log /mnt/data/logs/dvrs_* hoặc dùng strings trên /ydvrs/bin/vrs_main.out.
