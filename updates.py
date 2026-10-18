"""Explicit GitHub release checks and digest-verified staged update downloads."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request

REPOSITORY = "kuaan08/xbo360"
API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


def release(current, platform_name):
    request = urllib.request.Request(API, headers={"User-Agent": "Xbox360Recomp", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Oversized release response")
    data = json.loads(raw)
    url = data.get("html_url", "")
    if not url.startswith(f"https://github.com/{REPOSITORY}/releases/tag/"):
        raise ValueError("Unexpected release repository")
    desired = {"win-amd64": "Xbox360Recomp-Windows-x64.zip",
               "android-arm64": "Xbox360Recomp-Android.apk"}.get(platform_name)
    asset = next((a for a in data.get("assets", []) if a.get("name") == desired), None)
    tag = data.get("tag_name", "")
    if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+.][A-Za-z0-9.-]+)?", tag):
        raise ValueError("Release has an unsupported version tag")
    numeric = lambda v: tuple(int(n) for n in re.findall(r"\d+", v)[:3])
    return {"version": tag, "current": numeric(current) >= numeric(tag), "url": url,
            "asset": asset, "notes": data.get("body", "")[:10000]}


def download(info, directory):
    asset = info.get("asset")
    if not asset:
        raise ValueError("No update package is published for this platform")
    name = asset["name"]
    if name not in ("Xbox360Recomp-Windows-x64.zip", "Xbox360Recomp-Android.apk"):
        raise ValueError("Unexpected update filename")
    url = asset["browser_download_url"]
    if not url.startswith(f"https://github.com/{REPOSITORY}/releases/download/"):
        raise ValueError("Unexpected update download source")
    digest = asset.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Release asset has no SHA-256 digest; refusing an unverified download")
    if not isinstance(asset.get("size"), int) or not 0 < asset["size"] <= 2 * 1024**3:
        raise ValueError("Invalid update package size")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    partial = target.with_suffix(target.suffix + ".part")
    sha = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > asset["size"]:
                    raise ValueError("Update exceeds its published size")
                out.write(chunk)
                sha.update(chunk)
        if size != asset["size"] or "sha256:" + sha.hexdigest() != digest:
            raise ValueError("Update integrity verification failed")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


# The Windows portable application is an unpacked directory, not an MSI.
# The update helper lives outside that directory, allowing Windows to release
# its running .exe/.dll handles before replacing the whole installation.
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile


REQUIRED_PORTABLE_FILES = (
    "Xbox360Recomp.exe",
    "xbo360.py",
    "python/python.exe",
    "sdk/bin/rexglue.exe",
)

# This script is written into the OS temp directory (not downloaded content)
# and launched only after a local user has accepted "Install update", or
# explicitly enabled automatic installation at startup.
_WINDOWS_SWAP_SCRIPT = r'''
param(
  [Parameter(Mandatory=$true)][int]$ParentPid,
  [Parameter(Mandatory=$true)][string]$InstallDir,
  [Parameter(Mandatory=$true)][string]$StageDir,
  [Parameter(Mandatory=$true)][string]$WorkDir,
  [Parameter(Mandatory=$true)][string]$BackupDir,
  [Parameter(Mandatory=$true)][string]$StatusFile
)
$ErrorActionPreference = 'Stop'
function Report([string]$status) {
  $timestamp = (Get-Date).ToString('o')
  [IO.File]::WriteAllText($StatusFile, "$timestamp $status")
}
try {
  # The UI must exit before an executable or Python DLL can be renamed.
  $gone = $false
  for ($i=0; $i -lt 600; $i++) {
    if (-not (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue)) {
      $gone = $true
      break
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $gone) { throw "App did not close within five minutes; update not applied" }
  if (-not (Test-Path -LiteralPath (Join-Path $StageDir 'Xbox360Recomp.exe') -PathType Leaf)) {
    throw "Staged Windows executable is missing"
  }
  if (-not (Test-Path -LiteralPath (Join-Path $InstallDir 'Xbox360Recomp.exe') -PathType Leaf)) {
    throw "Previous application executable is missing"
  }
  if (Test-Path -LiteralPath $BackupDir) { throw "Backup directory already exists" }

  [IO.Directory]::Move($InstallDir, $BackupDir)
  try {
    [IO.Directory]::Move($StageDir, $InstallDir)
  } catch {
    if (-not (Test-Path -LiteralPath $InstallDir)) {
      [IO.Directory]::Move($BackupDir, $InstallDir)
    }
    throw
  }

  Report "Updated installation; launching"
  try {
    Start-Process -FilePath (Join-Path $InstallDir 'Xbox360Recomp.exe') -WorkingDirectory $InstallDir
  } catch {
    # Startup launch failed. Put the old usable portable directory back.
    $failedDir = "$InstallDir.failed"
    if (-not (Test-Path -LiteralPath $failedDir)) {
      [IO.Directory]::Move($InstallDir, $failedDir)
      [IO.Directory]::Move($BackupDir, $InstallDir)
    }
    throw
  }
  # Cleanup failure does not roll back an already started working program.
  try { Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction Stop } catch {}
  try { Remove-Item -LiteralPath $WorkDir -Recurse -Force -ErrorAction Stop } catch {}
  Report "Update installed and relaunched"
} catch {
  # A failed rename must not leave an installation missing.
  try {
    if (-not (Test-Path -LiteralPath $InstallDir) -and
        (Test-Path -LiteralPath $BackupDir)) {
      [IO.Directory]::Move($BackupDir, $InstallDir)
    }
  } catch {}
  Report "Update failed: $($_.Exception.Message)"
  exit 1
}
'''


def extract_verified_windows_package(package: Path, target: Path) -> None:
    """Strictly unpack the official portable ZIP to an empty staging folder.

    All entries must be below Xbox360Recomp/. Block traversal, case-fold
    collisions, Windows drive/ADS names, symlinks and excessively large files.
    """
    package = Path(package)
    target = Path(target)
    if target.exists():
        raise ValueError("Staging target already exists")
    target.mkdir(parents=True)
    seen = set()
    total_size = 0
    try:
        with zipfile.ZipFile(package) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > 30000:
                raise ValueError("Unexpected Windows package file count")
            for entry in infos:
                name = entry.filename
                if not name or "\\" in name or "\x00" in name or name.startswith("/"):
                    raise ValueError("Unsafe path in Windows package")
                components = name.rstrip("/").split("/")
                if (components[0] != "Xbox360Recomp" or
                    any(c in ("", ".", "..") or ":" in c or c.endswith((" ", ".")) for c in components)):
                    raise ValueError("Unsafe Windows package entry: " + name)
                if len(components) == 1:
                    if not entry.is_dir():
                        raise ValueError("Package root is not a directory")
                    continue
                relative = components[1:]
                key = "/".join(relative).casefold()
                if key in seen:
                    raise ValueError("Duplicate or case-colliding Windows update entry")
                seen.add(key)
                file_type = (entry.external_attr >> 16) & 0o170000
                if file_type == stat.S_IFLNK:
                    raise ValueError("Symlink in update package")
                if entry.file_size > 512 * 1024**2:
                    raise ValueError("Oversized file in Windows update")
                total_size += entry.file_size
                if total_size > 2 * 1024**3:
                    raise ValueError("Oversized extracted Windows update")
                dest = target.joinpath(*relative)
                if entry.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as reader, dest.open("xb") as writer:
                        shutil.copyfileobj(reader, writer, length=1024 * 1024)
        for rel in REQUIRED_PORTABLE_FILES:
            if not (target / rel).is_file():
                raise ValueError("Windows update is missing " + rel)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


def prepare_windows_install(info: dict, install_dir: Path, *, current_version: str) -> tuple[Path, Path, Path]:
    """Download a newer official release and stage it alongside the app.

    No writes to the active installation happen in this function. Caller
    must separately launch the exit-aware helper with explicit consent.
    """
    if os.name != "nt":
        raise RuntimeError("Automatic portable replacement is only available on Windows.")
    if info.get("current", True):
        raise ValueError("Already on the latest release")
    if info.get("asset", {}).get("name") != "Xbox360Recomp-Windows-x64.zip":
        raise ValueError("This release does not have a Windows portable package")
    install = Path(install_dir).resolve(strict=True)
    if install.is_symlink() or not (install / "Xbox360Recomp.exe").is_file():
        raise ValueError("Select the unpacked Xbox360Recomp application folder, not a game project")
    # A write test catches Program Files / protected locations before download.
    with tempfile.NamedTemporaryFile(prefix=".xbo360-check-", dir=install.parent) as probe:
        pass
    workspace = Path(tempfile.mkdtemp(prefix=".xbo360-update-", dir=install.parent))
    stage = workspace / "Xbox360Recomp"
    backup = install.with_name(f".{install.name}-backup-{uuid.uuid4().hex}")
    try:
        package = download(info, workspace)
        extract_verified_windows_package(package, stage)
        return workspace, stage, backup
    except BaseException:
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def launch_windows_swap(install_dir: Path, workspace: Path, stage: Path,
                        backup: Path, *, parent_pid: int) -> Path:
    """Launch a detached PowerShell helper, then let the GUI close normally."""
    if os.name != "nt":
        raise RuntimeError("The self-updater is Windows-only")
    if not 1 <= parent_pid <= 0x7FFFFFFF:
        raise ValueError("Invalid parent process ID")
    install_dir = Path(install_dir).resolve(strict=True)
    workspace = Path(workspace).resolve(strict=True)
    stage = Path(stage).resolve(strict=True)
    backup = Path(backup).absolute()
    if stage.parent != workspace or workspace.parent != install_dir.parent or backup.parent != install_dir.parent:
        raise ValueError("Update stages are not beside the application folder")
    if not (stage / "Xbox360Recomp.exe").is_file():
        raise ValueError("Staged executable does not exist")
    status_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Xbox360Recomp"
    status_dir.mkdir(parents=True, exist_ok=True)
    status = status_dir / "last-update-status.txt"
    fd, helper_path = tempfile.mkstemp(prefix="xbo360-update-", suffix=".ps1")
    helper = Path(helper_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as output:
            output.write(_WINDOWS_SWAP_SCRIPT)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-WindowStyle", "Hidden", "-File", str(helper),
             "-ParentPid", str(parent_pid), "-InstallDir", str(install_dir),
             "-StageDir", str(stage), "-WorkDir", str(workspace),
             "-BackupDir", str(backup), "-StatusFile", str(status)],
            cwd=str(install_dir.parent), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
            close_fds=True,
        )
        return status
    except BaseException:
        helper.unlink(missing_ok=True)
        raise
