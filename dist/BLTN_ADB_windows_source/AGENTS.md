
Before writing code:

* Design the architecture first
* Explain module dependencies
* Explain data flow
* Only then generate the code


# Repository Guidelines

## Project Structure & Module Organization
This repository is an operational BLTN ADB and debug-update workspace, not a conventional library package.

- `adapter-status-ui`: thin launcher for the GTK3 app.
- `adapter_status/`: Python package split into UI, service/business logic, ADB execution, config, and process helpers.
- `docs/`: operator documentation, architecture notes, Markdown guides, reports, `.docx` source files, ADB helper scripts, payloads, and public keys.
- `docs/adb.sh`: current Linux ADB connection script.
- `docs/*.bin`, `docs/vrs_update_info`, `docs/YOEUK_public*.pem`, and `ecu-files/`: payloads, public keys, and collected ECU data. Preserve exact filenames.
- `docs/adbscript_linux.sh` and `docs/adbscript_window.bat`: legacy setup scripts.

Avoid editing generated files such as `__pycache__/` or runtime scratch data under `.test-home/`.

## Build, Test, and Development Commands

- `python3 ./adapter-status-ui`: run the GTK status app locally.
- `bash docs/adb.sh`: configure the USB Ethernet interface, connect to ADB, then open `adb shell`.
- `bash -n docs/adb.sh docs/adbscript_linux.sh`: syntax-check shell scripts.
- `python3 -m py_compile adapter-status-ui adapter_status/*.py adapter_status/adb/*.py adapter_status/services/*.py adapter_status/ui/*.py`: syntax-check Python UI/package files.

## Coding Style & Naming Conventions

Use 4-space Python indentation and `UPPER_SNAKE_CASE` constants, matching `adapter-status-ui`. Prefer small helpers for device checks, subprocess calls, and UI state updates. Shell scripts should quote variables, keep output operator-readable, and use explicit paths or config variables. Keep user-facing UI/help text in Vietnamese unless the surrounding section is already English.

## Testing Guidelines

There is no formal automated test suite. Before committing code, run the syntax checks above. If hardware is available, test the workflow: open the UI, configure IP, run ADB Connect, confirm `adb devices`, and verify root/update actions only with the correct debug or CPU payload. For docs, review rendered Markdown and preserve command transcripts exactly.

## Commit & Pull Request Guidelines

Recent history uses short Vietnamese commit messages, with no strict prefix convention. Prefer descriptive messages such as `thêm kiểm tra version trong UI` instead of `ok`. Pull requests should list changed workflows, commands tested, hardware/device state, and screenshots for UI changes. Call out binary, key, archive, or ECU data changes explicitly.

## Security & Configuration Tips

Do not commit private ADB keys from `~/.android`; this repo should only contain intended public keys or payloads. Root/update commands can alter connected devices, so keep payload names exact and avoid running them casually.
