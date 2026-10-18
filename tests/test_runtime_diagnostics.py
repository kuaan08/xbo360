"""Regression tests for real-world startup logs without shipping game files."""
import json
from pathlib import Path
import tempfile
import unittest

from runtime_diagnostics import diagnose_runtime

LOG = r"""[2026-10-18 11:06:15.040] [info] [gpu] [t100] DXGI adapter: Intel(R) UHD Graphics
[2026-10-18 11:06:15.686] [info] [core] [t100] Initializing shader storage for title 53510823...
[2026-10-18 11:06:21.407] [error] [sys] [t200] BaseHeap::Alloc invalid requested range
[2026-10-18 11:06:21.408] [error] [sys] [t200] PhysicalHeap::Alloc unable to alloc physical memory in parent heap
[2026-10-18 11:06:21.408] [error] [sys] [t200] BaseHeap::Alloc failed to find contiguous range
[2026-10-18 11:06:21.519] [warning] [krnl] [t200] [NtCreateFile] FAILED: path='d:\LAYER1.000' -> 0xc000000f
[2026-10-18 11:06:21.530] [warning] [krnl] [t200] [NtCreateFile] FAILED: path='UPDATE:\TITLEUPDATE.000.tiger' -> 0xc000000f
[2026-10-18 11:06:21.530] [critical] [core] [t200] [FATAL] Call to invalid or unregistered function at guest address 0x823E7730
[2026-10-18 11:06:21.530] [critical] [core] [t200] [FATAL] Call to invalid or unregistered function at guest address 0x823E7730
"""


class RuntimeLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "my_game_001.log"
        self.log.write_text(LOG, encoding="utf-8")

    def test_crash_address_and_failure_categories_preserved(self):
        result = diagnose_runtime(self.log)
        self.assertEqual(result["unregistered_function_targets"], ["0x823E7730"])
        self.assertEqual(result["counts"]["invalid_heap_range"], 1)
        self.assertEqual(result["counts"]["physical_parent_alloc_failed"], 1)
        self.assertEqual(result["counts"]["no_contiguous_heap_range"], 1)
        self.assertEqual(result["title_id"], "53510823")
        self.assertEqual(result["failed_guest_files"][0], r"d:\LAYER1.000")
        self.assertIn("UPDATE", result["failed_guest_files"][1])

    def test_checks_guest_d_drive_without_treating_update_as_disc_file(self):
        assets = self.root / "assets"
        assets.mkdir()
        (assets / "LAYER1.000").write_bytes(b"fixture")
        project = self.root / "project"
        project.mkdir()
        (project / "xbo360-project.json").write_text(json.dumps(
            {"game_root": str(assets)}
        ), encoding="utf-8")
        result = diagnose_runtime(self.log, project)
        self.assertEqual(len(result["checked_assets"]), 1)
        self.assertTrue(result["checked_assets"][0]["exists"])
        (assets / "LAYER1.000").unlink()
        self.assertFalse(diagnose_runtime(self.log, project)["checked_assets"][0]["exists"])


if __name__ == "__main__":
    unittest.main()
