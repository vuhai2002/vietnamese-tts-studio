# Phase 1: Refactor run.py -> tts_engine.py (CLI regression-safe)

## Context Links

- Source being refactored: `D:\source-code\omnivoice-vietnamese\run.py` (87 lines)
- Project constraints: `D:\source-code\omnivoice-vietnamese\CLAUDE.md`
- Overview: [plan.md](plan.md)

## Overview

- **Priority:** P1 (foundation - Phases 3-6 import this module)
- **Status:** pending
- **Description:** Extract all model lifecycle + generation logic out of `run.py` into a reusable
  `tts_engine.py` module. `run.py` becomes a thin CLI that calls the engine. The CLI's args,
  defaults, stdout messages, and output behavior stay 100% backward compatible.

## Key Insights

- The single most fragile thing in this project is the **HF_HOME ordering**: it MUST be set before
  `omnivoice` / `huggingface_hub` is imported, or weights leak to `C:\Users\...\.cache`. Today that
  lives at the top of `run.py` (lines 16-19). After refactor, whoever imports omnivoice FIRST must
  have already set HF_HOME. Since both `run.py` and `app.py` will `import tts_engine` before they
  ever touch omnivoice, the safe home for this code is the **top of `tts_engine.py`** (module-level,
  runs on import, before the `from omnivoice import OmniVoice` line in that same module).
- The engine must support what the UI needs that the CLI never did: **unload** (free VRAM) and
  **device switch** (CPU checkbox toggled). The CLI only ever loads once and exits, so these are new.
- Preserve the `TypeError` fallback for `num_step` (run.py:74-77) - it is a defensive shim for omnivoice
  version drift and must survive into the engine's generate wrapper.

## Requirements

### Functional
- `tts_engine.py` exposes a small, stable API (suggested):
  - module constants: `MODEL_ID`, `SAMPLE_RATE`, `DEFAULT_TEXT`, `PROJECT_DIR`, `OUTPUTS_DIR`, `REFS_DIR`
  - `pick_device(force_cpu: bool) -> tuple[str, torch.dtype]` -> (`"cuda:0"`/`"cpu"`, float16/float32)
  - a `TtsEngine` class (or module-level singleton) with:
    - `ensure_loaded(device: str, dtype) -> None` - lazy load; if already loaded on a DIFFERENT device, unload then reload
    - `generate_one(text, ref_audio=None, ref_text=None, steps=16) -> np.ndarray` - returns the 1-D audio array (i.e. `audio[0]`), NOT the batch
    - `unload() -> None` - `del self.model; self.model=None; gc.collect(); torch.cuda.empty_cache()` (guard cuda call when on CPU / no cuda)
    - `is_loaded -> bool`, `current_device -> str | None`
- `run.py` reproduces today's behavior using the engine:
  - same argparse flags: `--text --out --ref --ref-text --steps --cpu` with identical defaults/help
  - same stdout lines (device/dtype, cache path, loading, generating, OK saved)
  - writes via `sf.write(out_path, audio, SAMPLE_RATE)` where `audio` is the 1-D array from the engine

### Non-functional
- `tts_engine.py` < 200 lines; `run.py` < 80 lines after slimming.
- No behavior change observable from the CLI (regression).
- UTF-8 stdout reconfigure preserved (move into a tiny helper or keep in both entrypoints; engine import must not crash on import if stdout reconfigure fails).

## Architecture

Data flow (CLI path):
```
run.py main()
  -> args = parse()
  -> device,dtype = tts_engine.pick_device(args.cpu)
  -> engine.ensure_loaded(device, dtype)        # lazy, prints loading line
  -> audio = engine.generate_one(text=args.text, ref_audio=args.ref,
                                 ref_text=args.ref_text, steps=args.steps)
  -> sf.write(args.out, audio, SAMPLE_RATE)
```

Import ordering inside `tts_engine.py` (TOP OF FILE, in this order):
```
import os, sys, gc
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_DIR / ".cache" / "huggingface"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(CACHE_DIR))   # <-- BEFORE omnivoice import
# only now:
import torch
from omnivoice import OmniVoice
```

Device-switch logic in `ensure_loaded`:
```
if self.model is not None and self.current_device != device:
    self.unload()            # free VRAM before loading on the new device
if self.model is None:
    self.model = OmniVoice.from_pretrained(MODEL_ID, device_map=device, dtype=dtype)
    self.current_device = device
```

Generate wrapper (keep the fallback):
```
kwargs = {"text": text, "num_step": steps}
if ref_audio: kwargs["ref_audio"] = ref_audio
if ref_text:  kwargs["ref_text"]  = ref_text
try:
    audio = self.model.generate(**kwargs)
except TypeError:
    kwargs.pop("num_step", None)
    audio = self.model.generate(**kwargs)
return audio[0]
```

## Related Code Files

- **Create:** `D:\source-code\omnivoice-vietnamese\tts_engine.py`
- **Modify:** `D:\source-code\omnivoice-vietnamese\run.py` (slim to CLI-over-engine)
- **Delete:** none

## Implementation Steps

1. Create `tts_engine.py`. Put the HF_HOME block + UTF-8 reconfigure at the very top, then torch /
   omnivoice imports (mirror run.py:14-30 exactly so cache behavior is byte-identical).
2. Add module constants (`MODEL_ID`, `SAMPLE_RATE`, `DEFAULT_TEXT`, dirs).
3. Implement `pick_device(force_cpu)`.
4. Implement `TtsEngine` with `ensure_loaded`, `generate_one`, `unload`, `is_loaded`, `current_device`.
   Make `unload()` safe to call when nothing is loaded and when on CPU (guard `torch.cuda.empty_cache()`
   behind `torch.cuda.is_available()`).
5. Provide a module-level singleton `engine = TtsEngine()` for app.py + run.py to share.
6. Rewrite `run.py` to import `tts_engine`, parse args, call the engine, write the file - preserving
   every stdout line and the `--out` parent-dir mkdir.
7. Compile-check both files: `uv run python -c "import tts_engine; import run"` (no execution side effects).

## Todo List

- [ ] `tts_engine.py` created with HF_HOME set before omnivoice import
- [ ] Module constants + `pick_device` implemented
- [ ] `TtsEngine.ensure_loaded` lazy-loads and reloads on device change
- [ ] `generate_one` returns 1-D array and keeps the `num_step` TypeError fallback
- [ ] `unload` frees VRAM safely (cuda guard, gc.collect)
- [ ] Shared singleton `engine` exported
- [ ] `run.py` slimmed to CLI-over-engine, all flags/defaults/help unchanged
- [ ] Both files compile (`uv run python -c "import tts_engine, run"`)
- [ ] Both files < 200 lines (run.py < 80)

## Success Criteria

- CLI regression: these produce the same outcome as before the refactor -
  - `uv run python run.py --text "Xin chào." --out outputs/_reg1.wav` -> valid 24000 Hz wav
  - `uv run python run.py --text "..." --cpu --out outputs/_reg2.wav` -> runs on CPU
  - `--ref` + `--ref-text` path passes both kwargs through
- `python -c "import tts_engine"` does NOT create `C:\Users\...\.cache\huggingface` (cache stays in project).
- No omnivoice import happens before HF_HOME is set (verify by reading import order).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| HF_HOME set after omnivoice import (cache leaks to C:) | Med | High | HF_HOME block is the FIRST executable code in tts_engine.py; both entrypoints import tts_engine before omnivoice. Verify by reading final file top-to-bottom. |
| Device switch leaves stale model in VRAM (4GB tight) | Med | High | `ensure_loaded` calls `unload()` before reloading on a new device; `unload` does del + empty_cache + gc. |
| Slimmed run.py changes a stdout line / default -> silent regression | Low | Med | Diff stdout lines against current run.py; keep DEFAULT_TEXT and all help strings verbatim. |
| `torch.cuda.empty_cache()` called on CPU-only run -> error | Low | Low | Guard behind `torch.cuda.is_available()`. |

## Security Considerations

- None new. No network beyond HF weight download (unchanged). No user-facing surface in this phase.

## Next Steps

- Unblocks Phase 3 (app.py imports `tts_engine.engine`).
- Phase 2 is independent and can proceed in parallel.
