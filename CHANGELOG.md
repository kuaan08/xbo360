# Changelog

## 0.3.4

- Fix Windows CMake configuration reporting `CMAKE_MAKE_PROGRAM is not set` even when Ninja is installed but not visible to the process after Visual Studio environment initialization.
- Find Ninja across PATH, Visual Studio's CMake/Ninja bundle, installed CMake and WinGet links; verify `ninja --version` actually runs before accepting it.
- Pass the validated absolute Ninja executable path to CMake with `-DCMAKE_MAKE_PROGRAM:FILEPATH=...` and retain `CMAKE_SUPPRESS_REGENERATION=ON` to prevent the previous 100-regeneration loop.
- Explain the official Ninja installation command when no working executable is found, before running the expensive game codegen phase.
- Extend desktop toolchain diagnostics and regression tests for Ninja aliases and paths with spaces.

## 0.3.3

- Fix repeated `[0/N] Re-running CMake...` followed by Ninja `manifest 'build.ninja' still dirty after 100 tries` on Windows projects. Each workbench build already invokes ReXGlue codegen and CMake configure explicitly, so the wrapper now configures Ninja with `CMAKE_SUPPRESS_REGENERATION=ON`, avoiding unnecessary build-time regeneration.
- Add automated CMake/Ninja regression coverage with a future-dated CMake source file. The test checks that a build.ninja regeneration rule is not generated.
- Preserve existing source manifests, generated PowerPC-to-C++ files, and original game assets. No removal of project or Ninja build directories is needed for the fix.
- Note that native compilation and commercial game compatibility remain unverified for Rise of the Tomb Raider.

## 0.3.2

- Diagnose MSVC/Windows SDK linker setup before generating C++ or running CMake, avoiding misleading `kernel32.lib` / `msvcrtd.lib` CMake failures.
- Load the Visual Studio `vcvars64.bat` environment when available, including Windows SDK and VC library paths, or preserve an already initialized developer shell.
- Verify the actual library files referenced by the `LIB` environment variable; Clang, CMake and Ninja alone no longer imply a ready Windows toolchain.
- Include missing library names and setup guidance in the desktop setup window and the command-line doctor.
- Add a regression test for Windows SDK and MSVC library lookup.
- Keep existing prepared projects and manually verified ReXGlue function hints unchanged.


## 0.3.1

- Inspect a supplied Rise of the Tomb Raider XEX and confirm a missing PowerPC leaf function at `0x82C21240` with a 112-byte extent, based on disassembly and adjacent PDATA entries.
- Show checksum-matched known hints in **Library → Function hints**, requiring explicit user selection and save; other revisions receive no suggested size.
- Add the read-only `suggest-hints` CLI and test that it never mutates the XEX or project and refuses nonmatching checksums.
- Document the evidence and test procedure; gameplay compatibility remains unconfirmed.


## 0.3.0

- Add a persistent, opt-in Force checkbox in the Recompile page and Settings. It reaches the desktop codegen process via the real ReXGlue global `--force` flag; ordinary builds still validate normally.
- Identify `UnresolvedCall` branches in existing project logs, including original source and target addresses. A branch alone does not prove a function boundary.
- Add **Library → Function hints** for reviewed function addresses and explicit sizes in bytes, plus an optional parent for a discontiguous code chunk.
- Write manual hints to `xbo360-function-hints.toml` and include it in the project manifest, without rewriting original XEX or assets.
- Add `diagnose` and `function-hint` CLI commands, regression tests and safety warnings. No commercial-game compatibility is implied.


## 0.2.0

- Restore the original-style Recompile/Library/About interface, fixed form, result card, console, status bar, recent inputs and drag/drop.
- Detect missing prerequisites at startup and ask before starting official Visual Studio/Clang/CMake/Ninja/Git/Java installers; automatically load the Visual Studio environment for builds.
- Add XDVDFS XISO/XGD1/2/3 inspection/extraction and folder input.
- Add explicit verified Android SDK/NDK/JDK setup, Android library/menu APK and experimental per-title ARM64 export using a separately pinned Android runtime and matching codegen.
- Validate imported Android executables against the compiled title and start matching imports automatically.
- Add per-game launch settings and official release checks with digest-verified Windows downloads.
- Expand tests, packaging checks, native Android fixture validation and technical documentation.

## 0.1.0

- Adapt SwitchRecomp frontend foundations to an Xbox 360 PC recompilation workbench.
- Add XEX2 header inspection, ReXGlue 0.10.0 installation with pinned hashes, project initialization, codegen, CMake build and launch commands.
- Preserve host path casing, select the requested XEX at runtime, and stage/configure the Xenos plugin.
- Add persistent project list, streaming logs, cancellation and toolchain checks.
- Add tests and Windows portable artifact workflow. Commercial-game compatibility remains unvalidated.
