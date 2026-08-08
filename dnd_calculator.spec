# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys
import tkinter

if sys.version_info < (3, 10):
    raise RuntimeError("DND 战斗计算器 v3 构建要求 Python 3.10 或更高版本")
if sys.platform == "darwin" and tkinter.TkVersion < 8.6:
    raise RuntimeError(
        "macOS 系统自带 Tk 8.5 会生成空白窗口；请使用 Python 3.11 与 Tk 8.6+ 构建"
    )

project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / "src" / "dnd_calculator" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["tkinter", "tkinter.ttk", "tkinter.scrolledtext"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="池中社DND战斗计算器v3.1.1",
        debug=False,
        strip=False,
        upx=True,
        console=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="池中社DND战斗计算器v3.1.1")
    app = BUNDLE(
        coll,
        name="池中社DND战斗计算器v3.1.1.app",
        icon=None,
        bundle_identifier="club.chizhong.dnd-calculator",
        info_plist={
            "CFBundleShortVersionString": "3.1.1",
            "CFBundleVersion": "3.1.1",
            "NSHighResolutionCapable": True,
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="池中社DND战斗计算器v3.1.1",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
    )
