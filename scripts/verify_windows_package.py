import argparse
import os
import sys
import zipfile


REQUIRED_FILES = {
    "adapter-status-ui",
    "adapter_status/host_platform.py",
    "adapter_status/windows_adb_shell.py",
    "adapter_status/windows_preflight.py",
    "adapter_status/windows_smoke.py",
    "adapter_status/windows_device_validation.py",
    "adapter_status/adb/executor.py",
    "adapter_status/services/connection.py",
    "adapter_status/services/root.py",
    "adapter_status/services/adb_update.py",
    "adapter_status/services/files.py",
    "adapter_status/services/runtime_controls.py",
    "adapter_status/ui/gtk_app.py",
    "run_windows.cmd",
    "bootstrap_windows.cmd",
    "check_windows_runtime.cmd",
    "smoke_windows.cmd",
    "validate_windows_with_device.cmd",
    "requirements-windows.txt",
    "docs/adb_windows.cmd",
    "docs/WINDOWS_PACKAGE.md",
    "docs/cpu_update.bin",
    "tools/README.md",
    "tools/platform-tools/README.md",
    "tools/mpv/README.md",
}


def fail(message):
    print(f"FAIL: {message}")
    return False


def ok(message):
    print(f"OK: {message}")
    return True


def verify(zip_path):
    if not os.path.isfile(zip_path):
        return fail(f"khong thay zip: {zip_path}")

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        all_ok = True

        missing = sorted(REQUIRED_FILES - names)
        if missing:
            all_ok = fail("thieu file bat buoc: " + ", ".join(missing)) and all_ok
        else:
            all_ok = ok("du file bat buoc") and all_ok

        generated = sorted(
            name for name in names if "__pycache__/" in name or name.endswith(".pyc")
        )
        if generated:
            all_ok = fail("zip co file generated: " + ", ".join(generated[:10])) and all_ok
        else:
            all_ok = ok("khong co __pycache__/.pyc") and all_ok

        private_keys = sorted(
            name
            for name in names
            if os.path.basename(name).lower() == "adbkey"
            or name.lower().endswith("/adbkey")
        )
        if private_keys:
            all_ok = fail("zip co private adbkey: " + ", ".join(private_keys)) and all_ok
        else:
            all_ok = ok("khong dong goi private adbkey") and all_ok

        try:
            cpu_info = archive.getinfo("docs/cpu_update.bin")
        except KeyError:
            all_ok = fail("thieu docs/cpu_update.bin") and all_ok
        else:
            all_ok = ok(f"cpu_update.bin size {cpu_info.file_size} bytes") and all_ok
            if cpu_info.file_size <= 0:
                all_ok = fail("cpu_update.bin rong") and all_ok

        bad_separators = sorted(name for name in names if "\\" in name)
        if bad_separators:
            all_ok = fail("zip co path separator Windows sai: " + ", ".join(bad_separators[:10])) and all_ok
        else:
            all_ok = ok("zip path dung dang portable") and all_ok

        return all_ok


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify BLTN Windows package zip")
    parser.add_argument("zip_path")
    args = parser.parse_args(argv)
    return 0 if verify(args.zip_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
