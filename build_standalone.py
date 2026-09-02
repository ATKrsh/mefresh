import os
import sys
import shutil
import subprocess

def build():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(workspace_dir, "src")
    dist_dir = os.path.join(os.path.dirname(workspace_dir), "dist")
    os.makedirs(dist_dir, exist_ok=True)

    # Determine next executable version
    version = 1
    while os.path.exists(os.path.join(dist_dir, f"mefresh_v{version}.exe")) or os.path.exists(os.path.join(workspace_dir, "dist", f"mefresh_v{version}.exe")):
        version += 1

    exe_name = f"mefresh_v{version}.exe"
    print(f"[*] Building versioned executable: {exe_name}...")

    # UI assets path separator (Windows uses ;)
    ui_data = f"{os.path.join(src_dir, 'ui')};ui"

    icon_path = os.path.join(workspace_dir, "icon.ico")
    cmd = [
        "pyinstaller",
        "--name", f"mefresh_v{version}",
        "--onefile",
        "--windowed",
        f"--icon={icon_path}",
        "--add-data", ui_data,
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "PySide6.QtWebEngineCore",
        "--hidden-import", "PySide6.QtWebChannel",
        "--hidden-import", "psutil",
        "--hidden-import", "winreg",
        os.path.join(src_dir, "main.py")
    ]

    print(f"[*] Executing command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=workspace_dir)

    if res.returncode == 0:
        built_exe = os.path.join(workspace_dir, "dist", f"mefresh_v{version}.exe")
        target_exe = os.path.join(dist_dir, exe_name)
        if os.path.exists(built_exe):
            shutil.copy2(built_exe, target_exe)
            print(f"[+] Build SUCCESS! Output executable: {target_exe}")
            return target_exe
        else:
            print(f"[-] Executable built in local dist: {built_exe}")
            return built_exe
    else:
        print(f"[-] PyInstaller failed with code: {res.returncode}")
        return None

if __name__ == "__main__":
    build()
