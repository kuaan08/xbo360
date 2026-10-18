"""Detect Windows build tools and start user-requested official installers."""
import json
import os
from pathlib import Path
import shutil
import subprocess

# Required by the generated MSVC/Windows Clang link command. Checking only
# whether clang++ exists misses installations with no VC or Windows SDK libs.
REQUIRED_WINDOWS_LIBRARIES = ("kernel32.lib", "user32.lib", "msvcrtd.lib", "oldnames.lib")

VS_COMPONENTS = ["Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                 "Microsoft.VisualStudio.Component.VC.Llvm.Clang",
                 "Microsoft.VisualStudio.Component.VC.CMake.Project"]
PACKAGES = {"visual-studio": "Microsoft.VisualStudio.2022.BuildTools",
            "clang": "LLVM.LLVM", "cmake": "Kitware.CMake", "ninja": "Ninja-build.Ninja",
            "java": "Microsoft.OpenJDK.17", "git": "Git.Git"}


def vs_installation():
    """Find the latest VS installation, including partially installed Build Tools."""
    if os.name != "nt":
        return None
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.is_file():
        return None
    # Prefer instances with C++ installed, but still report incomplete VS installs.
    for flags in (["-requires", VS_COMPONENTS[0]], []):
        try:
            result = subprocess.run(
                [str(vswhere), "-latest", "-products", "*", *flags,
                 "-property", "installationPath"],
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    return None


def windows_linker_status(env):
    """Check actual Windows SDK and MSVC .lib files, not just installed tools.

    Visual Studio vcvars64.bat populates LIB with a semicolon-delimited list;
    these paths contain drive colons and must not be split using POSIX pathsep.
    """
    lib_paths = [
        Path(value.strip().strip('"'))
        for value in env.get("LIB", "").split(";")
        if value.strip().strip('"')
    ]
    missing = [name for name in REQUIRED_WINDOWS_LIBRARIES
               if not any((folder / name).is_file() for folder in lib_paths)]
    return {"ready": not missing, "missing_libraries": missing,
            "lib_path_count": len(lib_paths)}


def _capture_vcvars(batch):
    # The batch path comes from vswhere, never from untrusted game metadata.
    if any(c in str(batch) for c in ('"', '&', '|', '%', '\n', '\r')):
        return None, "Unsupported special character in Visual Studio installation path."
    cmd = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/cmd.exe"
    command = f'"{cmd}" /d /s /c ""{batch}" >nul && set"'
    try:
        result = subprocess.run(command, shell=False, capture_output=True,
                                text=True, errors="replace", timeout=45)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"vcvars64.bat could not run: {exc}"
    if result.returncode:
        return None, ("vcvars64.bat failed (exit "
                      f"{result.returncode}). Verify the MSVC tools and Windows SDK in Visual Studio Installer.")
    captured = dict(line.split("=", 1) for line in result.stdout.splitlines()
                    if "=" in line and not line.startswith("="))
    return captured, ""


def build_environment(*, require_windows_linker=False):
    """Capture vcvars and verify that a real Windows native link can find SDK libs.

    Nonstrict mode serves the GUI's toolchain report. Strict mode is used
    before codegen/build and raises an actionable error instead of a CMake
    wall of missing-library messages.
    """
    env = os.environ.copy()
    if os.name != "nt":
        return env
    vs = vs_installation()
    failure = ""
    if not windows_linker_status(env)["ready"]:
        batch = vs / "VC/Auxiliary/Build/vcvars64.bat" if vs else None
        if batch and batch.is_file():
            captured, failure = _capture_vcvars(batch)
            if captured:
                env.update(captured)
        elif vs:
            failure = "Visual Studio is installed, but vcvars64.bat is missing (MSVC C++ build tools not installed)."
        else:
            failure = "Visual Studio C++ Build Tools were not detected."

    # Keep newer standalone LLVM first, while inheriting LIB, INCLUDE,
    # WindowsSdkDir, and PATH from the initialized Visual Studio environment.
    candidates = [vs / "VC/Tools/Llvm/x64/bin", vs / "VC/Tools/Llvm/bin",
                  vs / "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin",
                  vs / "Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja"] if vs else []
    pf = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    candidates = [pf / "LLVM/bin", pf / "CMake/bin"] + candidates
    env["PATH"] = os.pathsep.join(str(p) for p in candidates if p.is_dir()) + os.pathsep + env.get("PATH", "")
    if failure:
        env["XBO360_VCVARS_ERROR"] = failure
    libraries = windows_linker_status(env)
    if require_windows_linker and not libraries["ready"]:
        details = ", ".join(libraries["missing_libraries"])
        extra = f" ({failure})" if failure else ""
        raise RuntimeError(
            f"Windows native linker libraries are missing: {details}.{extra} "
            "Open Visual Studio Installer > Modify > Desktop development with C++; "
            "install MSVC x64/x86 build tools and Windows 10/11 SDK, then restart the app. "
            "Run 'toolchain' again to verify the installation."
        )
    return env



def ninja_executable(env=None):
    """Find a working Ninja executable across PATH, Visual Studio and WinGet.

    A bare shutil.which() can report a stale shell shim, while Visual Studio
    may install ninja.exe outside the launched app's PATH. Always validate
    candidates by running --version before handing CMake an absolute path.
    """
    env = env if env is not None else os.environ
    candidates = []
    found = shutil.which("ninja", path=env.get("PATH"))
    if found:
        candidates.append(Path(found))
    if os.name == "nt":
        vs = vs_installation()
        if vs:
            candidates.extend([
                vs / "Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe",
                vs / "Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja",
            ])
        pf = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        candidates.extend([
            pf / "CMake/bin/ninja.exe",
            pf / "Ninja/ninja.exe",
            local / "Microsoft/WinGet/Links/ninja.exe",
        ])
    checked = set()
    for candidate in candidates:
        # Normalize for duplicates, but don't require every shell shim to
        # implement resolve(strict=True).
        try:
            absolute = candidate.resolve()
        except OSError:
            continue
        if absolute in checked or not absolute.is_file():
            continue
        checked.add(absolute)
        try:
            result = subprocess.run([str(absolute), "--version"], capture_output=True,
                                    text=True, timeout=12, env=env)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return absolute
    return None

def report():
    env = build_environment()
    tools = []
    for name in ("cmake", "ninja", "clang" if os.name == "nt" else "clang-20",
                 "clang++" if os.name == "nt" else "clang++-20", "java", "git"):
        ninja_path = ninja_executable(env) if name == "ninja" else None
        path = str(ninja_path) if ninja_path else (None if name == "ninja" else shutil.which(name, path=env.get("PATH")))
        version = ""
        if path:
            try:
                proc = subprocess.run([path, "-version" if name == "java" else "--version"],
                                      capture_output=True, text=True, timeout=10, env=env)
                version = (proc.stdout or proc.stderr).splitlines()[0]
            except (OSError, subprocess.SubprocessError, IndexError):
                pass
        supported = bool(path)
        if name in ("clang", "clang++", "clang-20", "clang++-20") and version:
            import re
            match = re.search(r"version\s+(\d+)", version)
            supported = bool(match and int(match[1]) >= 20)
        if name == "cmake" and version:
            import re
            match = re.search(r"(\d+)\.(\d+)", version)
            supported = bool(match and tuple(map(int, match.groups())) >= (3, 25))
        tools.append({"name": name, "path": path, "version": version, "ready": supported})
    vs = vs_installation()
    libraries = windows_linker_status(env) if os.name == "nt" else {"ready": True, "missing_libraries": [], "lib_path_count": 0}
    return {"tools": tools, "visual_studio": str(vs) if vs else None,
            "windows_linker": libraries,
            "environment_error": env.get("XBO360_VCVARS_ERROR", ""),
            "desktop_ready": all(t["ready"] for t in tools[:4]) and (os.name != "nt" or libraries["ready"]),
            "winget": shutil.which("winget")}


def installer_command(tool):
    if tool not in PACKAGES:
        raise ValueError("Unknown prerequisite")
    args = ["winget", "install", "--id", PACKAGES[tool], "--exact", "--interactive",
            "--accept-source-agreements", "--accept-package-agreements"]
    if tool == "visual-studio":
        args += ["--override", "--wait --norestart --add Microsoft.VisualStudio.Workload.VCTools "
                 + " ".join("--add " + c for c in VS_COMPONENTS[1:]) + " --includeRecommended"]
    return args


def install(tool):
    if os.name != "nt" or not shutil.which("winget"):
        raise RuntimeError("Windows App Installer/winget is required. Install it from Microsoft, then retry.")
    print("Starting official installer for " + PACKAGES[tool], flush=True)
    code = subprocess.call(installer_command(tool))
    if code:
        raise RuntimeError(f"Installer exited with code {code}. Check its window and retry detection.")
    print("Installation completed. Run the toolchain check again.", flush=True)
