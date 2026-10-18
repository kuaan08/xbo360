"""Hermetic tests for offline bug assistant, no proprietary XEX/log assets."""
import json
from pathlib import Path
import tempfile
import unittest

from bug_assistant import scan_report, safe_markdown


class BugAssistantTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        (self.root / "my_game_manifest.toml").write_text(
            '[entrypoint]\nfile_path = "game/default.xex"\n[entrypoint.functions]\n'
            '"0x823E7730" = { size = 40 }\n', encoding="utf-8")
        (self.root / "xbo360-project.json").write_text(json.dumps(
            {"name": "my_game", "manifest": "my_game_manifest.toml", "status": "built",
             "game_root": str(self.root)}), encoding="utf-8")
        self.logdir = self.root / "out" / "build" / "win-amd64-release"
        self.logdir.mkdir(parents=True)

    def test_guest_function_heap_and_file_errors_reported_separately(self):
        (self.logdir / "my_game_001.log").write_text(
            "[info] Initializing shader storage for title 53510823...\n"
            "[error] BaseHeap::Alloc invalid requested range\n"
            "[error] BaseHeap::Alloc failed to find contiguous range\n"
            "[error] PhysicalHeap::Alloc unable to alloc physical memory in parent heap\n"
            "[warning] [NtCreateFile] FAILED: path='d:\\\\LAYER1.000' -> 0xc000000f\n"
            "[FATAL] Call to invalid or unregistered function at guest address 0x82286360\n",
            encoding="utf-8")
        report = scan_report(self.root)
        self.assertEqual(report["reports_found"], 1)
        self.assertEqual(report["hint_count"], 1)
        self.assertEqual(report["latest"]["function_targets"], ["0x82286360"])
        ids = {item["id"] for item in report["issues"]}
        self.assertIn("unregistered_function", ids)
        self.assertIn("guest_physical_heap", ids)
        self.assertIn("missing_files", ids)
        self.assertFalse(report["automatic_fixes_applied"])
        summary = safe_markdown(report)
        self.assertIn("0x82286360", summary)
        self.assertNotIn(str(self.root), summary)

    def test_vulkan_error_is_compile_capability_not_driver(self):
        (self.logdir / "my_game_002.log").write_text(
            "rexgpu-xenos: requested backend 'vulkan' is not compiled into this plugin\n")
        report = scan_report(self.root)
        vk = next(item for item in report["issues"] if item["id"] == "vulkan_not_built")
        self.assertIn("REXGLUE_USE_VULKAN=ON", vk["action"])
        self.assertNotIn("Update your GPU driver", vk["action"])

    def test_absent_logs_warn_without_crashing(self):
        report = scan_report(self.root)
        self.assertEqual(report["reports_found"], 0)
        self.assertEqual(report["issues"][0]["id"], "no_runtime_log")

    def test_ignores_logs_buried_in_external_assets(self):
        data = self.root / "extracted"
        data.mkdir()
        (data / "my_game_001.log").write_text("FATAL", encoding="utf-8")
        self.assertEqual(scan_report(self.root)["reports_found"], 0)


if __name__ == "__main__":
    unittest.main()
