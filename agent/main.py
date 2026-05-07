"""CLI entry point for the GMP audit agent system.

Usage:
    python -m agent.main --file path/to/document.pdf
    python -m agent.main --file path/to/document.docx --type deviation
    python -m agent.main --file path/to/document.txt --focus "数据完整性"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))

from agent.graph import build_audit_graph


async def run_audit(file_path: str, doc_type: str = "unknown", focus: str = "") -> dict:
    """Run the audit workflow on a document.

    Args:
        file_path: Path to the document file
        doc_type: Document type hint (deviation/sop/change_control)
        focus: Optional audit focus area

    Returns:
        Final state dictionary
    """
    graph = build_audit_graph()

    initial_state = {
        "document_name": file_path,
        "document_type": doc_type,
        "audit_focus": focus,
        "document_content": "",
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
    }

    print(f"\n{'='*60}")
    print(f"GMP Audit Agent - Starting")
    print(f"File: {file_path}")
    print(f"Type: {doc_type}")
    if focus:
        print(f"Focus: {focus}")
    print(f"{'='*60}\n")

    final_state = await graph.ainvoke(initial_state)

    # Print execution log
    print(f"\n{'='*60}")
    print("Execution Log:")
    print(f"{'='*60}")
    for msg in final_state.get("messages", []):
        print(f"  > {msg}")

    print(f"\n{'='*60}")
    print(f"Status: {final_state.get('status', 'unknown')}")
    print(f"Iterations: {final_state.get('iteration', 0)}")
    print(f"{'='*60}\n")

    return final_state


def main():
    parser = argparse.ArgumentParser(description="GMP Compliance Audit Agent")
    parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to the document file to audit",
    )
    parser.add_argument(
        "--type", "-t",
        default="unknown",
        choices=["deviation", "sop", "change_control", "unknown"],
        help="Document type hint",
    )
    parser.add_argument(
        "--focus",
        default="",
        help="Optional audit focus area (e.g., 'data integrity')",
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="Output path for the audit report (default: stdout)",
    )

    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    result = asyncio.run(run_audit(args.file, args.type, args.focus))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if result.get("report_markdown"):
            output_path.write_text(result["report_markdown"], encoding="utf-8")
            print(f"Report saved to: {output_path}")
        else:
            # Save raw state as JSON
            output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"State saved to: {output_path}")


if __name__ == "__main__":
    main()
