"""Windows native linker detection regressions."""
import tempfile
from pathlib import Path
import unittest
from unittest import mock
import subprocess

import prerequisites


class WindowsLinkerTests(unittest.TestCase):
    def test_ninja_discovery_validates_executable_and_ignores_broken_alias(self):
        with tempfile.TemporaryDirectory() as td:
            ninja = Path(td) / "ninja.exe"
            ninja.write_bytes(b"mock ninja candidate")
            env = {"PATH": td}
            with mock.patch.object(prerequisites.shutil, "which", return_value=str(ninja)), \
                 mock.patch.object(prerequisites.subprocess, "run", return_value=subprocess.CompletedProcess(
                     args=[str(ninja), "--version"], returncode=0, stdout="1.12.1\\n")):
                self.assertEqual(prerequisites.ninja_executable(env), ninja.resolve())
            with mock.patch.object(prerequisites.shutil, "which", return_value=str(ninja)), \
                 mock.patch.object(prerequisites.subprocess, "run", return_value=subprocess.CompletedProcess(
                     args=[str(ninja), "--version"], returncode=1, stdout="", stderr="not executable")):
                # Don't return the unusable candidate from PATH.
                self.assertNotEqual(prerequisites.ninja_executable(env), ninja.resolve())

    def test_linker_requires_sdk_and_msvc_libraries(self):
        with tempfile.TemporaryDirectory() as location:
            sdk = Path(location) / "sdk"
            vc = Path(location) / "vc"
            sdk.mkdir()
            vc.mkdir()
            env = {"LIB": str(sdk) + ";" + str(vc)}
            self.assertIn("kernel32.lib", prerequisites.windows_linker_status(env)["missing_libraries"])
            for name in ("kernel32.lib", "user32.lib"):
                (sdk / name).touch()
            for name in ("msvcrtd.lib", "oldnames.lib"):
                (vc / name).touch()
            self.assertTrue(prerequisites.windows_linker_status(env)["ready"])
            (sdk / "kernel32.lib").unlink()
            self.assertFalse(prerequisites.windows_linker_status(env)["ready"])


if __name__ == "__main__":
    unittest.main()
