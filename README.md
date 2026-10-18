# Xbox 360 Recomp

Xbox 360 Recomp adapts the desktop workflow of [SwitchRecompz](https://github.com/kuaan08/Switchrecompz) to Xbox 360 static recompilation through [ReXGlue](https://github.com/rexglue/rexglue-sdk). It prepares per-title C++ projects, invokes PowerPC analysis/code generation, builds native PC executables, and launches completed builds.

**Status: experimental workbench, version 0.1.0.** Project initialization has been tested against the official ReXGlue 0.10.0 binary. This repository has no validated commercial-game compatibility list. Building a title successfully does not establish that it boots, renders correctly, or is playable.

This project recompiles **Xbox 360 software for a Windows/Linux PC**. It does not convert Nintendo Switch games into Xbox 360 games and does not generate executables for Xbox 360 hardware.

## Download and start

The [Actions page](https://github.com/kuaan08/xbo360/actions/workflows/ci.yml) produces `Xbox360Recomp-Windows-x64.zip` after successful checks. Download the artifact from a successful run and extract the entire directory. The portable package includes the desktop frontend, Python, and the pinned ReXGlue SDK.

To compile generated projects on Windows, install Visual Studio 2022 with Desktop development with C++, the Windows SDK, Clang 20 or newer, CMake 3.25 or newer, and Ninja. Launch `Xbox360Recomp.exe` from an **x64 Native Tools Command Prompt for VS 2022** so the compiler can find Windows headers and libraries. The package does not install Visual Studio.

For source usage, Python 3.11 or newer is required. Run:

```powershell
python xbo360.py install-sdk
python xbo360.py doctor
```

The SDK installer downloads the exact 0.10.0 release asset, validates its SHA-256, checks `rexglue --version`, and installs it into an application cache. Downloads are explicit; opening the frontend does not download tools.

## Desktop workflow

1. Open **Settings** and check the toolchain. Select an SDK prefix if using your own installation.
2. Open **New project**, choose an extracted `.xex`, and optionally specify the root directory containing that executable and its assets.
3. Choose an empty project directory separate from the assets, then enter a lowercase name such as `my_game`.
4. Use **Prepare project** to create editable C++/TOML files, or **Recompile + build** to run the whole pipeline.
5. Under **Projects**, regenerate C++, resume a build, inspect the output directory, or launch a successfully built executable.

The log view streams real child-process output. `build.log` retains the full output in each project, including output removed from the bounded UI log. Cancel stops the Python process and its compiler process tree. Settings and the project list persist between sessions.

## Command line

```powershell
python xbo360.py inspect "D:\MyGame\Default.xex"
python xbo360.py prepare "D:\MyGame\Default.xex" --project "D:\Ports\my_game" --name my_game
python xbo360.py codegen "D:\Ports\my_game"
python xbo360.py build "D:\Ports\my_game" --jobs 8
python xbo360.py run "D:\Ports\my_game" --renderer d3d12
```

For a single invocation:

```powershell
python xbo360.py recompile "D:\MyGame\Default.xex" --project "D:\Ports\my_game" --name my_game
```

`recompile --generate-only` stops after C++ generation. `--sdk PATH` selects a ReXGlue **installation prefix** containing `bin/rexglue.exe`, `include/`, and `lib/`, rather than a source checkout. `prepare --no-scan-dll` disables discovery of guest DLL modules. `build --configuration Debug` and `RelWithDebInfo` are also available.

On Linux x64, use `python3`, Clang/Clang++ 20, CMake, and Ninja. The frontend can be built with `cargo build --release --manifest-path gui/Cargo.toml`; keep the resulting binary with `xbo360.py`, or start it from this repository. The installed SDK must be compatible with the host system's C++ runtime.

## How it works

| Stage | Implementation | Result |
| --- | --- | --- |
| Input inspection | Python reads the big-endian XEX2 header and validates structural bounds | Basic metadata and early rejection of incorrect input |
| Project initialization | Official `rexglue init --project-name ... --xex-path ...` | CMake project, application subclass, and TOML manifest |
| Path correction | Wrapper restores host path casing in the generated manifest | Mixed-case asset paths remain usable on Linux |
| CPU recompilation | Official `rexglue codegen <manifest>` | PowerPC/Xenon instructions translated to C++ ahead of time |
| Native compilation | CMake/Ninja/Clang using the SDK's platform presets | Host executable and SDK runtime dependencies |
| Launch | SDK `ReXApp`, Xenos plugin, and original game data directory | Runtime execution of the per-title native build |

The frontend reuses the Rust/egui styling, procedural icon foundation, and background-process/log machinery from SwitchRecomp by MZ Labs. The Xbox 360 project pages, settings, SDK integration, manifest handling, and build orchestration are specific to this adaptation.

The Switch ARM64 translator, Horizon services, Maxwell GPU implementation, Nintendo package importer, keys settings, GCC/TCC pipeline, and Android builder are not part of this Xbox 360 pipeline. Those components describe different hardware and operating-system interfaces and cannot provide Xbox 360 compatibility through a rename.

ReXGlue supplies the PowerPC translator and the runtime for memory, kernel calls, threading, filesystem, audio, input, and graphics integration. Its Xenos plugin builds on Xenia research. These are upstream implementations, not subsystems newly implemented by this fork.

## Graphics and runtime

Generated targets explicitly request `GPU_PLUGINS xenos` so the runtime-loaded GPU plugin is staged beside the executable. The generated app loads the chosen input XEX, including its relative path, instead of assuming `default.xex`.

Renderer choices are Automatic, Direct3D 12 on Windows, and Vulkan. The adaptation registers an `xbo_renderer` runtime variable and passes its value to `LoadGpuPlugin("xenos", backend)`. Availability depends on the actual SDK plugin; requesting an unavailable backend fails rather than silently selecting another one. The workbench does not implement a new D3D12 or Vulkan backend.

Game assets remain in their original directory. The launcher supplies `--game_data_root` and starts the executable from its build directory. Linux launches include the selected SDK's `lib/` in `LD_LIBRARY_PATH`. Compiled outputs are development builds associated with a project and SDK installation, not standalone game distribution packages.

## Generated project layout

```text
my_game/
  xbo360-project.json
  my_game_manifest.toml
  CMakeLists.txt
  CMakePresets.json
  build.log
  src/
  generated/
  out/build/<platform>-<configuration>/
```

Edit the manifest for analysis settings and function boundaries. Add title-specific hooks and replacements under `src/`. Resume with `codegen` and `build`; initialization refuses to overwrite a non-empty directory. A failed codegen/build clears the recorded executable so an older executable is not offered as a new successful build.

## Limitations

- Input is an extracted XEX2 file. ISO, GOD/STFS, marketplace package extraction, updates and multi-disc management are not implemented.
- Automatic analysis can fail on indirect control flow, missing function boundaries, imports, or exception metadata. Title-specific reverse engineering may be necessary.
- SDK validation failures stop the pipeline. There is no automatic `--force` that conceals unresolved calls.
- The frontend is portable, but building native game projects requires a compatible external C++ toolchain.
- Android, UWP, Xbox One/Series, and Xbox 360 console outputs are not implemented.
- No claim of commercial-game boot, gameplay performance, graphics accuracy, or universal compatibility has been established by the tests.

## Development and verification

```bash
python3 -m unittest discover -s tests -v
cargo test --locked --manifest-path gui/Cargo.toml
```

Set `XBO360_TEST_SDK` to an installed SDK prefix to enable the real-SDK initialization and error-propagation test. It uses a synthetic XEX header created during the test, with no commercial data. This validates project integration and rejection of an incomplete executable; it is not a gameplay or successful full-recompilation test.

The CI checks Python on Windows/Linux, builds/tests the Rust frontend, checks the official SDK integration, and packages a Windows frontend. See [architecture and upstream decisions](docs/ARCHITECTURE.md) for the reviewed revisions and remaining work.

## Credits and license

**SwitchRecomp by MZ Labs** is the original frontend foundation, licensed under Apache-2.0. This adaptation was developed from `kuaan08/Switchrecompz` at `c33f097`; preserve [NOTICE.txt](NOTICE.txt) and [LICENSE.txt](LICENSE.txt).

Xbox 360 adaptation and fork additions: **katakishi0**. Repository hosting: **kuaan08**.

**ReXGlue by Tom Clay and contributors** is a separate BSD-3-Clause dependency. Credit also belongs to **Xenia**, **XenonRecomp by hedge-dev**, and **rexdex's recompiler**, as acknowledged upstream. The SDK and its dependencies retain their own licenses. See [THIRD_PARTY.md](THIRD_PARTY.md).
