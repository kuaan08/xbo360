"""Xbox360Recomp experimental local bug assistant.

Fully offline, deterministic and read-only. There is no hosted AI model,
network call, hidden game patch, or automatic modification of a title.
Explanations are confidence-labelled and can be copied to an external AI by
the user's own choice. AOT recompilation success != title compatibility.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tomllib

from runtime_diagnostics import diagnose_runtime

FATAL = re.compile(r"Call to invalid or unregistered function at guest address (0x[0-9A-Fa-f]{8})")
TIMESTAMPED = re.compile(r"\b(?:my_game|[A-Za-z0-9_]+)_\d{3}(?:\(\d+\))?\.log$", re.I)
UNSUPPORTED_VULKAN = "not compiled into this plugin"
MAX_LOG_BYTES = 8 * 1024 * 1024


def recent_runtime_logs(root: Path, limit: int = 10) -> list[Path]:
    """Only inspect project and one known CMake output layer, never game assets."""
    candidates = []
    for folder in (root, root / "out" / "build"):
        if folder == root:
            files = folder.glob("*.log")
        elif folder.is_dir():
            files = (file for sub in folder.iterdir() if sub.is_dir() for file in sub.glob("*.log"))
        else:
            files = ()
        for candidate in files:
            if candidate.is_file() and TIMESTAMPED.search(candidate.name):
                candidates.append(candidate)
    return sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def scan_report(root: Path) -> dict:
    root = Path(root).resolve(strict=True)
    project_json = root / "xbo360-project.json"
    if not project_json.is_file():
        raise ValueError("Select a prepared Xbox360Recomp project (xbo360-project.json missing)")
    state = json.loads(project_json.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("Invalid project state")
    build_path = root / "build.log"
    build_tail = build_path.read_text(encoding="utf-8", errors="replace")[-MAX_LOG_BYTES:] if build_path.is_file() else ""
    logs = recent_runtime_logs(root)
    history = []
    for path in logs:
        result = diagnose_runtime(path, root)
        raw = path.read_text(encoding="utf-8", errors="replace")[-MAX_LOG_BYTES:]
        history.append({
            "file": str(path),
            "function_targets": result["unregistered_function_targets"],
            "heap_failure_counts": result["counts"],
            "vulkan_missing": UNSUPPORTED_VULKAN in raw,
            "game_files_failed": result["failed_guest_files"],
        })
    latest = history[0] if history else None
    issues = []
    suggestions = []
    if latest:
        if latest["function_targets"]:
            issues.append({
                "id": "unregistered_function",
                "level": "fatal",
                "confidence": "confirmed",
                "summary": "Guest PowerPC indirect call was not present in the generated function table: " +
                           ", ".join(latest["function_targets"]),
                "action": "Verify the exact XEX and function start/size in disassembly; use Function hints only after verification. Do not guess sizes, enable Force or invent code.",
            })
        counts = latest["heap_failure_counts"]
        if counts.get("physical_parent_alloc_failed") or counts.get("invalid_heap_range"):
            issues.append({
                "id": "guest_physical_heap",
                "level": "error",
                "confidence": "confirmed symptom, root cause unknown",
                "summary": f"Physical parent heap failed {counts.get('physical_parent_alloc_failed', 0)} times; "
                           f"invalid ranges {counts.get('invalid_heap_range', 0)} times; "
                           f"contiguous allocation failures {counts.get('no_contiguous_heap_range', 0)} times.",
                "action": "Instrument guest range low/high, size, alignment, heap base, allocation flags and caller in ReXGlue's xmemory.cpp. This does NOT prove Windows RAM exhaustion.",
            })
        if latest["vulkan_missing"]:
            issues.append({
                "id": "vulkan_not_built",
                "level": "error",
                "confidence": "confirmed",
                "summary": "The Xenos GPU plugin was built without its Vulkan backend.",
                "action": "Choose Direct3D 12 now; Vulkan requires a separate ReXGlue SDK compiled with REXGLUE_USE_VULKAN=ON and the Vulkan/SPIR-V sources.",
            })
        missing = latest["game_files_failed"]
        if missing:
            issues.append({
                "id": "missing_files",
                "level": "warning",
                "confidence": "confirmed lookup; optionality unknown",
                "summary": "The title tried to open: " + ", ".join(missing[:7]),
                "action": "Confirm game_root points to the extracted disc. Missing LAYER1/PATCH/UPDATE files can be optional; do not rename bigfiles or create placeholders.",
            })
    if not logs:
        issues.append({
            "id": "no_runtime_log",
            "level": "info",
            "confidence": "confirmed",
            "summary": "No my_game_001.log-like runtime log was found in project output.",
            "action": "Launch the compiled title through Library > Run, then reopen Bug Assistant. Diagnostic logs live beside the native executable.",
        })
    if "not in any function" in build_tail:
        issues.append({
            "id": "unresolved_codegen",
            "level": "warning",
            "confidence": "confirmed in saved build log",
            "summary": "At least one generated-code analysis pass found an unresolved branch.",
            "action": "Review Function hints; a PPC b can be a local branch, not necessarily a new function.",
        })
    if not any(i["id"] == "unresolved_codegen" for i in issues) and state.get("status") == "built":
        suggestions.append("Native link succeeded; that does not establish that any commercial game can start or render.")
    manifest = root / str(state.get("manifest", ""))
    hint_count = 0
    if manifest.is_file() and manifest.parent == root:
        manifest_data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        hint_count = len(manifest_data.get("entrypoint", {}).get("functions", {}))
    safe_info = {
        "project_name": str(state.get("name", "")),
        "project_status": str(state.get("status", "")),
        "hint_count": hint_count,
        "reports_found": len(history),
        "latest": latest,
        "history": history,
        "issues": issues,
        "notes": suggestions,
        "automatic_fixes_applied": False,
        "mode": "Offline diagnostic assistant (rules, not a generative AI)",
    }
    return safe_info


def safe_markdown(report: dict) -> str:
    """Structured, privacy-conscious summary; no game bytes or full local paths."""
    lines = [
        "# Xbox360Recomp bug report",
        "Diagnostic assistant: offline rules, not a machine-learning model.",
        f"Project status: {report.get('project_status', 'unknown')}",
        f"Manifest function hints: {report.get('hint_count', 0)}",
        f"Crash logs analyzed: {report.get('reports_found', 0)}",
    ]
    for item in report["issues"]:
        lines.extend([
            f"## {item['id']} [{item['confidence']}]",
            item["summary"],
            "Next investigation: " + item["action"],
        ])
    lines.append("No automatic changes or fixes were applied to a game or runtime.")
    return "\n\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    print(json.dumps(scan_report(args.project), indent=2, ensure_ascii=False))
