"""Knowledge graph management API (LightRAG-based)."""

import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

INDEX_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "graphrag_index"))
INPUT_DIR = os.path.join(INDEX_ROOT, "input")
OUTPUT_DIR = os.path.join(INDEX_ROOT, "lightrag_output")

# Track build status in-memory
_build_status = {"building": False, "started_at": None, "error": None, "recent_logs": []}


def _append_build_log(message: str) -> None:
    _build_status["recent_logs"] = (_build_status.get("recent_logs", []) + [message])[-50:]


def _get_index_info() -> dict:
    """Check if LightRAG index is built."""
    if not os.path.isdir(OUTPUT_DIR):
        return {"built": False, "file_count": 0, "last_modified": None}

    files = []
    for root, _, filenames in os.walk(OUTPUT_DIR):
        for f in filenames:
            files.append(os.path.join(root, f))

    if not files:
        return {"built": False, "file_count": 0, "last_modified": None}

    latest_mtime = max(os.path.getmtime(f) for f in files)
    return {
        "built": True,
        "file_count": len(files),
        "last_modified": datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat(),
    }


def _parse_graphml(filepath: str) -> dict:
    """Parse GraphML file and return nodes and edges."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}

    # Build key mapping
    key_map = {}
    for key_elem in root.findall("g:key", ns):
        key_id = key_elem.get("id")
        attr_name = key_elem.get("attr.name")
        key_map[key_id] = attr_name

    nodes = []
    edges = []

    graph = root.find("g:graph", ns)
    if graph is None:
        return {"nodes": [], "edges": []}

    # Parse nodes
    for node_elem in graph.findall("g:node", ns):
        node_id = node_elem.get("id")
        node_data = {"id": node_id, "name": node_id, "category": "unknown", "description": ""}

        for data_elem in node_elem.findall("g:data", ns):
            key = data_elem.get("key")
            attr_name = key_map.get(key, "")
            value = data_elem.text or ""

            if attr_name == "entity_type":
                node_data["category"] = value
            elif attr_name == "description":
                node_data["description"] = value

        nodes.append(node_data)

    # Parse edges
    for edge_elem in graph.findall("g:edge", ns):
        source = edge_elem.get("source")
        target = edge_elem.get("target")
        edge_data = {"source": source, "target": target, "label": "", "weight": 1.0}

        for data_elem in edge_elem.findall("g:data", ns):
            key = data_elem.get("key")
            attr_name = key_map.get(key, "")
            value = data_elem.text or ""

            if attr_name == "description":
                edge_data["label"] = value[:100] if value else ""
            elif attr_name == "weight":
                try:
                    edge_data["weight"] = float(value)
                except (ValueError, TypeError):
                    pass

        edges.append(edge_data)

    return {"nodes": nodes, "edges": edges}


@router.get("/status")
async def get_status():
    """Get knowledge graph index status."""
    index_info = _get_index_info()

    input_files = []
    if os.path.isdir(INPUT_DIR):
        input_files = [f for f in os.listdir(INPUT_DIR) if f.endswith((".txt", ".md"))]

    return {
        **index_info,
        "input_file_count": len(input_files),
        "building": _build_status["building"],
    }


@router.get("/graph")
async def get_graph_data():
    """Get knowledge graph nodes and edges for visualization."""
    graphml_path = os.path.join(OUTPUT_DIR, "graph_chunk_entity_relation.graphml")

    if not os.path.isfile(graphml_path):
        raise HTTPException(status_code=404, detail="图谱数据不存在，请先构建索引")

    try:
        data = _parse_graphml(graphml_path)
        return data
    except Exception as exc:
        logger.exception("Failed to parse graphml")
        raise HTTPException(status_code=500, detail=f"解析图谱数据失败: {exc}")


@router.post("/build")
async def build_index(
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    """Trigger LightRAG index build."""
    if _build_status["building"]:
        raise HTTPException(status_code=409, detail="索引正在构建中")

    if not os.path.isdir(INPUT_DIR) or not any(f.endswith((".txt", ".md")) for f in os.listdir(INPUT_DIR)):
        raise HTTPException(status_code=400, detail="没有输入文件，请先将法规文本放入 graphrag_index/input/ 目录")

    async def _build():
        global _build_status
        _build_status = {
            "building": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
            "recent_logs": ["Build started"],
        }
        try:
            from agent.tools.lightrag_tool import build_index as lr_build
            _append_build_log("Initializing LightRAG build")
            await lr_build(force_rebuild=force)
            _append_build_log("Build completed")
            logger.info("LightRAG index build completed")
        except Exception as exc:
            _build_status["error"] = str(exc)
            _append_build_log(f"Build failed: {exc}")
            logger.exception("LightRAG build failed")
        finally:
            _build_status["building"] = False

    background_tasks.add_task(_build)
    return {"status": "building", "message": "索引构建已启动"}


@router.get("/build-status")
async def get_build_status():
    """Get current build status."""
    return {
        "building": _build_status["building"],
        "started_at": _build_status["started_at"],
        "error": _build_status["error"],
        "recent_logs": _build_status.get("recent_logs", []),
    }


class QueryRequest(BaseModel):
    query: str
    method: str = "local"


@router.post("/query")
async def query_kg(request: QueryRequest):
    """Query the knowledge graph."""
    index_info = _get_index_info()
    if not index_info["built"]:
        raise HTTPException(status_code=400, detail="知识图谱索引尚未构建，请先构建索引")

    try:
        from agent.tools.lightrag_tool import lightrag_search
        results = await lightrag_search(request.query, method=request.method)
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询失败: {exc}")


@router.get("/documents")
async def list_documents():
    """List regulation documents in the input directory."""
    if not os.path.isdir(INPUT_DIR):
        return {"documents": []}

    docs = []
    for filename in sorted(os.listdir(INPUT_DIR)):
        filepath = os.path.join(INPUT_DIR, filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            docs.append({
                "filename": filename,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    return {"documents": docs}


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
):
    """Upload a regulation document to the input directory."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # Validate file extension
    allowed_extensions = {".txt", ".md", ".pdf", ".docx"}
    convertible_extensions = {".pdf", ".docx"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 .txt、.md、.pdf、.docx")

    # Validate file size (10MB limit)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    # Ensure input directory exists
    os.makedirs(INPUT_DIR, exist_ok=True)

    # Convert PDF/DOCX to Markdown
    if ext in convertible_extensions:
        from app.services.converter import convert_to_markdown
        try:
            md_text = await convert_to_markdown(content, file.filename)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        save_name = os.path.splitext(file.filename)[0] + ".md"
        filepath = os.path.join(INPUT_DIR, save_name)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_text)
        logger.info("Uploaded and converted %s -> %s (%d chars)", file.filename, save_name, len(md_text))
        return {"message": "文件上传并转换成功", "filename": save_name, "converted_from": file.filename}

    # Save text/markdown files as-is
    filepath = os.path.join(INPUT_DIR, file.filename)
    with open(filepath, "wb") as f:
        f.write(content)

    logger.info("Uploaded document: %s (%d bytes)", file.filename, len(content))
    return {"message": "文件上传成功", "filename": file.filename}


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Delete a regulation document from the input directory."""
    filepath = os.path.join(INPUT_DIR, filename)

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="文件不存在")

    # Security check: ensure filename doesn't contain path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    os.remove(filepath)
    logger.info(f"Deleted document: {filename}")
    return {"message": "文件删除成功"}
