"""Offline tests for portable self-update ZIP validation and staging."""
import tempfile
import os
import subprocess
from unittest import mock
from pathlib import Path
import zipfile
import unittest

import updates


class PortableUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "unpacked"
        self.package = self.root / "release.zip"

    def make_zip(self, extra=None):
        files = {f"Xbox360Recomp/{name}": b"fixture" for name in updates.REQUIRED_PORTABLE_FILES}
        files.update(extra or {})
        with zipfile.ZipFile(self.package, "w", zipfile.ZIP_DEFLATED) as f:
            for name, content in files.items():
                f.writestr(name, content)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell-only syntax check")
    def test_detached_swap_helper_is_valid_powershell(self):
        check = (
            "$tokens=$null; $errors=$null; "
            "[void][System.Management.Automation.Language.Parser]::ParseInput("
            "$env:XBO360_TEST_UPDATER_PS,[ref]$tokens,[ref]$errors); "
            "if ($errors.Count -gt 0) { $errors | Out-String | Write-Output; exit 1 }"
        )
        with mock.patch.dict(os.environ, {"XBO360_TEST_UPDATER_PS": updates._WINDOWS_SWAP_SCRIPT}):
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", check],
                capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_release_unpacks_to_new_staging_folder(self):
        self.make_zip()
        updates.extract_verified_windows_package(self.package, self.out)
        for name in updates.REQUIRED_PORTABLE_FILES:
            self.assertEqual((self.out / name).read_bytes(), b"fixture")
        self.assertFalse((self.root / "Xbox360Recomp.exe").exists())

    def test_path_traversal_is_rejected(self):
        for attack in ("Xbox360Recomp/../../outside.exe",
                       "Xbox360Recomp/../outside",
                       "Xbox360Recomp/C:/Windows/system32.dll",
                       "Xbox360Recomp/dir\\outside"):
            with self.subTest(path=attack):
                self.make_zip({attack: b"malicious"})
                with self.assertRaises(ValueError):
                    updates.extract_verified_windows_package(self.package, self.out)
                self.assertFalse(self.out.exists())
                self.assertFalse((self.root / "outside.exe").exists())

    def test_file_case_collisions_rejected(self):
        self.make_zip({"Xbox360Recomp/xbo360.PY": b"replacement"})
        with self.assertRaisesRegex(ValueError, "Duplicate or case-colliding"):
            updates.extract_verified_windows_package(self.package, self.out)

    def test_missing_runtime_rejected(self):
        with zipfile.ZipFile(self.package, "w") as f:
            f.writestr("Xbox360Recomp/Xbox360Recomp.exe", b"fixture")
        with self.assertRaisesRegex(ValueError, "missing"):
            updates.extract_verified_windows_package(self.package, self.out)

    def test_symlink_rejected(self):
        import stat
        info = zipfile.ZipInfo("Xbox360Recomp/fake-link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.make_zip()
        with zipfile.ZipFile(self.package, "a") as f:
            f.writestr(info, b"../../outside")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            updates.extract_verified_windows_package(self.package, self.out)


if __name__ == "__main__":
    unittest.main()
