"""Validate the experimental dual-graphics SDK builder without network or compilation."""
from pathlib import Path
import tempfile
import unittest

import vulkan_sdk


class VulkanBuildTests(unittest.TestCase):
    def test_configure_keeps_both_backends(self):
        args = vulkan_sdk.configure_args(
            Path("C:/src/rexglue-sdk"),
            Path("C:/Users/User/Local SDK/Vulkan"),
            Path("C:/Program Files/Ninja/ninja.exe"),
        )
        self.assertIn("-DREXGLUE_USE_VULKAN:BOOL=ON", args)
        self.assertIn("-DREXGLUE_USE_D3D12:BOOL=ON", args)
        self.assertIn("-DCMAKE_INSTALL_PREFIX:PATH=C:/Users/User/Local SDK/Vulkan", args)
        self.assertIn("-DCMAKE_MAKE_PROGRAM:FILEPATH=C:/Program Files/Ninja/ninja.exe", args)
        self.assertEqual(args[0:3], ["cmake", "--preset", "win-amd64"])

    def test_prefix_needs_actual_plugin_and_compiled_backend_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            prefix = base / "install"
            for rel in ("bin/rexglue.exe", "bin/rexgpu-xenos.dll",
                        "lib/cmake/rexglue/rexglueConfig.cmake"):
                p = prefix / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"test")
            cache = base / "CMakeCache.txt"
            cache.write_text("REXGLUE_USE_D3D12:BOOL=ON\nREXGLUE_USE_VULKAN:BOOL=OFF\n")
            with self.assertRaisesRegex(RuntimeError, "REXGLUE_USE_VULKAN"):
                vulkan_sdk.validate_installed_sdk(prefix, cache)
            cache.write_text("REXGLUE_USE_D3D12:BOOL=ON\nREXGLUE_USE_VULKAN:BOOL=ON\n")
            vulkan_sdk.validate_installed_sdk(prefix, cache)
            (prefix / "bin/rexgpu-xenos.dll").unlink()
            with self.assertRaisesRegex(RuntimeError, "Incomplete SDK"):
                vulkan_sdk.validate_installed_sdk(prefix, cache)

    def test_confirmation_required_without_external_calls(self):
        with self.assertRaises(RuntimeError if __import__("os").name != "nt" else ValueError):
            vulkan_sdk.build(confirmed=False)


if __name__ == "__main__":
    unittest.main()
