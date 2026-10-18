# Analysis finding: Rise of the Tomb Raider (Xbox 360)

This note contains **no game executable, assets, proprietary source code or keys**. It documents the metadata and the single control-flow issue observed while reviewing one user-provided XEX. It does not claim commercial-game compatibility.

## Exact XEX fingerprint

- Title ID: `53510823`
- Media ID: `2427ED57`
- Version: `0.0.0.6`
- XEX2 file size: 16,531,456 bytes
- SHA-256: `9f718cac4cc7fb33ec7204e90d0901387f81e18c953eb1f90c40be5e2e3ff021`
- XEX is encrypted with BASIC compression. The analyst reconstructed the executable image and examined PDATA and PowerPC instructions without redistributing it.

## Finding and rationale

The codegen log reported `UnresolvedCall 0x82C21240 from 0x82C22B14`. Direct PPC branch `b` from `0x82C22B14` targets `0x82C21240`, following an `addi` at `0x82C22B10`; the source lies outside the prior PDATA function. The target is an apparent leaf-function entry not present in PDATA:

- Previous registered PDATA function: `0x82C21110` through `0x82C21240` (exclusive).
- Unregistered function starts: `0x82C21240`.
- Last instruction `0x82C212AC`: `blr`.
- Next registered PDATA function starts: `0x82C212B0`.
- Evidenced extent: `0x82C21240..0x82C212B0`, **0x70 = 112 bytes**.

This boundary is independently supported by return/control-flow and PDATA adjacency. It is not an arbitrary guess; nevertheless, ReXGlue codegen and gameplay have **not been retested successfully** after adding the hint.

## Apply to an existing prepared project

In desktop **Library → Function hints → Check verified hints for this XEX**, only the exact SHA-256 match exposes the evidence-backed 112-byte suggestion. Choose **Use verified hint**, explicitly save the boundary, then retry **Generate C++** with **Force disabled**. The verification occurs on the PC and no game data is uploaded.

Equivalent CLI:

```powershell
python xbo360.py suggest-hints "D:\Ports\my_game"
python xbo360.py function-hint "D:\Ports\my_game" --address 0x82C21240 --size 112
python xbo360.py codegen "D:\Ports\my_game"
```

This writes `xbo360-function-hints.toml` and includes it from `[entrypoint].includes`. Do not delete or reinitialize the existing project. Alternatively, with ReXGlue 0.10.0, insert the TOML below at the end of the manifest:

```toml
[entrypoint.functions]
"0x82C21240" = { size = 112 }
```

Do not use both mechanisms for the same function address at the same time. If subsequent errors appear, preserve the updated build log; missing function boundaries can occur more than once. Force is diagnostic and does not fix codegen or runtime behavior.


## Runtime boot investigation (2026-10-18)

The user successfully built the Windows host and reached Direct3D 12 device setup and
guest function-table initialization before a black screen and crash.
The runtime log `my_game_001.log` reports three independent issue families:

- **Fatal guest dispatch:** `Call to invalid or unregistered function at guest address 0x823E7730`.
  The ReXGlue 0.10.0 dispatcher only accepts entries present in its hash table;
  an unrecognized indirect call is fatal, not evidence that the target is invalid machine code.
- **Guest physical heap allocation errors:** `BaseHeap::Alloc invalid requested range`,
  `BaseHeap::Alloc failed to find contiguous range` and
  `PhysicalHeap::Alloc unable to alloc physical memory in parent heap`.
  These messages do not expose allocation sizes, alignment or requested ranges;
  **do not claim** they prove insufficient host RAM.
- **Unresolved guest paths:** `d:\\LAYER1.000`, `d:\\LAYER1.DAT`,
  `d:\\PATCH1.000.tiger` and `UPDATE:\\TITLEUPDATE.000.tiger`.
  `D:\\` maps to the selected `game_root` on the host. Missing UPDATE:
  content can be optional; verify assets before assuming their absence caused the crash.

### Newly recovered missing vtable methods

We re-examined the **same exact encrypted BASIC XEX** identified by the SHA-256
above, reconstructed the in-memory PE image locally, examined PDATA entries and
confirmed guest-code addresses are stored as big-endian function pointers in
the original PE data region. No XEX bytes, keys, ROMs or derived proprietary
source code are published.

| Guest address | Exact size | Evidence |
|---|---:|---|
| `0x823E7708` | 40 bytes (`0x28`) | pointer stored at `0x82003260`, `bctr` at `0x823E772C`, next entry at `0x823E7730` |
| `0x823E7730` | 40 bytes (`0x28`) | pointer at `0x82003264`; exact runtime FATAL target; `bctr` at `0x823E7754` |
| `0x823E7758` | 44 bytes (`0x2C`) | pointer at `0x82003268`; `blr` at `0x823E7780`, 4-byte padding after |
| `0x823E7B78` | 8 bytes (`0x08`) | pointer at `0x82003274`; `blr` at `0x823E7B7C`, next PDATA entry `0x823E7B80` |

These are all outside named function entries in the XEX PDATA; the previous
PDATA function begins at `0x823E7698` and the next at `0x823E7788`.
Each size is inferred from **verified instruction boundaries and stored code
pointers**, not blindly from a numeric gap. Their inclusion in ReXGlue
codegen has not yet been demonstrated to fix this game's boot.

### Manual codegen experiment

Use the desktop Library's Function hints panel after verifying the exact
XEX checksum; each hint requires explicit selection and saving. Alternatively,
add to the existing `[entrypoint.functions]` section of your generated
manifest (do not repeat the header if already present):

```toml
"0x823E7708" = { size = 40 }
"0x823E7730" = { size = 40 }
"0x823E7758" = { size = 44 }
"0x823E7B78" = { size = 8 }
```

Keep the prior `0x82C21240 = { size = 112 }` hint. Re-run ReXGlue
codegen and native build **without Force**, then launch with the full
original extracted game directory.

For separate log inspection:

```powershell
python xbo360.py diagnose-runtime "C:\\Path\\To\\my_game_001.log" --project "C:\\Path\\To\\artifacts"
```

Confirm missing `D:\\` asset filenames exist directly under the
chosen game root. Do not fabricate dummy files for unknown updates or bypass
memory allocation failures. No functionality, frame rate, or gameplay
compatibility is guaranteed from these hints; further failures should be
debugged independently.
