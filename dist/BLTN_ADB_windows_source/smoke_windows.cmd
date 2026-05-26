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
set "REPORT=%ROOT%reports\windows-smoke-report.txt"

"%PYTHON%" -m adapter_status.windows_preflight --require-runtime
if errorlevel 1 (
  echo.
  echo Preflight fail. Xem thong bao phia tren.
  pause
  exit /b 1
)

"%PYTHON%" -m adapter_status.windows_smoke --require-gtk --report "%REPORT%"
if errorlevel 1 (
  echo.
  echo Smoke test fail. Report: %REPORT%
  pause
  exit /b 1
)

echo.
echo Smoke test OK. Report: %REPORT%
pause
