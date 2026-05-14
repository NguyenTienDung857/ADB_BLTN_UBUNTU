import os
import shlex
import shutil
import subprocess

from ..adb.executor import adb_env
from ..constants import APP_DIR, APP_RUN_ID, DEFAULT_ADB_WORKDIR
from ..processes import register_process


def project_workdir():
    return APP_DIR


def docs_dir():
    return os.path.join(project_workdir(), "docs")


def adb_workdir():
    return project_workdir()


def adb_script_candidates():
    return [
        os.path.join(project_workdir(), "adb.sh"),
        os.path.join(docs_dir(), "adb.sh"),
        os.path.join(DEFAULT_ADB_WORKDIR, "adb.sh"),
        os.path.join(DEFAULT_ADB_WORKDIR, "docs", "adb.sh"),
        os.path.join(os.path.expanduser("~"), "adb.sh"),
    ]


def adb_script_path():
    for candidate in adb_script_candidates():
        if os.path.isfile(candidate):
            return candidate
    return None


def preferred_file_dialog_dir():
    for candidate in (docs_dir(), project_workdir(), os.path.expanduser("~")):
        if os.path.isdir(candidate):
            return candidate
    return project_workdir()


def terminal_command(workdir, script_path):
    shell_command = f"bash {shlex.quote(script_path)}; exec bash"
    shell_command_arg = f"bash -lc {shlex.quote(shell_command)}"
    candidates = [
        ("ptyxis", ["--new-window", "--working-directory", workdir, "--", "bash", "-lc", shell_command]),
        ("gnome-terminal", [f"--working-directory={workdir}", "--", "bash", "-lc", shell_command]),
        ("xfce4-terminal", [f"--working-directory={workdir}", "--command", shell_command_arg]),
        ("mate-terminal", [f"--working-directory={workdir}", "--", "bash", "-lc", shell_command]),
        ("konsole", ["--workdir", workdir, "-e", "bash", "-lc", shell_command]),
        ("lxterminal", ["--working-directory", workdir, "-e", shell_command_arg]),
        ("x-terminal-emulator", ["-e", "bash", "-lc", shell_command]),
        ("xterm", ["-e", "bash", "-lc", shell_command]),
    ]
    for executable, args in candidates:
        path = shutil.which(executable)
        if path:
            if executable == "x-terminal-emulator" and os.path.basename(os.path.realpath(path)) == "ptyxis":
                return [
                    path,
                    "--new-window",
                    "--working-directory",
                    workdir,
                    "--",
                    "bash",
                    "-lc",
                    shell_command,
                ]
            return [path] + args
    return None



def open_terminal_session():
    workdir = adb_workdir()
    script_path = adb_script_path()
    if not script_path:
        searched = "\n".join(adb_script_candidates())
        return False, f"Không thấy script adb.sh. Đã tìm:\n{searched}"

    command = terminal_command(workdir, script_path)
    if not command:
        return False, "Không tìm thấy terminal emulator để mở."

    try:
        env = adb_env()
        env["ADAPTER_STATUS_TRACK"] = "1"
        env["ADAPTER_STATUS_RUN_ID"] = APP_RUN_ID
        env["ADAPTER_STATUS_OWNER_PID"] = str(os.getpid())
        proc = subprocess.Popen(command, cwd=workdir, env=env, start_new_session=True)
        register_process(proc.pid, command, "terminal")
    except Exception as exc:
        return False, f"Không mở được terminal: {exc}"
    return True, f"Đã mở terminal tại {workdir} và chạy {script_path}"
