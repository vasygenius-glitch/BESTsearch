# build.py
import subprocess
import sys
import os
from sys import platform

def build_app():
    print("⚡ Bolt is preparing the build process...")

    # Path to main script
    main_script = 'main.py'

    # Check if we have the script
    if not os.path.exists(main_script):
        print(f"Error: {main_script} not found!")
        sys.exit(1)

    # Explicitly check for icon
    icon_param = []
    if os.path.exists('icon.ico'):
        icon_param = ['--icon=icon.ico']

    # Base PyInstaller command
    cmd = [
        'pyinstaller',
        '--noconfirm',
        '--onefile',
        '--windowed',
        '--name=TG_Reader_PRO',
        '--clean',
    ] + icon_param

    # Important hidden imports for the packages we are using
    hidden_imports = [
        'rapidfuzz',
        'pymorphy3',
        'pymorphy3_dicts_ru',
        'wordcloud',
        'pandas',
        'matplotlib',
        'lxml',
        'lxml.html',
        'textblob'
    ]

    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])

    # Collect all data for tricky NLP libraries so they don't crash the .exe
    collect_data = ['pymorphy3_dicts_ru', 'wordcloud']
    for data_pkg in collect_data:
        cmd.extend(['--collect-all', data_pkg])

    cmd.append(main_script)

    print(f"Running command: {' '.join(cmd)}")

    # Execute the build
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ Build successful! The executable is located in the 'dist' directory.")
        if platform == "win32":
            print("Look for: dist\\TG_Reader_PRO.exe")
        else:
            print("Look for: dist/TG_Reader_PRO")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed with error code {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    build_app()
