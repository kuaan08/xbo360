"""Conservative RTTI-independent PowerPC pointer-table discovery prototype.

Input MUST be an already mapped executable image. Encrypted/compressed XEX2
files are not PE images and are deliberately rejected at the CLI layer.
This module never guesses function sizes or changes ReXGlue manifests.

Unlike the upstream ReXGlue VTableScanner, which requires MSVC RTTI/COL,
this can report runs of big-endian PowerPC code pointers in data sections.
Runs of pointers can ALSO be jump tables, so these are candidates, not vtables
or automatically safe function entry points.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def valid_range(value: tuple[int, int]) -> bool:
    return (isinstance(value, tuple) and len(value) == 2
            and all(type(n) is int for n in value) and 0 <= value[0] < value[1] <= 0x100000000)


def scan_tables(image: bytes, *, base: int, data_ranges: list[tuple[int, int]],
                executable_ranges: list[tuple[int, int]], minimum_slots: int = 3,
                max_results: int = 4096) -> list[dict]:
    if type(base) is not int or base < 0 or base > 0xFFFFFFFF:
        raise ValueError("Invalid guest memory image base")
    if not 2 <= minimum_slots <= 256 or not 1 <= max_results <= 100000:
        raise ValueError("Invalid scan settings")
    if not all(valid_range(r) for r in data_ranges + executable_ranges):
        raise ValueError("Invalid memory interval")
    if any(start < base or end > base + len(image) for start, end in data_ranges):
        raise ValueError("Data range is outside the loaded image")
    if any(start < base or end > base + len(image) for start, end in executable_ranges):
        raise ValueError("Code range is outside the loaded image")

    def is_code(value: int) -> bool:
        return value % 4 == 0 and any(start <= value < end for start, end in executable_ranges)

    tables = []
    for data_start, data_end in data_ranges:
        cursor = data_start
        # Big endian as stored in an Xbox 360 executable image.
        while cursor + 4 <= data_end:
            offset = cursor - base
            value = int.from_bytes(image[offset:offset + 4], "big")
            if not is_code(value):
                cursor += 4
                continue
            slot_start = cursor
            pointers = []
            while cursor + 4 <= data_end and len(pointers) < 4096:
                offset = cursor - base
                pointer = int.from_bytes(image[offset:offset + 4], "big")
                if not is_code(pointer):
                    break
                pointers.append(pointer)
                cursor += 4
            if len(pointers) >= minimum_slots:
                tables.append({
                    "data_address": f"0x{slot_start:08X}",
                    "slot_count": len(pointers),
                    "guest_targets": [f"0x{p:08X}" for p in pointers],
                    "distinct_targets": len(set(pointers)),
                    "confidence": "candidate only: vtable or switch/jump table",
                    "not_a_function_boundary": True,
                })
                if len(tables) >= max_results:
                    break
            if not pointers:
                cursor += 4
        if len(tables) >= max_results:
            break
    return tables


def parse_range(value: str) -> tuple[int, int]:
    try:
        first, last = value.split(":", 1)
        result = (int(first, 0), int(last, 0))
        if not valid_range(result):
            raise ValueError
        return result
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use guest START:END, e.g. 0x82000000:0x82010000") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Already decoded/mapped in-memory PE image, NOT a raw XEX")
    parser.add_argument("--base", type=lambda s: int(s, 0), required=True)
    parser.add_argument("--code", action="append", type=parse_range, required=True)
    parser.add_argument("--data", action="append", type=parse_range, required=True)
    args = parser.parse_args(argv)
    if args.image.stat().st_size > 512 * 1024 * 1024:
        parser.error("Image larger than 512 MiB; refusing")
    image = args.image.read_bytes()
    if image.startswith((b"XEX1", b"XEX2")):
        parser.error("An encrypted/compressed XEX is not a mapped PE image. First decode it using your local SDK tools.")
    print(json.dumps({
        "tables": scan_tables(image, base=args.base, executable_ranges=args.code, data_ranges=args.data),
        "warning": "Pointer-table candidates are NOT proven callable functions. Inspect PowerPC CFG and PDATA before adding hints.",
        "automatic_manifest_edits": False,
    }, indent=2))


if __name__ == "__main__":
    main()
