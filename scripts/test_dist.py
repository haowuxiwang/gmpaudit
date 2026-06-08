"""Distribution artifact test suite for AuditBee.

Tests the packaged dist/AuditBee/ build against all critical paths.
Run with: python scripts/test_dist.py [--port PORT]
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

DIST_DIR = Path(__file__).resolve().parent.parent / "dist" / "AuditBee"
EXE_PATH = DIST_DIR / "AuditBee.exe"
BASE_URL = "http://127.0.0.1:8000"  # Overridden by --port arg in __main__

# Test results collector
results = []


def test(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))


def api_get(path, timeout=10):
    """Make a GET request to the API."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)


def api_post(path, data=None, timeout=30):
    """Make a POST request to the API."""
    url = f"{BASE_URL}{path}"
    try:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
        except Exception:
            detail = str(e)
        return e.code, detail
    except Exception as e:
        return None, str(e)


def api_get_raw(path, timeout=10):
    """Make a GET request and return raw response."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)


# ============================================================
# Layer 1: Startup & Infrastructure
# ============================================================

def test_layer1():
    print("\n=== Layer 1: Startup & Infrastructure ===")

    # 1.1 EXE exists and is executable
    test("1.1 EXE exists", EXE_PATH.exists(), f"size={EXE_PATH.stat().st_size:,} bytes")

    # 1.2 Check critical bundled files
    checks = [
        ("_internal/config/.env.example", "Config template"),
        ("config/.env", "Runtime .env"),
        ("config/.env.example", "Runtime .env.example"),
        ("_internal/agent/__init__.py", "Agent package"),
    ]
    for path, label in checks:
        full = DIST_DIR / path
        test(f"1.2 {label}", full.exists(), path)

    # 1.3 .env does NOT contain real API keys
    env_path = DIST_DIR / "config" / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        has_real_key = any(
            line.strip() and not line.startswith("#") and "=" in line
            and "sk-" in line.split("=", 1)[1]
            for line in content.splitlines()
        )
        test("1.3 No real API keys in .env", not has_real_key)
    else:
        test("1.3 .env exists", False, "config/.env not found")

    # 1.4 Embedding model exists
    model_path = DIST_DIR / "model" / "pytorch_model.bin"
    test("1.4 Embedding model", model_path.exists(),
         f"size={model_path.stat().st_size:,} bytes" if model_path.exists() else "MISSING")


# ============================================================
# Layer 2: API Endpoints (requires running server)
# ============================================================

def test_layer2():
    print("\n=== Layer 2: API Endpoints ===")

    # 2.1 Health check
    status, data = api_get("/api/health")
    test("2.1 Health check", status == 200, f"status={status}")

    # 2.2 DB health check
    status, data = api_get("/api/health/db")
    test("2.2 DB health", status == 200, f"status={status}")

    # 2.3 Static files (frontend)
    status, raw = api_get_raw("/")
    is_html = raw is not None and b"<!doctype html>" in raw.lower()
    test("2.3 Frontend static files", is_html, f"status={status}, is_html={is_html}")

    # 2.4 Document list
    status, data = api_get("/api/documents/")
    test("2.4 Document list", status == 200, f"status={status}")

    # 2.5 Task list
    status, data = api_get("/api/audit/tasks")
    test("2.5 Task list", status == 200, f"status={status}")

    # 2.6 Report list
    status, data = api_get("/api/reports/")
    test("2.6 Report list", status == 200, f"status={status}")

    # 2.7 Config
    status, data = api_get("/api/config/")
    test("2.7 Config list", status == 200, f"status={status}")

    # 2.8 Alerts
    status, data = api_get("/api/alerts/")
    test("2.8 Alert list", status == 200, f"status={status}")

    # 2.9 KG status
    status, data = api_get("/api/kg/status")
    test("2.9 KG status", status == 200, f"status={status}")

    # 2.10 Dashboard
    status, data = api_get("/api/audit/dashboard")
    test("2.10 Dashboard", status == 200, f"status={status}")


# ============================================================
# Layer 3: Core Business Flow
# ============================================================

def test_layer3():
    print("\n=== Layer 3: Core Business Flow ===")

    # 3.1 Upload test document
    test_doc = Path(__file__).resolve().parent.parent / "data" / "test_documents"
    doc_files = list(test_doc.glob("*.txt")) if test_doc.exists() else []

    if not doc_files:
        # Create a simple test document
        test_doc.mkdir(parents=True, exist_ok=True)
        test_file = test_doc / "test_deviation.txt"
        test_file.write_text(
            "偏差处理SOP\n\n"
            "1. 目的：建立偏差处理的标准操作规程\n"
            "2. 范围：适用于生产车间的所有偏差\n"
            "3. 职责：QA 负责偏差的调查和处理\n"
            "4. 程序：发现偏差后应在24小时内填写偏差报告\n"
            "5. 偏差分类：严重偏差、一般偏差、微小偏差\n",
            encoding="utf-8"
        )
        doc_files = [test_file]

    test_file = doc_files[0]
    print(f"  Using test document: {test_file.name}")

    # Upload via multipart form data
    import io
    boundary = "----TestBoundary"
    file_content = test_file.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{test_file.name}"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    ).encode() + file_content + f"\r\n--{boundary}--\r\n".encode()

    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/documents/upload",
            data=body,
            method="POST"
        )
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            upload_status = resp.status
            upload_data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        upload_status = e.code
        try:
            upload_data = json.loads(e.read().decode())
        except Exception:
            upload_data = str(e)
    except Exception as e:
        upload_status = None
        upload_data = str(e)

    test("3.1 Document upload", upload_status == 200,
         f"status={upload_status}, data={str(upload_data)[:200]}")

    if upload_status != 200:
        print("  Skipping remaining Layer 3 tests (upload failed)")
        return

    doc_id = upload_data.get("id") or (upload_data.get("documents", [{}])[0].get("id") if isinstance(upload_data, dict) and "documents" in upload_data else None)

    # Wait for document processing (poll up to 30s)
    doc_status = "unknown"
    for _i in range(10):
        time.sleep(3)
        status, doc_detail = api_get(f"/api/documents/{doc_id}")
        if isinstance(doc_detail, dict):
            doc_status = doc_detail.get("process_status", "unknown")
            if doc_status in ("processed", "failed"):
                break
    test("3.2 Document processed", doc_status == "processed",
         f"status={doc_status}")

    # 3.3 Create audit task
    status, task_data = api_post("/api/audit/tasks", {
        "task_name": "分发测试任务",
        "task_type": "deviation_analysis",
        "document_ids": [doc_id]
    })
    test("3.3 Task created", status == 200,
         f"status={status}, task_id={task_data.get('id') if isinstance(task_data, dict) else 'N/A'}")

    if status != 200 or not isinstance(task_data, dict):
        print("  Skipping remaining Layer 3 tests (task creation failed)")
        return

    task_id = task_data["id"]

    # 3.4 Run task
    status, run_result = api_post(f"/api/audit/tasks/{task_id}/run")
    test("3.4 Task started", status == 200, f"status={status}")

    if status == 200:
        # Wait for task completion (max 600s — agent pipeline can take 5-8 min)
        print("  Waiting for task completion (max 600s)...")
        for i in range(120):
            time.sleep(5)
            status, task_detail = api_get(f"/api/audit/tasks/{task_id}")
            if isinstance(task_detail, dict):
                current_status = task_detail.get("status", "")
                if current_status in ("completed", "failed", "awaiting_review", "rejected"):
                    break
        else:
            current_status = task_detail.get("status", "unknown") if isinstance(task_detail, dict) else "unknown"

        test("3.5 Task completed", current_status in ("completed", "awaiting_review"),
             f"final_status={current_status}")

        # 3.6 Check findings
        status, findings = api_get(f"/api/audit/tasks/{task_id}/findings")
        has_findings = isinstance(findings, list) and len(findings) > 0
        test("3.6 Findings generated", has_findings,
             f"count={len(findings) if isinstance(findings, list) else 0}")

        # 3.7 Check reports (API returns paginated dict {items: [...]} or list)
        status, reports = api_get(f"/api/reports/?task_id={task_id}")
        if isinstance(reports, dict):
            report_items = reports.get("items", [])
        elif isinstance(reports, list):
            report_items = reports
        else:
            report_items = []
        task_reports = [r for r in report_items if isinstance(r, dict) and r.get("task_id") == task_id]
        test("3.7 Report generated", len(task_reports) > 0,
             f"report_count={len(task_reports)}")


# ============================================================
# Layer 4: Knowledge Graph
# ============================================================

def test_layer4():
    print("\n=== Layer 4: Knowledge Graph ===")

    # 4.1 KG status
    status, kg_status = api_get("/api/kg/status")
    test("4.1 KG status query", status == 200)

    # 4.2 KG documents list
    status, kg_docs = api_get("/api/kg/documents")
    test("4.2 KG documents list", status == 200)

    # 4.3 KG query (may return empty if not built)
    status, query_result = api_post("/api/kg/query", {"query": "偏差处理"})
    test("4.3 KG query", status in (200, 404),
         f"status={status}")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuditBee distribution test suite")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    BASE_URL = f"http://127.0.0.1:{args.port}"

    print("=" * 60)
    print("AuditBee Distribution Artifact Test Suite")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    # Layer 1: Filesystem checks (no server needed)
    test_layer1()

    # Check if server is running
    try:
        urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=2)
        server_running = True
    except Exception:
        server_running = False

    proc = None
    if not server_running:
        print("\n" + "=" * 60)
        print("Server not running. Starting AuditBee.exe with --no-launcher...")
        print("=" * 60)

        exe = str(EXE_PATH)
        # CREATE_NO_WINDOW prevents a visible console window on Windows
        # Use DEVNULL for stdout/stderr to prevent pipe buffer overflow
        # (uvicorn logs fill the pipe and block the server process)
        creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        proc = subprocess.Popen(
            [exe, "--no-launcher", "--port", str(args.port)],
            cwd=str(DIST_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

        # Wait for server to be ready
        print("Waiting for server to start...")
        for i in range(30):
            time.sleep(2)
            try:
                urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=2)
                print(f"Server ready after {(i+1)*2}s")
                break
            except Exception:
                pass
        else:
            print("Server failed to start within 60s")
            proc.kill()
            sys.exit(1)

    try:
        test_layer2()
        test_layer3()
        test_layer4()
    finally:
        if proc is not None:
            print("\nStopping server...")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r["passed"]:
                print(f"  FAIL: {r['name']}" + (f" -- {r['detail']}" if r["detail"] else ""))

    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
