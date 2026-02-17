# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Resume Customizer GUI
Windows executable build configuration
"""

import sys
from pathlib import Path

block_cipher = None

# Application data
app_name = 'ResumeCustomizerGUI'
main_script = 'resume_customizer_gui.py'

# Collect all Python files
a = Analysis(
    [main_script],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'openai',
        'pdf_resume_updater',
        'pdf_renderer',
        'resume_customizer',
        'weasyprint',
        'reportlab',
        'ctypes',
        'ctypes.wintypes',  # For Windows console setup
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate entries
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # You can add an icon file here if you have one
)
