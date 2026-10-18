"""CMake/Ninja regeneration regression: xbo360 configures explicitly after codegen."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

import xbo360


class CMakeRegenerationTests(unittest.TestCase):
    def test_workbench_uses_explicit_cmake_configure_without_ninja_regeneration(self):
        args = xbo360.cmake_configure_args("win-amd64-release", Path("C:/path with spaces/sdk"))
        self.assertEqual(args[0:3], ["cmake", "--preset", "win-amd64-release"])
        self.assertIn("-DCMAKE_SUPPRESS_REGENERATION=ON", args)
        self.assertTrue(any("CMAKE_PREFIX_PATH" in x for x in args))

    def test_cmake_uses_verified_absolute_ninja_path_even_with_spaces(self):
        ninja = Path("C:/Users/User/Microsoft WinGet/Ninja/ninja.exe")
        args = xbo360.cmake_configure_args(
            "win-amd64-release", Path("C:/Recomp SDK"), ninja)
        self.assertIn("-DCMAKE_MAKE_PROGRAM:FILEPATH=C:/Users/User/Microsoft WinGet/Ninja/ninja.exe", args)
        self.assertEqual(len([a for a in args if a.startswith("-DCMAKE_MAKE_PROGRAM")]), 1)

    @unittest.skipUnless(shutil.which("cmake") and shutil.which("ninja"), "CMake and Ninja required")
    def test_future_dated_cmake_source_does_not_generate_ninja_regen_rule(self):
        with tempfile.TemporaryDirectory(prefix="xbo360 future timestamp ") as td:
            root = Path(td)
            cmakelists = root / "CMakeLists.txt"
            cmakelists.write_text(
                "cmake_minimum_required(VERSION 3.25)\n"
                "project(recomp_fixture NONE)\n"
                "add_custom_target(dummy ALL COMMAND ${CMAKE_COMMAND} -E echo working)\n",
                encoding="utf-8",
            )
            future = time.time() + 600
            os.utime(cmakelists, (future, future))
            build = root / "out"
            command = ["cmake", "-S", str(root), "-B", str(build), "-G", "Ninja",
                       "-DCMAKE_SUPPRESS_REGENERATION=ON"]
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=35)
            content = (build / "build.ninja").read_text(encoding="utf-8")
            self.assertNotIn("RERUN_CMAKE", content)
            result = subprocess.run(["cmake", "--build", str(build)], check=True,
                                    capture_output=True, text=True, timeout=35)
            self.assertIn("working", result.stdout)


if __name__ == "__main__":
    unittest.main()
