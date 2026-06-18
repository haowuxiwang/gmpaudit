"""Layer 1: KG Data Layer Verification.

Verifies that knowledge graph data exists and is retrievable.
No LLM calls required — only checks data files and fallback DB.
"""

import json
from pathlib import Path

# Project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent
KG_OUTPUT_DIR = _PROJECT_ROOT / "data" / "kg_output"
KG_INPUT_DIR = _PROJECT_ROOT / "data" / "kg_input"


class TestKGDataExists:
    """Verify KG data files exist on disk."""

    def test_lightrag_output_dir_exists(self):
        assert KG_OUTPUT_DIR.is_dir(), f"KG output directory missing: {KG_OUTPUT_DIR}"

    def test_graphml_file_exists(self):
        p = KG_OUTPUT_DIR / "graph_chunk_entity_relation.graphml"
        assert p.exists(), f"GraphML file missing: {p}"
        assert p.stat().st_size > 0, "GraphML file is empty"

    def test_vdb_chunks_exists(self):
        p = KG_OUTPUT_DIR / "vdb_chunks.json"
        assert p.exists(), f"vdb_chunks.json missing: {p}"
        assert p.stat().st_size > 0

    def test_vdb_entities_exists(self):
        p = KG_OUTPUT_DIR / "vdb_entities.json"
        assert p.exists(), f"vdb_entities.json missing: {p}"
        assert p.stat().st_size > 0

    def test_vdb_relationships_exists(self):
        p = KG_OUTPUT_DIR / "vdb_relationships.json"
        assert p.exists(), f"vdb_relationships.json missing: {p}"
        assert p.stat().st_size > 0

    def test_kg_input_files_exist(self):
        txt_files = list(KG_INPUT_DIR.glob("*.txt"))
        assert len(txt_files) >= 10, f"Expected >= 10 input files, found {len(txt_files)}"

    def test_doc_status_shows_processed(self):
        status_file = KG_OUTPUT_DIR / "kv_store_doc_status.json"
        assert status_file.exists(), "doc_status file missing"
        with open(status_file, encoding="utf-8") as f:
            data = json.load(f)
        # Count processed documents
        processed = sum(1 for v in data.values() if isinstance(v, dict) and v.get("status") == "processed")
        assert processed >= 5, f"Expected >= 5 processed docs, found {processed}"


class TestFallbackDB:
    """Verify hardcoded regulation fallback DB works."""

    def test_all_regulations_count(self):
        from agent.tools.regulation_db import GMP_REGULATIONS

        assert len(GMP_REGULATIONS) >= 20, f"Expected >= 20 regulations, found {len(GMP_REGULATIONS)}"

    def test_search_deviation(self):
        from agent.tools.regulation_db import search_regulations

        results = search_regulations("偏差处理", n_results=5)
        assert len(results) > 0, "No results for '偏差处理'"

    def test_search_capa(self):
        from agent.tools.regulation_db import search_regulations

        results = search_regulations("CAPA 纠正预防", n_results=5)
        assert len(results) > 0, "No results for 'CAPA'"

    def test_search_change_control(self):
        from agent.tools.regulation_db import search_regulations

        results = search_regulations("变更控制", n_results=5)
        assert len(results) > 0, "No results for '变更控制'"

    def test_search_result_structure(self):
        from agent.tools.regulation_db import search_regulations

        results = search_regulations("文件管理", n_results=3)
        for r in results:
            assert "regulation" in r, "Result missing 'regulation' field"
            assert "content" in r, "Result missing 'content' field"
            assert r["content"], "Result has empty content"
