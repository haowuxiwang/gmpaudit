# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Project root
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'backend', 'app', 'launcher.py')],
    pathex=[
        os.path.join(PROJECT_ROOT, 'backend'),
        PROJECT_ROOT,
    ],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, 'backend', 'static'), 'static'),
        (os.path.join(PROJECT_ROOT, 'config'), 'config'),
        (os.path.join(PROJECT_ROOT, 'agent'), 'agent'),
        (os.path.join(PROJECT_ROOT, 'scripts', 'download_model.py'), 'scripts'),
        (os.path.join(PROJECT_ROOT, 'tools', 'ffmpeg'), 'tools/ffmpeg'),
        (os.path.join(PROJECT_ROOT, 'graphrag_index'), 'graphrag_index'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'sqlalchemy.dialects.sqlite',
        'aiosqlite',
        'langchain',
        'langchain_core',
        'langchain_openai',
        'langchain_anthropic',
        'langgraph',
        'sentence_transformers',
        'lightrag',
        'pydantic',
        'pydantic_settings',
        'markdown',
        'markitdown',
        'pymupdf',
        'fitz',
        'mammoth',
        'rapidocr_onnxruntime',
        'httpx',
        'json_repair',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AuditBee',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AuditBee',
)
