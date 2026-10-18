"""Regression coverage for the Windows Android export Ninja discovery bug.

No Android SDK, title files, or network are required.
"""
import ast
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import android_build


class AndroidNinjaTests(unittest.TestCase):
    def test_prefer_verified_ninja_even_if_path_contains_spaces(self):
        with tempfile.TemporaryDirectory(prefix="Ninja build tools ") as td:
            expected = (Path(td) / "ninja.exe").resolve()
            with mock.patch("prerequisites.ninja_executable", return_value=expected):
                got = android_build.android_ninja({"PATH": ""})
            self.assertEqual(got, expected)
            self.assertEqual(android_build.android_cmake_ninja_args(got), [
                f"-DCMAKE_MAKE_PROGRAM:FILEPATH={expected.as_posix()}",
                "-DCMAKE_SUPPRESS_REGENERATION=ON",
            ])

    def test_missing_ninja_fails_before_any_native_codegen(self):
        with mock.patch("prerequisites.ninja_executable", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Ninja is missing"):
                android_build.android_ninja({"PATH": ""})

    def test_reject_relative_ninja_path(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            android_build.android_cmake_ninja_args(Path("ninja"))

    def test_both_host_and_android_cmake_configures_get_ninja(self):
        # AST check prevents a regression where only host tools or only the
        # cross-compilation stage receives the CMAKE_MAKE_PROGRAM fix.
        fn = ast.parse(Path(android_build.__file__).read_text(encoding="utf-8"))
        native = next(node for node in fn.body
                      if isinstance(node, ast.FunctionDef) and node.name == "native_project")
        cmake_configures = [
            node for node in ast.walk(native)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "run" and node.args
            and isinstance(node.args[0], ast.List)
            and any(isinstance(item, ast.Constant) and item.value == "-G"
                    for item in node.args[0].elts)
        ]
        self.assertEqual(len(cmake_configures), 2, "Need both host and ARM64 CMake configure calls")
        for node in cmake_configures:
            self.assertTrue(any(isinstance(item, ast.Starred)
                                and isinstance(item.value, ast.Name)
                                and item.value.id == "ninja_args"
                                for item in node.args[0].elts),
                            "Missing verified Ninja path in an Android CMake configure")
        self.assertEqual(sum(1 for node in ast.walk(fn)
                             if isinstance(node, ast.Call)
                             and isinstance(node.func, ast.Name)
                             and node.func.id == "android_ninja"), 2,
                         "Both export early validation and native build require Ninja")


if __name__ == "__main__":
    unittest.main()
