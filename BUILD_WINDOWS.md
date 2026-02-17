# Building Windows Executable

This guide explains how to build a standalone Windows executable (.exe) for the Resume Customizer GUI application.

## Platform analysis (Ubuntu vs Windows)

- **Ubuntu / Linux**: The app is cross-platform. Use `./install_gui.sh` then `./launch_gui.sh` or `python3 resume_customizer_gui.py`. Path handling uses `pathlib`; Windows-specific sanitization is a no-op on Linux.
- **Windows**: The code already supports Windows:
  - `setup_windows_console()` sets UTF-8 in console (only when running in a console).
  - `sanitize_windows_filename` / `sanitize_windows_path` ensure valid paths and drive roots (e.g. `C:\`) are preserved.
  - Frozen EXE: `get_base_path()` in the GUI handles PyInstaller’s `sys.frozen` / `_MEIPASS`.
- **Visual PDF (WeasyPrint vs ReportLab)**: The app can render a “visual” PDF via WeasyPrint (HTML→PDF) or ReportLab. On Ubuntu the script often uses WeasyPrint; the **Windows exe** now prefers ReportLab when running frozen so behavior matches (no silent WeasyPrint failure). If visual rendering still fails, the GUI shows the error in the success dialog so you see why the optional `.visual.pdf` was not created.

## Prerequisites

- **Windows 10/11** (or use WINE on Linux/Mac)
- **Python 3.7 or higher** installed
- **pip** (Python package manager)

## Quick Build (Windows)

1. Open Command Prompt or PowerShell in the project directory
2. Run the build script:
   ```batch
   build_windows.bat
   ```

The script will:
- Install PyInstaller if needed
- Install all dependencies
- Build the executable
- Place it in the `dist/` folder

## Manual Build

If you prefer to build manually:

1. **Install dependencies:**
   ```batch
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. **Build the executable:**
   ```batch
   pyinstaller --clean resume_customizer_gui.spec
   ```

3. **Find your executable:**
   - Location: `dist/ResumeCustomizerGUI.exe`
   - This is a standalone executable that includes all dependencies

## Building on Linux/Mac (for Windows)

If you're on Linux or Mac and want to build a Windows executable, you can use:

1. **Install Wine** (for running Windows tools)
2. **Use the shell script:**
   ```bash
   chmod +x build_windows.sh
   ./build_windows.sh
   ```

Or use **cross-compilation** with PyInstaller in a Windows VM or container.

## Distribution

The built executable (`ResumeCustomizerGUI.exe`) is standalone and includes:
- All Python dependencies
- PyQt6 GUI framework
- OpenAI client library
- PDF processing libraries
- All application code

**You can distribute just the .exe file** - no Python installation required on the target machine!

## Troubleshooting

### Build fails with "Module not found"
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check that PyInstaller is up to date: `pip install --upgrade pyinstaller`

### Executable is large (>100MB)
- This is normal - PyInstaller bundles Python and all libraries
- You can reduce size by excluding unused modules in the `.spec` file

### Executable doesn't run
- Make sure you're building on the same Windows version (or compatible)
- Check Windows Defender isn't blocking it
- Try running from Command Prompt to see error messages

### Missing DLL errors
- Install Visual C++ Redistributable on the target machine
- Or rebuild with `--onefile` option (though this is slower to start)

### WeasyPrint warnings during build
- You may see “WeasyPrint could not import some external libraries”. The build still completes; at runtime the app uses **ReportLab** for the optional “visual” PDF when WeasyPrint fails. Core customization and PDF updates do not depend on WeasyPrint.

## Advanced Options

Edit `resume_customizer_gui.spec` to customize:
- Add an icon file
- Include additional data files
- Exclude unused modules to reduce size
- Change console/console-less mode

## Notes

- First run may be slower as Windows extracts the bundled files
- The executable is self-contained - no Python needed on target machines
- File size is typically 50-150MB depending on included libraries
