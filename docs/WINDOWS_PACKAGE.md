# Dong goi chay tren Windows

Muc tieu cua ban Windows la giu nguyen app GTK va cac workflow ADB hien co:

- Cau hinh IP adapter bang Windows `netsh`.
- ADB Connect bang `adb.exe`.
- Get Root, Thoat Root, Update ADB, Dashboard ECU, File Explorer, Log realtime van di qua cac service Python hien co.
- Mo Terminal dung `docs\adb_windows.cmd`.
- Stream video dung `mpv.exe` neu may Windows co mpv trong `PATH` hoac trong `tools\mpv`.

## Kien truc Windows

```text
run_windows.cmd
    -> Python/MSYS2 UCRT64
    -> adapter-status-ui
    -> adapter_status.ui.gtk_app
    -> adapter_status.services.*
    -> adapter_status.host_platform
    -> adapter_status.adb.executor
    -> netsh / ping / adb.exe / taskkill / PowerShell
```

UI khong goi truc tiep `adb`, `netsh`, `subprocess`. UI chi goi service. Service goi `host_platform` de lay lenh dung theo he dieu hanh, sau do goi executor.

## Cach nhanh nhat tren Windows

1. Giai nen package vao vi du `C:\BLTN_ADB`.
2. Chay `bootstrap_windows.cmd` de cai runtime MSYS2 GTK/Python va `psutil`.
3. Copy Android platform-tools vao `tools\platform-tools` neu may chua co `adb.exe` trong PATH.
4. Copy ADB key rieng vao `%USERPROFILE%\.android`.
5. Chay `smoke_windows.cmd` de kiem tra runtime/app khong can cam BLTN.
6. Chuot phai `run_windows.cmd` -> **Run as administrator**.
7. Khi cam BLTN that, chuot phai `validate_windows_with_device.cmd` -> **Run as administrator** de ghi report ket noi thuc.

Co the chay `check_windows_runtime.cmd` bat cu luc nao de xem con thieu GTK, `psutil`, `adb.exe`, key, hay quyen administrator.

## Phu thuoc can co tren Windows

Khuyen nghi dung MSYS2 UCRT64 vi PyGObject/GTK3 on dinh hon pip Python thuong.

1. Cai MSYS2 vao `C:\msys64`.
2. Mo **MSYS2 UCRT64** va chay:

```bash
pacman -S --needed \
  mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-python-gobject \
  mingw-w64-ucrt-x86_64-gtk3 \
  mingw-w64-ucrt-x86_64-gdk-pixbuf2
```

3. Cai `psutil`:

```bash
python -m pip install -r requirements-windows.txt
```

`bootstrap_windows.cmd` tu dong chay cac buoc pacman/pip tren neu MSYS2 nam tai `C:\msys64`.

4. Cai ADB cho Windows:

- Cach de dong goi portable: dat `adb.exe` vao `tools\platform-tools\adb.exe`.
- Hoac cai Android platform-tools va them thu muc chua `adb.exe` vao `PATH`.

5. Neu can mo video truc tiep:

- Dat `mpv.exe` vao `tools\mpv\mpv.exe`, hoac cai mpv va them vao `PATH`.

## ADB key

Khong dong goi private ADB key vao repo/package.

Tren may Windows, copy key dung vao:

```text
%USERPROFILE%\.android\adbkey
```

Hoac cac thu muc con:

```text
%USERPROFILE%\.android\<model>\adbkey
```

App se tu quet `%USERPROFILE%\.android` va set `ADB_VENDOR_KEYS` bang dau phan cach dung cua Windows.

## Cach chay

1. Giai nen package vao vi du:

```text
C:\BLTN_ADB
```

2. Neu chua cai runtime, chay:

```text
bootstrap_windows.cmd
```

3. Kiem tra runtime:

```text
check_windows_runtime.cmd
```

4. Smoke test app khong can thiet bi:

```text
smoke_windows.cmd
```

5. Chuot phai `run_windows.cmd` -> **Run as administrator**.

Can quyen administrator de nut **Cau hinh IP** va **ADB Connect** goi `netsh` gan IP `192.168.244.10/24` cho adapter.

6. Trong o **Ten cong**, dung ten adapter Windows, vi du:

```text
Ethernet
USB Ethernet/RNDIS Gadget
```

Neu o nay van la ten Linux `enx...`, app se co gang tu do adapter USB/RNDIS tren Windows.

## Kiem chung tren Windows co thiet bi that

Sau khi cam BLTN va chay app duoc, chay:

```text
validate_windows_with_device.cmd
```

Script nay khong chay Get Root hay Update ADB. No chi:

- Kiem tra runtime va quyen Administrator.
- Gan IP adapter bang `netsh`.
- Chay ADB reconnect toi `192.168.244.1:4321`.
- Doc `adb shell id`.
- Doc thu muc `/` bang File Explorer service.
- Ghi report vao `reports\windows-device-validation.txt`.

Neu report PASS thi cac phan nen tang cua app tren Windows da duoc xac nhan: runtime, ADB, key, cau hinh IP, status polling va File Explorer read path.

## File cau hinh tren Windows

```text
%APPDATA%\adapter-status\config.json
%LOCALAPPDATA%\adapter-status\child-processes.json
%LOCALAPPDATA%\adapter-status\runtime-dashboard-state.json
```

## Terminal ADB tren Windows

Nut **Mo Terminal** se chay:

```text
docs\adb_windows.cmd
```

Script nay doc config cua app, thu cau hinh IP bang `netsh`, chay `adb connect`, in `adb devices`, roi mo `adb shell`.

## Build zip tu Ubuntu

Tu thu muc repo:

```bash
bash scripts/package_windows.sh
```

Script nay compile Python vao `/tmp`, chay static preflight, tao zip, verify zip khong co `__pycache__/.pyc` va khong dong goi private `adbkey`.

## Gioi han xac minh

Tren Ubuntu chi xac minh duoc cu phap Python/shell va viec package du file. Buoc xac minh that su tren Windows can chay `run_windows.cmd` tren may Windows co MSYS2 GTK, `adb.exe`, ADB key, va adapter BLTN cam thuc te.
