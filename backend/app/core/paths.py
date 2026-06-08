"""Centralized path resolution for both dev and PyInstaller frozen mode.

Design principle:
- BUNDLE_DIR (sys._MEIPASS): read-only resources bundled by PyInstaller
- APP_DIR (exe directory / project root): writable data that persists across runs
"""

import os
import sys
from pathlib import Path
from typing import Optional

FROZEN = getattr(sys, "frozen", False)

# Read-only resource directory (PyInstaller extracts datas here)
BUNDLE_DIR: Optional[Path] = Path(sys._MEIPASS) if FROZEN else None

# Writable application directory
if FROZEN:
    APP_DIR = Path(os.path.dirname(sys.executable))  # dist/AuditBee/
else:
    APP_DIR = Path(__file__).resolve().parent.parent.parent.parent  # project root

# Resource base: bundled resources in frozen mode, project root in dev
RESOURCE_BASE = BUNDLE_DIR if FROZEN else APP_DIR

# --- Read-only resource paths ---
CONFIG_DIR = RESOURCE_BASE / "config"
AGENT_DIR = RESOURCE_BASE / "agent"
TOOLS_DIR = RESOURCE_BASE / "tools"

# Writable config directory (for .env file that user edits at runtime)
CONFIG_DIR_WRITABLE = APP_DIR / "config"

# Static files: in frozen mode build.spec maps backend/static -> static/ in _internal
if FROZEN:
    STATIC_DIR = BUNDLE_DIR / "static"
else:
    STATIC_DIR = APP_DIR / "backend" / "static"

# Model directory: in frozen mode, prefer the bundled model inside _internal/
# (read-only, no download needed); fall back to APP_DIR/model if not bundled.
if FROZEN:
    _bundled_model = BUNDLE_DIR / "model"
    _default_model = str(_bundled_model if _bundled_model.is_dir() else APP_DIR / "model")
else:
    _default_model = str(APP_DIR / "model")
MODEL_DIR = Path(os.getenv("EMBEDDING_MODEL_PATH") or _default_model)

# --- Writable data paths (always under APP_DIR, never inside _internal) ---
# AUDITBEE_DATA_DIR can be set via --data-dir CLI flag to override the default data directory
_data_dir_override = os.getenv("AUDITBEE_DATA_DIR")
DATA_DIR = Path(_data_dir_override) if _data_dir_override else APP_DIR / "data"
DB_DIR = DATA_DIR / "database"
LOG_DIR = DATA_DIR / "logs"
DOCS_DIR = DATA_DIR / "documents"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

# LightRAG writable output (separate from read-only input)
KG_OUTPUT_DIR = DATA_DIR / "kg_output"

# KG input: writable so users can upload regulation documents at runtime
KG_INPUT_DIR = DATA_DIR / "kg_input"
# Pre-loaded regulation files bundled by PyInstaller (read-only source for first-run copy)
_KG_INPUT_BUNDLED = RESOURCE_BASE / "lightrag_index" / "input"

# Pre-built LightRAG index bundled by PyInstaller (read-only source for first-run copy)
_KG_OUTPUT_BUNDLED = RESOURCE_BASE / "lightrag_index" / "lightrag_output"

# .env file location (writable, user edits via UI)
ENV_FILE = CONFIG_DIR_WRITABLE / ".env"


def ensure_writable_dirs() -> None:
    """Create all writable directories. Call once at startup."""
    for d in [
        DATA_DIR, DB_DIR, LOG_DIR, DOCS_DIR, PROCESSED_DIR,
        REPORTS_DIR, KG_OUTPUT_DIR, CONFIG_DIR_WRITABLE, KG_INPUT_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
