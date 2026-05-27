"""Tests for app.core.paths module."""

import os
from pathlib import Path

from app.core import paths


class TestPathConstants:
    """Verify path constants are correctly defined."""

    def test_frozen_is_false_in_dev(self):
        assert paths.FROZEN is False

    def test_bundle_dir_is_none_in_dev(self):
        assert paths.BUNDLE_DIR is None

    def test_app_dir_is_project_root(self):
        assert paths.APP_DIR.is_dir()
        assert (paths.APP_DIR / "backend").is_dir()
        assert (paths.APP_DIR / "agent").is_dir()

    def test_resource_base_equals_app_dir_in_dev(self):
        assert paths.RESOURCE_BASE == paths.APP_DIR

    def test_config_dir_contains_env_example(self):
        assert paths.CONFIG_DIR.is_dir()
        assert (paths.CONFIG_DIR / ".env.example").is_file()

    def test_static_dir_points_to_backend_static(self):
        assert paths.STATIC_DIR == paths.APP_DIR / "backend" / "static"

    def test_agent_dir_contains_prompts(self):
        assert paths.AGENT_DIR.is_dir()
        assert (paths.AGENT_DIR / "prompts").is_dir()

    def test_tools_dir_path(self):
        assert paths.TOOLS_DIR == paths.APP_DIR / "tools"

    def test_kg_input_dir(self):
        assert paths.KG_INPUT_DIR == paths.DATA_DIR / "kg_input"

    def test_model_dir(self):
        assert paths.MODEL_DIR == paths.APP_DIR / "model"

    def test_data_dir_under_app_dir(self):
        assert paths.DATA_DIR == paths.APP_DIR / "data"

    def test_db_dir_under_data(self):
        assert paths.DB_DIR == paths.DATA_DIR / "database"

    def test_log_dir_under_data(self):
        assert paths.LOG_DIR == paths.DATA_DIR / "logs"

    def test_docs_dir_under_data(self):
        assert paths.DOCS_DIR == paths.DATA_DIR / "documents"

    def test_processed_dir_under_data(self):
        assert paths.PROCESSED_DIR == paths.DATA_DIR / "processed"

    def test_reports_dir_under_data(self):
        assert paths.REPORTS_DIR == paths.DATA_DIR / "reports"

    def test_kg_output_dir_under_data(self):
        assert paths.KG_OUTPUT_DIR == paths.DATA_DIR / "kg_output"

    def test_env_file_in_config(self):
        assert paths.ENV_FILE == paths.APP_DIR / "config" / ".env"

    def test_config_dir_writable(self):
        assert paths.CONFIG_DIR_WRITABLE == paths.APP_DIR / "config"

    def test_all_path_types_are_path(self):
        for name in [
            "APP_DIR", "CONFIG_DIR", "STATIC_DIR", "AGENT_DIR", "TOOLS_DIR",
            "KG_INPUT_DIR", "MODEL_DIR", "DATA_DIR", "DB_DIR", "LOG_DIR",
            "DOCS_DIR", "PROCESSED_DIR", "REPORTS_DIR", "KG_OUTPUT_DIR", "ENV_FILE",
            "CONFIG_DIR_WRITABLE",
        ]:
            assert isinstance(getattr(paths, name), Path), f"{name} should be Path"


class TestEnsureWritableDirs:
    """Test ensure_writable_dirs() creates all directories."""

    def test_creates_all_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(paths, "DB_DIR", tmp_path / "data" / "database")
        monkeypatch.setattr(paths, "LOG_DIR", tmp_path / "data" / "logs")
        monkeypatch.setattr(paths, "DOCS_DIR", tmp_path / "data" / "documents")
        monkeypatch.setattr(paths, "PROCESSED_DIR", tmp_path / "data" / "processed")
        monkeypatch.setattr(paths, "REPORTS_DIR", tmp_path / "data" / "reports")
        monkeypatch.setattr(paths, "KG_OUTPUT_DIR", tmp_path / "data" / "kg_output")
        monkeypatch.setattr(paths, "CONFIG_DIR_WRITABLE", tmp_path / "config")
        monkeypatch.setattr(paths, "KG_INPUT_DIR", tmp_path / "data" / "kg_input")

        paths.ensure_writable_dirs()

        for d in [
            tmp_path / "data",
            tmp_path / "data" / "database",
            tmp_path / "data" / "logs",
            tmp_path / "data" / "documents",
            tmp_path / "data" / "processed",
            tmp_path / "data" / "reports",
            tmp_path / "data" / "kg_output",
            tmp_path / "config",
            tmp_path / "data" / "kg_input",
        ]:
            assert d.is_dir(), f"{d} should exist"

    def test_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(paths, "DB_DIR", tmp_path / "data" / "database")
        monkeypatch.setattr(paths, "LOG_DIR", tmp_path / "data" / "logs")
        monkeypatch.setattr(paths, "DOCS_DIR", tmp_path / "data" / "documents")
        monkeypatch.setattr(paths, "PROCESSED_DIR", tmp_path / "data" / "processed")
        monkeypatch.setattr(paths, "REPORTS_DIR", tmp_path / "data" / "reports")
        monkeypatch.setattr(paths, "KG_OUTPUT_DIR", tmp_path / "data" / "kg_output")
        monkeypatch.setattr(paths, "CONFIG_DIR_WRITABLE", tmp_path / "config")
        monkeypatch.setattr(paths, "KG_INPUT_DIR", tmp_path / "data" / "kg_input")

        paths.ensure_writable_dirs()
        paths.ensure_writable_dirs()  # should not raise

        assert (tmp_path / "data").is_dir()
