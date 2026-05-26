@echo off
setlocal

cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
  echo Khong thay python trong PATH.
  echo Neu dung MSYS2, hay chay file nay trong MSYS2 MinGW shell hoac cai Python cho Windows.
  pause
  exit /b 1
)

python -m adapter_status.windows_adb_shell
