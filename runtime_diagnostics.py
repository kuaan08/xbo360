"""Read-only runtime crash diagnosis for built ReXGlue ports.

No game files or binary patches are touched. Memory allocation failures,
missing optional update paths and invalid guest function dispatch are separate
symptoms and must not be conflated.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

FATAL = re.compile(r"Call to invalid or unregistered function at guest address (0x[0-9A-Fa-f]{8})")
FILE_MISSING = re.compile(r"\[NtCreateFile\] FAILED: path='([^']+)'")
TITLE = re.compile(r"Initializing shader storage for title ([0-9A-Fa-f]{8})")
GPU = re.compile(r"DXGI adapter: ([^\r\n]+)")


def diagnose_runtime(log: Path, project: Path | None = None) -> dict:
    log = Path(log).resolve(strict=True)
    text = log.read_text(encoding="utf-8", errors="replace")[-16 * 1024 * 1024:]
    targets = list(dict.fromkeys(f"0x{address[2:].upper()}" for address in FATAL.findall(text)))
    missing = list(dict.fromkeys(FILE_MISSING.findall(text)))
    errors = Counter()
    for line in text.splitlines():
        if "BaseHeap::Alloc invalid requested range" in line:
            errors["invalid_heap_range"] += 1
        elif "BaseHeap::Alloc failed to find contiguous range" in line:
            errors["no_contiguous_heap_range"] += 1
        elif "PhysicalHeap::Alloc unable to alloc physical memory in parent heap" in line:
            errors["physical_parent_alloc_failed"] += 1
        elif "Too few processor cores - scheduling will be wonky" in line:
            errors["scheduler_warnings"] += 1
    assets = []
    state = {}
    if project is not None:
        root = Path(project).resolve()
        config = root / "xbo360-project.json"
        if not config.is_file():
            raise ValueError("Provided project directory has no xbo360-project.json.")
        state = json.loads(config.read_text(encoding="utf-8"))
        game_root = Path(state.get("game_root", ""))
        for guest_path in missing:
            # Only map an explicit game-disc D: device, never arbitrary host
            # absolute paths. Do not assume missing update: is required.
            if not guest_path.lower().startswith("d:\\"):
                continue
            relative = Path(*guest_path[3:].replace("/", "\\").split("\\"))
            if any(part in ("", ".", "..") for part in relative.parts):
                continue
            candidate = game_root / relative
            assets.append({"guest_path": guest_path,
                           "host_path": str(candidate),
                           "exists": candidate.is_file()})
    notes = []
    if targets:
        notes.append("Unregistered function target found. Check function boundaries and "
                     "vtable references in the exact XEX; do not guess byte lengths or enable Force as a fix.")
    if errors["invalid_heap_range"] or errors["physical_parent_alloc_failed"]:
        notes.append("Guest physical heap requests are failing. The log does not record "
                     "allocation size, alignment or requested range; it cannot establish host RAM exhaustion.")
    if missing:
        notes.append("Check the extracted game-root filesystem for D: files. "
                     "Missing UPDATE: and patch files may be optional; do not fabricate placeholder assets.")
    if errors["scheduler_warnings"]:
        notes.append("Scheduler warnings are secondary and do not explain the fatal unregistered call.")
    return {
        "log_file": str(log),
        "project": str(Path(project).resolve()) if project else None,
        "title_id": (TITLE.search(text).group(1) if TITLE.search(text) else None),
        "graphics_adapter": (GPU.search(text).group(1) if GPU.search(text) else None),
        "unregistered_function_targets": targets,
        "counts": dict(errors),
        "failed_guest_files": missing,
        "checked_assets": assets,
        "notes": notes,
    }
