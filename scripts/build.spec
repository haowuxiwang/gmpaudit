# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Project root
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# Collect full package data (submodules + data files + binaries) for critical packages.
# hiddenimports alone only tells PyInstaller to find the top-level module — it does NOT
# collect submodules or data files.  collect_all() returns (datas, binaries, hiddenimports).
_collected = {}
for _pkg in [
    'bleach',           # 43 submodules, 12 data files (vendored html5lib)
    'reportlab',        # 159 submodules, 32 data files (CID fonts)
    'pydantic_settings',# 22 submodules
    'httpx',            # 24 submodules
    'aiosqlite',        # 10 submodules
    'xhtml2pdf',        # submodules + pisa
    'markdown',         # submodules
    'pymupdf',          # C extensions
    'mammoth',
    'lxml',             # C extensions
    'numpy',            # C extensions
    'onnxruntime',      # C extensions
    'lightrag',         # LightRAG knowledge graph (pip: lightrag-hku)
    'sentence_transformers',  # embedding model loader
    'transformers',         # HuggingFace model library (sentence_transformers dep)
    'langchain',        # agent framework
    'langchain_core',   # langchain core
    'langchain_openai', # OpenAI adapter
    'langchain_anthropic',  # Anthropic adapter
    'langgraph',        # agent state graph
    'markitdown',       # document converter (pip: markitdown)
    'olefile',          # OLE2 parser for .doc fallback
    'docx',             # python-docx DOCX parser
    'tiktoken',         # tokenizer for LightRAG (Python wrapper + C ext)
    'tiktoken_ext',     # tiktoken encoding definitions (o200k_base etc.)
    'tokenizers',       # HuggingFace tokenizers (sentence_transformers dep)
    'nano_vectordb',    # LightRAG vector storage backend (CRITICAL)
    'aiohttp',          # LightRAG async HTTP dependency
    'networkx',         # LightRAG graph operations
    'pandas',           # LightRAG data processing
    'pypinyin',         # LightRAG Chinese text processing
    'tenacity',         # LightRAG retry logic
    'xlsxwriter',       # LightRAG Excel export (transitive)
]:
    try:
        _collected[_pkg] = collect_all(_pkg)
    except Exception as _exc:
        print(f"WARNING: collect_all failed for {_pkg}: {_exc}")

# rapidocr_onnxruntime: collect_all fails under numpy 2.x, so collect data manually
import importlib
_rapidocr_datas = []
try:
    _rapidocr_spec = importlib.util.find_spec('rapidocr_onnxruntime')
    if _rapidocr_spec and _rapidocr_spec.origin:
        _rapidocr_pkg_dir = os.path.dirname(_rapidocr_spec.origin)
        for _root, _dirs, _files in os.walk(_rapidocr_pkg_dir):
            for _f in _files:
                if _f.endswith(('.onnx', '.yaml', '.json', '.txt')):
                    _src = os.path.join(_root, _f)
                    _dst = os.path.join('rapidocr_onnxruntime', os.path.relpath(_root, _rapidocr_pkg_dir))
                    _rapidocr_datas.append((_src, _dst))
except Exception as _exc:
    print(f"WARNING: manual rapidocr data collection failed: {_exc}")

# tiktoken_ext: namespace package — collect_all may fail, so manual fallback
_tiktoken_ext_datas = []
try:
    _te_spec = importlib.util.find_spec('tiktoken_ext')
    if _te_spec and _te_spec.origin:
        _te_pkg_dir = os.path.dirname(_te_spec.origin)
        for _root, _dirs, _files in os.walk(_te_pkg_dir):
            for _f in _files:
                if _f.endswith(('.py', '.pyd', '.so')):
                    _src = os.path.join(_root, _f)
                    _dst = os.path.join('tiktoken_ext', os.path.relpath(_root, _te_pkg_dir))
                    _tiktoken_ext_datas.append((_src, _dst))
except Exception as _exc:
    print(f"WARNING: tiktoken_ext manual collection failed: {_exc}")

_extra_datas = [item for _items in _collected.values() for item in _items[0]]
_extra_binaries = [item for _items in _collected.values() for item in _items[1]]
_extra_hidden = [item for _items in _collected.values() for item in _items[2]]

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'backend', 'app', 'launcher.py')],
    pathex=[
        os.path.join(PROJECT_ROOT, 'backend'),
        PROJECT_ROOT,
    ],
    binaries=[*_extra_binaries],
    datas=[
        (os.path.join(PROJECT_ROOT, 'backend', 'static'), 'static'),
        (os.path.join(PROJECT_ROOT, 'config', '.env.example'), 'config'),
        *([(os.path.join(PROJECT_ROOT, 'config', '.env'), 'config')] if os.path.exists(os.path.join(PROJECT_ROOT, 'config', '.env')) else []),
        (os.path.join(PROJECT_ROOT, 'agent'), 'agent'),
        (os.path.join(PROJECT_ROOT, 'scripts', 'download_model.py'), 'scripts'),
        (os.path.join(PROJECT_ROOT, 'tools', 'ffmpeg'), 'tools/ffmpeg'),
        (os.path.join(PROJECT_ROOT, 'graphrag_index', 'input'), 'graphrag_index/input'),
        (os.path.join(PROJECT_ROOT, 'graphrag_index', 'lightrag_output'), 'graphrag_index/lightrag_output'),
        *_extra_datas,
        *_rapidocr_datas,
        *_tiktoken_ext_datas,
    ],
    hiddenimports=[
        'app',
        'app.core',
        'app.core.paths',
        'app.core.config',
        'app.core.providers',
        'app.core.database',
        'app.api',
        'app.api.documents',
        'app.api.audit',
        'app.api.reports',
        'app.api.config',
        'app.api.alerts',
        'app.api.agent_audit',
        'app.api.kg',
        'app.api.health',
        'app.models',
        'app.models.document',
        'app.models.audit_task',
        'app.models.finding',
        'app.models.report',
        'app.models.risk_alert',
        'app.models.configuration',
        'app.services',
        'app.services.llm_engine',
        'app.services.document_processor',
        'app.services.audit_engine',
        'app.services.event_bus',
        'app.services.notification',
        'app.services.task_runner',
        'app.services.converter',
        'app.utils',
        'app.utils.agent_helpers',
        'app.utils.file_utils',
        'app.main',
        'app.launcher',
        'app.tkinter_launcher',
        'tkinter',
        '_tkinter',
        'tkinter.ttk',
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
        'langchain',
        'langchain_core',
        'langchain_openai',
        'langchain_anthropic',
        'langgraph',
        'sentence_transformers',
        'lightrag',
        'pydantic',
        'dotenv',
        'multipart',
        'json_repair',
        'docx',
        'fitz',
        'rapidocr_onnxruntime',
        'agent.tools.document_chunker',
        'agent.tools.prompt_loader',
        'agent.graph',
        'agent.state',
        'agent.config',
        'agent.parsers',
        'agent.parsers.pdf_parser',
        'agent.parsers.docx_parser',
        'agent.parsers.text_parser',
        'agent.agents',
        'agent.agents.supervisor',
        'agent.agents.regulation_expert',
        'agent.agents.risk_assessor',
        'agent.agents.report_writer',
        'agent.tools.regulation_db',
        'agent.tools.risk_matrix',
        'agent.tools.json_parser',
        'agent.tools.lightrag_tool',
        'agent.main',
        'agent.trace',
        'modelscope',
        *_extra_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pytest_asyncio',
        'mypy',
        'setuptools',
        'playwright',
        'paddle',
        'llvmlite',
        'agent.tests',
    ],
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
