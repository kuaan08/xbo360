# Experimental diagnostics, no-RTTI discovery and Vulkan

These are developer features. A native codegen/build success does not
establish that a commercial Xbox 360 game will run or render. No game
executables or assets are distributed with the application.

## Research references

- ReXGlue SDK 0.10.0: https://github.com/rexglue/rexglue-sdk
- ReXGlue codegen stages: https://github.com/rexglue/rexglue-sdk/wiki/Codegen-Pipeline-Overview
- Xenia Xbox 360 emulation: https://github.com/xenia-project/xenia
- Xenon Recomp AOT pipeline: https://github.com/nimauria/Xenon-Recomp

ReXGlue's VTableScanner traverses MSVC RTTI Complete Object Locators.
Tables without recognized RTTI may be missed. Its general function-pointer
scan is currently disabled upstream because of false positives. A pointer
run can be a switch/jump table, not necessarily a set of callable methods.

## Safer no-RTTI function discovery groundwork

The exact-XEX evidence catalogue includes manually verified PowerPC
functions and rejects duplicate entries when the main TOML already
contains an address. Functions are never added automatically.

ppc_pointer_tables.py is a separate conservative scanner that takes
an ALREADY DECODED MAPPED PE image plus independently verified guest
code/data address intervals. It reports runs of big-endian code pointers,
with their data addresses and evidence, but does not infer function sizes,
patch any file, or register calls with ReXGlue. A raw encrypted/compressed
XEX is not an acceptable input.

Example (ranges are only illustrative, confirm actual PE sections):

    python ppc_pointer_tables.py mapped_image.bin --base 0x82000000 --code 0x82170000:0x82D0DB4C --data 0x82000000:0x82008000

Future integration requires tests that distinguish RTTI-less vtables from
jump tables and uses CFG/PDATA before assigning callable boundaries.

## Experimental Bug Assistant

The Library > Analyze bugs action and Assistant tab read saved build
and recent runtime logs without changing games. They distinguish:
- unregistered guest PowerPC call targets (fatal);
- guest physical heap errors (possible range/alignment/fragmentation);
- unavailable compiled Vulkan renderer;
- file lookup failures, including possibly optional UPDATE content;
- recent crash-target history.

Choose Copy safe summary to paste a short, path-free report into ChatGPT
or a GitHub issue. There is NO automatic external upload, network AI API,
game modification or self-repair. This is an offline deterministic
diagnostic assistant, not a generative AI model.

CLI:

    python xbo360.py bug-assistant "C:\Your\Project\artifacts"

The repeating physical-heap error does NOT prove host RAM exhaustion.
ReXGlue src/system/xmemory.cpp should record requested low/high range,
size, alignment, heap base/size, allocation flags and call origin before
modifying the allocator.

## Vulkan for Windows: real source build, experimental runtime

The release-bundled ReXGlue SDK 0.10.0 remains Direct3D 12-only.
The Settings button Build experimental Vulkan + DX12 SDK from pinned
source invokes a separate SOURCE build, with explicit confirmation.

It clones the official ReXGlue v0.10.0 commit:
f5337cdc947ff6d4c4196737e2c807a48f2a1fc2
including submodules, and configures:
- REXGLUE_USE_VULKAN=ON
- REXGLUE_USE_D3D12=ON

Then it compiles a Release SDK, installs it under:
%LOCALAPPDATA%\Xbox360Recomp\sdk-vulkan\0.10.0\install
and checks BOTH backend flags plus the rexgpu-xenos DLL. On success
the UI selects this separate SDK prefix. Rebuild each project with
the custom SDK and then choose Vulkan in Game settings. Do not use
the original bundled SDK for Vulkan.

Direct CLI:

    python xbo360.py build-vulkan-sdk --yes --jobs 4

Requires Windows C++ Build Tools, Windows SDK, Clang, Git, CMake and Ninja.
This command downloads the full SDK source; it never silently replaces
the bundled SDK. Building the plugin is NOT proof of a Vulkan device
initializing, graphical correctness, or retail game compatibility.
Experimental Vulkan compilation is checked independently by the
Experimental Vulkan SDK GitHub Actions workflow.

## Frontend and limitations

The UI gained an Assistant tab, per-project Analyze bugs action,
resizable sidebar, safer function-hint saves, and reduced-motion option.
The codegen, game runtime and game data remain separate. Future work
should implement a full, confidence-scored no-RTTI scanning pass inside
ReXGlue and investigate guest memory allocation arithmetic separately,
without guessing function lengths or falsely reporting full game support.
