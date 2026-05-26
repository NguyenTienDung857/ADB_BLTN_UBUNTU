@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PATH=%ROOT%tools\platform-tools;%ROOT%tools\mpv;%PATH%"

if defined MSYS2_ROOT (
  set "MSYS2=%MSYS2_ROOT%"
) else (
  set "MSYS2=C:\msys64"
)

if exist "%MSYS2%\ucrt64\bin\python.exe" (
  set "PATH=%MSYS2%\ucrt64\bin;%PATH%"
  set "PYTHON=%MSYS2%\ucrt64\bin\python.exe"
) else (
  set "PYTHON=python"
)

if not exist "%PYTHON%" (
  where %PYTHON% >nul 2>nul
  if errorlevel 1 (
    echo Khong thay Python/MSYS2 Python. Chay bootstrap_windows.cmd truoc.
    pause
    exit /b 1
  )
)

if not exist "%ROOT%reports" mkdir "%ROOT%reports"
set "REPORT=%ROOT%reports\windows-device-validation.txt"

echo Script nay se cau hinh IP adapter bang netsh va connect ADB toi BLTN.
echo Hay chuot phai file nay va chon Run as administrator.
echo Khong chay Get Root hoac Update ADB; chi kiem tra ket noi/doc thu muc /.
echo.

"%PYTHON%" -m adapter_status.windows_preflight --require-runtime --require-admin
if errorlevel 1 (
  echo.
  echo Preflight fail. Chay lai bang Run as administrator va kiem tra adb.exe/key.
  pause
  exit /b 1
)

"%PYTHON%" -m adapter_status.windows_device_validation --report "%REPORT%"
if errorlevel 1 (
  echo.
  echo Device validation FAIL. Report: %REPORT%
  pause
  exit /b 1
)

echo.
echo Device validation PASS. Report: %REPORT%
pause
