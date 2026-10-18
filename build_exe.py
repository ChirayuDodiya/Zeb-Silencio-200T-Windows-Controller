import os
import sys
import shutil
import subprocess

def build():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    icon_path = os.path.join("app", "assets", "icon.ico")
    assets_data = f"{os.path.join('app', 'assets')};assets"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=ZEB-Silencio-200T",
        f"--icon={icon_path}",
        f"--add-data={assets_data}",
        "--collect-all=customtkinter",
        "--hidden-import=serial",
        "--hidden-import=serial.tools.list_ports",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--clean",
        "run_app.py"
    ]

    print("Running PyInstaller command:")
    print(" ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"Build failed with exit code {res.returncode}")
        sys.exit(res.returncode)

    built_exe = os.path.join(root_dir, "dist", "ZEB-Silencio-200T.exe")
    dest_exe = os.path.join(root_dir, "ZEB-Silencio-200T.exe")
    if os.path.exists(built_exe):
        shutil.copy2(built_exe, dest_exe)
        print(f"\nSUCCESS! Standalone application created at:\n{dest_exe}")
    else:
        print(f"Executable not found at {built_exe}")

if __name__ == "__main__":
    build()
