"""Build a separate experimental Windows ReXGlue SDK with DX12 + Vulkan.

Uses only a pinned official source commit and its submodules. The default
portable SDK is never overwritten. Not a promise of a working Vulkan game.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

SDK_URL = "https://github.com/rexglue/rexglue-sdk.git"
SDK_REVISION = "f5337cdc947ff6d4c4196737e2c807a48f2a1fc2"
SDK_VERSION = "0.10.0"


def workspace_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache"))) / "Xbox360Recomp" / "sdk-vulkan" / SDK_VERSION


def configure_args(source: Path, prefix: Path, ninja: Path) -> list[str]:
    # Use the upstream pinned Windows preset to preserve compiler flags/ABI.
    return ["cmake", "--preset", "win-amd64",
            "-DREXGLUE_USE_VULKAN:BOOL=ON", "-DREXGLUE_USE_D3D12:BOOL=ON",
            "-DREXGLUE_BUILD_TESTS:BOOL=OFF",
            f"-DCMAKE_INSTALL_PREFIX:PATH={prefix.as_posix()}",
            f"-DCMAKE_MAKE_PROGRAM:FILEPATH={ninja.as_posix()}"]


def validate_installed_sdk(prefix: Path, cache: Path) -> None:
    """Never label a DX12-only SDK as Vulkan-enabled."""
    required = ["bin/rexglue.exe", "bin/rexgpu-xenos.dll", "lib/cmake/rexglue/rexglueConfig.cmake"]
    missing = [p for p in required if not (prefix / p).is_file()]
    if missing:
        raise RuntimeError("Incomplete SDK install: " + ", ".join(missing))
    entries = {}
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and ":" in line:
            key, value = line.split("=", 1)
            entries[key.split(":", 1)[0]] = value
    for option in ("REXGLUE_USE_VULKAN", "REXGLUE_USE_D3D12"):
        if entries.get(option) != "ON":
            raise RuntimeError(f"SDK was not built with {option}=ON")
    # This validates binary presence/config, not driver startup or real gameplay.


def build(*, confirmed: bool, jobs: int = 4) -> Path:
    if os.name != "nt":
        raise RuntimeError("Experimental dual-backend Vulkan SDK builder currently supports Windows x64 only.")
    if not confirmed:
        raise ValueError("An explicit --yes flag is required. This downloads a large official source tree.")
    if not 1 <= jobs <= 32:
        raise ValueError("jobs must be between 1 and 32")
    import prerequisites
    env = prerequisites.build_environment(require_windows_linker=True)
    ninja = prerequisites.ninja_executable(env)
    if ninja is None:
        raise RuntimeError("Ninja is missing. Install Ninja or Visual Studio C++ with CMake tools.")
    for name in ("git", "cmake", "clang++"):
        if not shutil.which(name, path=env.get("PATH")):
            raise RuntimeError(f"Missing {name} in your native toolchain. Open Settings > Check toolchain.")

    base = workspace_root()
    source, prefix = base / "source", base / "install"
    base.mkdir(parents=True, exist_ok=True)
    if not source.is_dir():
        print("Cloning the exact official ReXGlue 0.10.0 SDK and all submodules...", flush=True)
        subprocess.run(["git", "clone", "--branch", "v0.10.0", "--recurse-submodules",
                        SDK_URL, str(source)], cwd=base, env=env, check=True)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                       text=True, env=env).strip()
    if revision.lower() != SDK_REVISION:
        raise RuntimeError("SDK source checkout does not match pinned ReXGlue commit; refusing to build")
    print("Checking dependencies and pinned submodules...", flush=True)
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"],
                   cwd=source, env=env, check=True)
    print("Configuring the experimental dual-backend Xenos runtime...", flush=True)
    subprocess.run(configure_args(source, prefix, ninja), cwd=source, env=env, check=True)
    cache = source / "out" / "build" / "win-amd64" / "CMakeCache.txt"
    if not cache.is_file():
        raise RuntimeError("CMake cache was not created")
    for command in (
        ["cmake", "--build", "out/build/win-amd64", "--config", "Release",
         "--parallel", str(jobs)],
        ["cmake", "--install", "out/build/win-amd64", "--config", "Release",
         "--prefix", str(prefix)],
    ):
        subprocess.run(command, cwd=source, env=env, check=True)
    validate_installed_sdk(prefix, cache)
    print(f"DX12 + Vulkan plugin built. Experimental SDK prefix: {prefix}", flush=True)
    print("Select this prefix in Settings > ReXGlue SDK, then REBUILD your project "
          "to link against the matching runtime. Vulkan gameplay is unverified.", flush=True)
    return prefix
