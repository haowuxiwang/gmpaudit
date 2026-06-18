"""Pipeline Verification CLI Script.

Runs layer-by-layer verification of the GMP Audit Pipeline.
Produces PASS/FAIL per check with a final summary.

Usage:
    python scripts/verify_pipeline.py --layer 1    # KG data only
    python scripts/verify_pipeline.py --layer 2    # LLM stability only
    python scripts/verify_pipeline.py --e2e        # E2E only
    python scripts/verify_pipeline.py --all        # Everything
    python scripts/verify_pipeline.py --quick      # Skip slow LLM tests
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Setup paths
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env
_env_file = _PROJECT_ROOT / "config" / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        for line in _env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


class VerificationResult:
    def __init__(self, name: str, passed: bool, detail: str = ""):
        self.name = name
        self.passed = passed
        self.detail = detail


def run_check(name: str, fn) -> VerificationResult:
    """Run a check function and return a result."""
    try:
        result = fn()
        if result is True:
            return VerificationResult(name, True)
        elif isinstance(result, str):
            return VerificationResult(name, False, result)
        else:
            return VerificationResult(name, bool(result))
    except Exception as e:
        return VerificationResult(name, False, str(e)[:200])


def layer1_checks() -> list[VerificationResult]:
    """Layer 1: KG Data Layer."""
    from pathlib import Path

    results = []
    project_root = Path(__file__).parent.parent
    kg_output = project_root / "data" / "kg_output"
    kg_input = project_root / "data" / "kg_input"

    def check_dir():
        return kg_output.is_dir() or "KG output dir missing"

    results.append(run_check("KG output directory exists", check_dir))

    def check_graphml():
        p = kg_output / "graph_chunk_entity_relation.graphml"
        return p.exists() and p.stat().st_size > 0 or "GraphML missing/empty"

    results.append(run_check("GraphML index file", check_graphml))

    def check_vdb():
        for name in ["vdb_chunks.json", "vdb_entities.json", "vdb_relationships.json"]:
            p = kg_output / name
            if not p.exists() or p.stat().st_size == 0:
                return f"{name} missing/empty"
        return True

    results.append(run_check("VDB index files", check_vdb))

    def check_input():
        txt_files = list(kg_input.glob("*.txt"))
        return len(txt_files) >= 10 or f"Only {len(txt_files)} input files (need >= 10)"

    results.append(run_check("KG input files (>=10)", check_input))

    def check_status():
        status_file = kg_output / "kv_store_doc_status.json"
        if not status_file.exists():
            return "doc_status file missing"
        with open(status_file, encoding="utf-8") as f:
            data = json.load(f)
        processed = sum(1 for v in data.values() if isinstance(v, dict) and v.get("status") == "processed")
        return processed >= 5 or f"Only {processed} processed docs (need >= 5)"

    results.append(run_check("Doc status (>=5 processed)", check_status))

    def check_fallback_db():
        from agent.tools.regulation_db import GMP_REGULATIONS

        return len(GMP_REGULATIONS) >= 20 or f"Only {len(GMP_REGULATIONS)} regulations (need >= 20)"

    results.append(run_check("Fallback DB (>=20 regulations)", check_fallback_db))

    def check_fallback_search():
        from agent.tools.regulation_db import search_regulations

        results = search_regulations("偏差处理", n_results=3)
        return len(results) > 0 or "No results for fallback search"

    results.append(run_check("Fallback DB search", check_fallback_search))

    return results


def layer2_checks(quick: bool = False) -> list[VerificationResult]:
    """Layer 2: LLM Stability."""
    results = []

    def check_provider():
        from agent.config import get_default_provider

        p = get_default_provider()
        return True if p else "No default provider set"

    results.append(run_check("Default provider set", check_provider))

    def check_fallback():
        from agent.config import get_llm_with_fallback

        llm = get_llm_with_fallback(temperature=0.1)
        return llm is not None or "get_llm_with_fallback returned None"

    results.append(run_check("LLM fallback works", check_fallback))

    if not quick:

        def check_10x():
            import asyncio

            from agent.config import call_llm_with_retry, get_llm_with_fallback

            async def run():
                llm = get_llm_with_fallback(temperature=0.1)
                successes = 0
                auth_errors = 0
                for i in range(10):
                    try:
                        resp = await call_llm_with_retry(llm, f"Say 'pong {i}'")
                        if resp.content:
                            successes += 1
                    except Exception as e:
                        error_str = str(e).lower()
                        if any(kw in error_str for kw in ("401", "403", "unauthorized")):
                            auth_errors += 1
                return successes, auth_errors

            successes, auth_errors = asyncio.run(run())
            if auth_errors > 0:
                return f"{auth_errors} auth errors"
            return successes >= 8 or f"Only {successes}/10 succeeded"

        results.append(run_check("10x consecutive LLM calls", check_10x))

    return results


def layer3_checks() -> list[VerificationResult]:
    """Layer 3: RAG/KG Retrieval with trace."""
    import asyncio

    from agent.trace import PipelineTrace, clear_current_trace, set_current_trace

    results = []

    def check_trace_import():
        return True

    results.append(run_check("Trace module imports", check_trace_import))

    def check_search_trace():

        async def run():
            from agent.agents.regulation_expert import _search_regulations

            trace = PipelineTrace(document_name="test.txt")
            set_current_trace(trace)
            try:
                import sys
                from unittest.mock import patch

                with patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}):
                    results, source = await _search_regulations("偏差处理")
                return source == "fallback_db" and len(trace.kg_events) >= 1
            finally:
                clear_current_trace()

        return asyncio.run(run()) or "Trace not recorded"

    results.append(run_check("KG search records trace", check_search_trace))

    return results


def layer5_checks() -> list[VerificationResult]:
    """Layer 5: LangGraph execution path."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from agent.trace import PipelineTrace, clear_current_trace, set_current_trace

    results = []

    def check_graph_builds():
        from agent.graph import build_audit_graph

        graph = build_audit_graph()
        return graph is not None

    results.append(run_check("Graph builds successfully", check_graph_builds))

    def check_nodes_traced():
        async def run():
            from agent.graph import build_audit_graph

            trace = PipelineTrace(document_name="test.txt")
            set_current_trace(trace)
            try:
                initial_state = {
                    "document_name": "test.txt",
                    "document_path": "test.txt",
                    "document_type": "deviation",
                    "audit_focus": "",
                    "document_content": "偏差处理程序",
                    "next_agent": "",
                    "supervisor_reasoning": "",
                    "matched_regulations": [],
                    "regulation_summary": "",
                    "findings": [],
                    "risk_score": 0,
                    "risk_level": "",
                    "report_markdown": "",
                    "report_path": "",
                    "messages": [],
                    "iteration": 0,
                    "status": "running",
                    "regulation_checked": False,
                    "risk_assessed": False,
                    "report_generated": False,
                }

                mock_llm = MagicMock()
                mock_llm._provider = "test"
                mock_llm._model = "test"
                mock_llm._trace_node = "unknown"
                mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='[{"title":"t"}]'))

                with (
                    patch.dict(sys.modules, {"agent.tools.lightrag_tool": None}),
                    patch("agent.agents.regulation_expert.get_llm_with_fallback", return_value=mock_llm),
                    patch("agent.agents.regulation_expert.load_prompt", return_value="x: {document_content}"),
                    patch("agent.agents.risk_assessor.get_llm_with_fallback", return_value=mock_llm),
                    patch("agent.agents.risk_assessor.load_prompt", return_value="x: {document_content}"),
                    patch("agent.agents.report_writer.get_llm_with_fallback", return_value=mock_llm),
                    patch("agent.agents.report_writer.load_prompt", return_value="x: {document_name}"),
                ):
                    graph = build_audit_graph()
                    await graph.ainvoke(initial_state)

                nodes = {e.node for e in trace.node_events}
                expected = {"parse_doc", "regulation_expert", "risk_assessor", "report_writer"}
                return expected.issubset(nodes) or f"Missing: {expected - nodes}"
            finally:
                clear_current_trace()

        return asyncio.run(run())

    results.append(run_check("All 4 nodes traced", check_nodes_traced))

    return results


def e2e_checks(quick: bool = False) -> list[VerificationResult]:
    """E2E: Full pipeline verification."""
    results = []

    if not quick:

        def check_e2e():
            from agent.main import run_audit

            doc_path = str(_PROJECT_ROOT / "data" / "test_documents" / "sample_deviation.txt")

            async def run():
                return await run_audit(doc_path, doc_type="deviation")

            result = asyncio.run(run())
            trace = result.get("trace")
            if not trace:
                return "No trace in result"
            if not trace.get("kg_events"):
                return "No KG events"
            if not trace.get("llm_events"):
                return "No LLM events"
            nodes = {e["node"] for e in trace.get("node_events", [])}
            if "regulation_expert" not in nodes:
                return "regulation_expert not traced"
            return True

        results.append(run_check("E2E: deviation analysis", check_e2e))

    return results


def print_results(results: list[VerificationResult], layer_name: str):
    """Print results for a layer."""
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n=== {layer_name} ({passed}/{total}) ===")
    for r in results:
        icon = "PASS" if r.passed else "FAIL"
        detail = f" -- {r.detail}" if r.detail else ""
        print(f"  [{icon}] {r.name}{detail}")


def main():
    parser = argparse.ArgumentParser(description="GMP Pipeline Verification")
    parser.add_argument("--layer", type=int, choices=[1, 2, 3, 5], help="Run specific layer")
    parser.add_argument("--e2e", action="store_true", help="Run E2E checks")
    parser.add_argument("--all", action="store_true", help="Run everything")
    parser.add_argument("--quick", action="store_true", help="Skip slow LLM tests")
    args = parser.parse_args()

    if not any([args.layer, args.e2e, args.all]):
        args.all = True

    all_results = []

    if args.all or args.layer == 1:
        results = layer1_checks()
        print_results(results, "Layer 1: KG Data")
        all_results.extend(results)

    if args.all or args.layer == 2:
        results = layer2_checks(quick=args.quick)
        print_results(results, "Layer 2: LLM Stability")
        all_results.extend(results)

    if args.all or args.layer == 3:
        results = layer3_checks()
        print_results(results, "Layer 3: RAG/KG Retrieval")
        all_results.extend(results)

    if args.all or args.layer == 5:
        results = layer5_checks()
        print_results(results, "Layer 5: LangGraph Path")
        all_results.extend(results)

    if args.all or args.e2e:
        results = e2e_checks(quick=args.quick)
        print_results(results, "E2E: Full Pipeline")
        all_results.extend(results)

    # Final summary
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    failed = total - passed

    print(f"\n{'=' * 50}")
    print(f"FINAL RESULT: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 50}")

    if failed > 0:
        print("\nFailed checks:")
        for r in all_results:
            if not r.passed:
                print(f"  - {r.name}: {r.detail}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
