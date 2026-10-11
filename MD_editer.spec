# build.spec
# -*- mode: python ; coding: utf-8 -*-
import sys, os, glob
import shutil

# ===================== 1. conda-forge 布局适配 =====================
CONDA_ROOT = r"D:\software\miniforge3" # 按你机器改
LIBFFI_CANDIDATES = glob.glob(os.path.join(CONDA_ROOT, 'Library', 'bin', '*.dll')) \
                  + glob.glob(os.path.join(CONDA_ROOT, 'bin', '*.dll'))
binaries = []
for dll in LIBFFI_CANDIDATES:
    binaries.append((dll, '.'))


# ---------- 资源文件 datas ----------
# 源路径相对 spec 文件;目标路径相对 _internal/
datas = [
    # 单文件:UI/md_edit.ui → _internal/UI/md_edit.ui
    ('UI/md_edit.ui', 'UI'),       # 单个文件： (源文件， 目标目录)
    # 整个目录:UI/icons/ → _internal/UI/icons/
    # ('UI/icons', 'UI/icons'),         # 整个子目录(递归拷)： （源目录， 目标目录）
]

# ===================== 2. Analysis 阶段(扫描依赖) =====================
a = Analysis(
    ['main.py'],  # ← 入口文件
    binaries=binaries, # 显式带上 lib*.dll
    # 让 PyInstaller 去 conda 找包
    pathex=[os.path.join(CONDA_ROOT, 'Library', 'bin'),
            os.path.join(CONDA_ROOT, 'Lib', 'site-packages')],
    datas=datas, # 添加资源路径
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# ===================== 3. EXE 阶段 —— 对应命令行参数 -w 不弹黑框(GUI 程序)=====================
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 必须 True,才能走 COLLECT 拆目录
    name='MD_editer',  # ← --name MD_editers
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # ← -w  (无控制台窗口)
                    # True  ← -c  (保留命令行,跟 -w 反义)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,       # 想换图标写 icon='path\\to.ico'
)
# ===================== 4. COLLECT 阶段 —— 对应 -D =====================
# 有 COLLECT() = onedir 模式,产物是 dist\MD_editer\ 目录
# 没有 COLLECT,只用 EXE() + noarchive=True,就是 -F 模式(单文件)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MD_editer', # 输出目录名
)

# ---------- 5. 打包后目录重组 ----------
# 这一段是 spec 的 Python 代码,COLLECT 跑完才执行
DIST = os.path.join('dist', 'MD_editer')
SRC_INTERNAL = os.path.join(DIST, '_internal')
SRC_UI_IN_INTERNAL = os.path.join(DIST, '_internal', 'UI')
DST_UI_TOP = os.path.join(DIST, 'UI')

def safe_rmtree(p):
    if os.path.exists(p):
        shutil.rmtree(p)

if os.path.isdir(SRC_INTERNAL):
    # 把 UI 目录从 _internal 里搬到顶层
    if os.path.isdir(SRC_UI_IN_INTERNAL):
        safe_rmtree(DST_UI_TOP)
        shutil.move(SRC_UI_IN_INTERNAL, DST_UI_TOP)
        print(f'[post] moved UI → {DST_UI_TOP}')
else:
    print('[post] _internal not found,skip')