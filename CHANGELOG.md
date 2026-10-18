# Changelog

## 0.3.9

- Fix frontend layout regression where the Recompile sidebar expanded over the build/codegen logs over time, leaving the user unable to read output.
- Move the full compilation console to a **separate Output tab**: it appears and opens automatically as soon as any command starts, including **Library → Generate C++ / Build / Export APK**. After completion, output remains readable until the user clears it; **Copy** and **Save...** remain available.
- Remove the log console from the Recompile split view while idle so it cannot be obscured by the form. Keep a clear **Open output** shortcut after a task has run.
- Allow manual drag-resizing of the Recompile form with a defined **300–430 px range** and a 370 px initial width. Prevent the Browse text fields from silently pushing the sidebar wider than the chosen value.
- Remove the log frame's dynamically growing minimum width, preserving a contained independently scrollable full-width console. No change to generated code, compilation flags, project manifests or saved logs.

## 0.3.8

- Fix **Android ARM64 per-game APK export on Windows** failing during matching host-codegen CMake configuration with `CMake was unable to find a build program corresponding to "Ninja"` / `CMAKE_MAKE_PROGRAM is not set`.
- Reuse the existing validated Ninja executable discovery (PATH, Visual Studio CMake tools and WinGet) for Android **host code generator and Android NDK** CMake configure calls. Pass an explicit absolute `-DCMAKE_MAKE_PROGRAM:FILEPATH=...` in both, including paths containing spaces.
- Suppress redundant Ninja regeneration loops; CMake is explicitly configured before building. Diagnose missing Ninja **before** updating large Android runtime submodules; recommend `Settings > Install Ninja` or `winget install --id Ninja-build.Ninja --exact` then restart the app.
- Add offline regression tests ensuring both CMake stages receive verified Ninja settings and broken/missing Ninja fails with a clear message.
- The host configuration error is addressed; successful ARM64 compilation and runtime boot for a retail Xbox 360 title still require device-specific testing, and other errors can surface later.

## 0.3.7

- Introduce the **Experimental Bug Assistant** in the Rust desktop frontend and an offline CLI. It scans recent per-game runtime logs and build metadata, classifies fatal PowerPC indirect calls, physical heap errors, missing guest assets, unavailable Vulkan, and crash history. All fixes remain manual and evidence-based; no personal logs or game files are transmitted to an AI service. Copyable summaries deliberately exclude full local paths.
- Improve the exact-XEX function hints for Rise of the Tomb Raider: include vetted additional PowerPC method addresses 0x82286388 (20 bytes) and 0x82286360 (40 bytes) based on reconstructed control flow; do not duplicate an address already present in the main manifest.
- Add a **conservative RTTI-independent pointer-table scanner prototype** for previously decoded mapped PE images. Big-endian code-pointer runs are only candidates; they are not blindly registered as functions, and encrypted XEX cannot be scanned as plaintext.
- Introduce **experimental Windows Vulkan + DirectX 12 SDK source builds**, pinned to the official ReXGlue v0.10.0 commit. Build all dependencies in a separate prefix from Settings with explicit consent, verify CMake flags and plugin files, and only select that SDK on build success. Add a separate Vulkan SDK CI workflow. The **bundled SDK remains D3D12-only** pending runtime validation; compilation does not establish playable games.
- Refresh UI with an Assistant tab, per-project Analyze bugs, resizable project form, reduced-motion preference, additional diagnostics, clearer limitations and safer handling of function hints.
- No claim is made that physical-heap failures or Rise of the Tomb Raider black-screen crashes are fixed by these changes. Vulkan rendering on Windows remains experimental until verified on a real GPU.

## 0.3.6

- Add an **in-app Windows portable updater**: check GitHub releases automatically on startup, show new-version notification, download a release directly inside the app, and install/restart with one click. No manual browser navigation, ZIP extraction or copying of application files.
- Add a separate, **opt-in unattended startup update** setting (automatically install/restart after a newer release is verified); enabled only on the user's choice. Automatic *checking* is enabled by default and can be disabled in Settings.
- Preserve installed settings at `%LOCALAPPDATA%\\Xbox360Recomp\\settings.json` and game projects outside the application directory. Automatically stage the package beside the portable app, verify its published SHA-256 digest and required contents, then swap installation directories only after the GUI exits.
- The detached Windows helper makes a same-volume installation backup and attempts rollback on failed directory moves. On disk-write or access problems, the user can check `%LOCALAPPDATA%\\Xbox360Recomp\\last-update-status.txt`. Installation to protected locations may require moving the portable folder to a user-writable directory.
- Harden update ZIP extraction against traversal, case collisions, symlinks, oversize files and missing runtime files. Add offline regression tests for release archive validation.
- Clarify graphics support: the **official ReXGlue 0.10.0 Windows SDK includes Direct3D 12 but excludes Vulkan by default**. Vulkan requires separately rebuilding the SDK and Xenos plugin with `REXGLUE_USE_VULKAN=ON`; it is **not** being falsely advertised as working in this Windows build.
- Current Rise of the Tomb Raider native runtime incompatibilities (guest physical heap and function dispatch) remain unresolved; auto-updating the frontend does not fix them by itself.

## 0.3.5

- Investigate an actual Windows native startup crash for the exact Rise of the Tomb Raider XEX (SHA-256 `9f718cac...e3ff021`), after successful codegen and native compilation. Direct3D 12 initialization succeeded but did not render gameplay.
- Confirm fatal unregistered guest target `0x823E7730` points to real PowerPC method code via the game's vtable. Add reviewed, exact-revision function hints at `0x823E7708` (40 B), `0x823E7730` (40 B), `0x823E7758` (44 B) and `0x823E7B78` (8 B). No changes to protected game binaries.
- Add `diagnose-runtime` command classifying guest-dispatch crashes, physical heap errors, missing D: assets and optional update paths; optionally check paths relative to the project's original `game_root`.
- Add runtime diagnosis and function-hint regression tests and check the game-root folder exists before launch. Preserve Force OFF and require explicit user approval before adding hints.
- Runtime physical heap behavior and full retail-game startup remain unverified; this is an evidence-backed diagnostic and experimental workaround, not a game-playability claim.

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
