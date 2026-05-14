# Hướng dẫn update file debug lấy quyền root

```text
bltn@bltn-15Z90RT-G-AH55A5:~$ ./adb.sh
Interface: enx1c860b2bbfcf
Host IP:   192.168.244.10/24
ADB:       192.168.244.1:4321
List of devices attached
192.168.244.1:4321    device

/ $ 
bltn@bltn-15Z90RT-G-AH55A5:~$ adb push DEBUG_GN7FL.BLTN_CAM.KOR.01.00_m01.20_c01.20_2325B01103.bin /tmp/cpu_update.bin
DEBUG_GN7FL.BLTN_CAM.KOR.01.00_m01.20_c01.20_2325B01103.bin: 1 file pushed, 0 skipped. 21.8 MB/s (8704 bytes in 0.000s)
bltn@bltn-15Z90RT-G-AH55A5:~$ adb shell
/ $ cmdtool
=========================================================
COMMAND TOOL
              Build Date [Day:2026-04-24][Time:08:51:48]
              HW Ver. 100, SW Ver. 01.00.01.20
                       Insert [help] for more information
                                            YURA CO,. Ltd
=========================================================
VRS> update cpu
*** command status = 0
VRS> bltn@bltn-15Z90RT-G-AH55A5:~$ adb shell
/ $ cd /home/adb
~ $ ./change_file
setuid/setgid 성공, 현재 사용자 ID[0], 그룹 ID[0]입니다.
mount 성공
Passwd 복사 및 수정 성공
command : mv /home/adb/copyPasswdFile /etc/passwd 
build.prob 복사 및 수정 성공
command : mv /home/adb/copyBuildprobFile /build.prop 
change_file 파일 삭제
Rebooting.
bltn@bltn-15Z90RT-G-AH55A5:~$ adb shell
root@sa6155:~# cd /ydvrs/bin
root@sa6155:/ydvrs/bin# mount -o rw,remount /
root@sa6155:/ydvrs/bin# 
bltn@bltn-15Z90RT-G-AH55A5:~$ adb push YOEUK_public.pem /ydvrs/bin/OEMUpdateKey.pem
YOEUK_public.pem: 1 file pushed, 0 skipped. 1.8 MB/s (451 bytes in 0.000s)
bltn@bltn-15Z90RT-G-AH55A5:~$ adb shell
root@sa6155:~# cat /ydvrs/bin/OEMUpdateKey.pem
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzBpU9lLCYjQBDRjj2f55
XaJ9ehCiUxQayTsa9ZApSSbD4g6xtHolKzZ6s+ClGJ5YaJEebauV10QNe/BY/Itd
RRnxJ+5UHKFV0EWkDfYaOxSEbi5jDb65WHbqPnupz9ujQnE8fbVV0captzONeL7w
lj99ZBChkvJcEg/K2wLiVakY3ZiRUQi/yJUizFkOuhPOOV1ab2+pdx2ONavucwRi
Tbt5jHRstNPwJPUyWwTbrjvSkbmb1pl9UZs5UKa4pFN4qtFUpcxUthrIF+qrL2Ke
E1mui9H4h50Gfu0hHT+fuip9uyCUM6szqVS93uL1r+AqcdO4Hoc5Rhp6ifNvGGws
VQIDAQAB
-----END PUBLIC KEY-----
root@sa6155:~#
```
