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
    echo Khong thay Python/MSYS2 Python.
    echo Cai MSYS2 UCRT64 va cac package trong docs\WINDOWS_PACKAGE.md, hoac them Python vao PATH.
    pause
    exit /b 1
  )
)

echo Nen chay file nay bang Run as administrator de nut Cau hinh IP/ADB Connect dung netsh.
echo.
"%PYTHON%" -m adapter_status.windows_preflight --require-runtime --require-admin
if errorlevel 1 (
  echo.
  echo Runtime Windows chua san sang. Chay bootstrap_windows.cmd hoac check_windows_runtime.cmd de xem thieu gi.
  pause
  exit /b 1
)

"%PYTHON%" "%ROOT%adapter-status-ui"

if errorlevel 1 (
  echo.
  echo App da thoat voi loi. Kiem tra docs\WINDOWS_PACKAGE.md de cai GTK/PyGObject/ADB.
  pause
)
