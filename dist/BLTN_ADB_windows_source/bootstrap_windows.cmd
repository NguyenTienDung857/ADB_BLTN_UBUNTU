@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
if defined MSYS2_ROOT (
  set "MSYS2=%MSYS2_ROOT%"
) else (
  set "MSYS2=C:\msys64"
)

if not exist "%MSYS2%\usr\bin\bash.exe" (
  echo Khong thay MSYS2 tai %MSYS2%.
  echo Hay cai MSYS2 vao C:\msys64 hoac set MSYS2_ROOT roi chay lai.
  echo Link tai: https://www.msys2.org/
  pause
  exit /b 1
)

echo Cai/cap nhat runtime GTK/Python cho Adapter Status...
"%MSYS2%\usr\bin\bash.exe" -lc "pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-pip mingw-w64-ucrt-x86_64-python-gobject mingw-w64-ucrt-x86_64-gtk3 mingw-w64-ucrt-x86_64-gdk-pixbuf2"
if errorlevel 1 (
  echo pacman cai package bi loi. Kiem tra internet/MSYS2 roi chay lai.
  pause
  exit /b 1
)

set "PATH=%MSYS2%\ucrt64\bin;%ROOT%tools\platform-tools;%ROOT%tools\mpv;%PATH%"
"%MSYS2%\ucrt64\bin\python.exe" -m pip install -r "%ROOT%requirements-windows.txt"
if errorlevel 1 (
  echo pip cai requirements-windows.txt bi loi.
  pause
  exit /b 1
)

if not exist "%ROOT%tools\platform-tools\adb.exe" (
  echo.
  echo Chua thay %ROOT%tools\platform-tools\adb.exe
  echo Hay copy adb.exe va cac DLL platform-tools vao thu muc tools\platform-tools.
  echo Neu adb.exe da nam trong PATH thi van dung duoc.
)

echo.
"%MSYS2%\ucrt64\bin\python.exe" -m adapter_status.windows_preflight --require-runtime
if errorlevel 1 (
  echo.
  echo Bootstrap xong nhung preflight con loi. Sua cac dong FAIL roi chay check_windows_runtime.cmd.
  pause
  exit /b 1
)

echo.
echo Bootstrap OK. Hay chuot phai run_windows.cmd va chon Run as administrator.
pause
