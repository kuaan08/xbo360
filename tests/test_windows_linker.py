"""Windows native linker detection regressions."""
import tempfile
from pathlib import Path
import unittest

import prerequisites


class WindowsLinkerTests(unittest.TestCase):
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
