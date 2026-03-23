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

    # Base PyInstaller command
    cmd = [
        'pyinstaller',
        '--noconfirm',
        '--onefile',
        '--windowed',
        '--name=TG_Reader_PRO',
        '--clean',
    ]

    # Important hidden imports for the packages we are using
    hidden_imports = [
        'rapidfuzz',
        'pymorphy3',
        'pymorphy3_dicts_ru',
        'wordcloud',
        'pandas',
        'matplotlib',
        'bs4',
        'lxml',
        'textblob'
    ]

    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])

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
