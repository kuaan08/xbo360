# Changelog

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
