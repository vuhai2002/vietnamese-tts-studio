# Phase 3: Install gradio + app.py basic TTS tab + start-ui.bat

## Context Links

- Engine API from Phase 1: `D:\source-code\omnivoice-vietnamese\tts_engine.py` (created in phase 1)
- Project constraints (install discipline, diacritics): `D:\source-code\omnivoice-vietnamese\CLAUDE.md`
- Overview: [plan.md](plan.md)

## Overview

- **Priority:** P1
- **Status:** pending (blocked by Phase 1)
- **Description:** Install Gradio into the bare `.venv`, then build the app skeleton + the
  "Tạo giọng nói" tab handling a SINGLE sentence (no chunking yet - that's Phase 4). Includes the
  giọng mẫu block (dropdown of refs/ + upload + microphone + lời mẫu), steps slider, "Dùng CPU"
  checkbox, "Đọc" button, inline audio output, and a "Giải phóng VRAM" button. Ship `start-ui.bat`.

## Key Insights

- **No pyproject.toml / uv.lock** in this project - deps live bare in `.venv`. Install Gradio the same
  way everything else was installed, with the cross-filesystem copy flag:
  `UV_LINK_MODE=copy uv pip install "gradio==6.16.0"`. Do NOT add a pyproject.toml (would change the
  project's dependency model; flagged as a separate user decision, not in scope here).
- Pin **gradio==6.16.0** (verified latest stable 2026-06-03, Python 3.12 supported).
- `gr.Audio(sources=["upload","microphone"], type="filepath")` gives BOTH a file picker and a mic
  recorder in one widget and returns a temp filepath - which is exactly what omnivoice `ref_audio`
  wants (a path). No numpy round-trip needed.
- Serial execution is mandatory on 4GB VRAM: set `demo.queue(default_concurrency_limit=1)` AND keep
  `concurrency_limit=1` on the generate click. Default is already 1, but pin it so a future edit can't
  silently allow parallel generations that would OOM.
- `app.py` will grow over phases 3-5; keep it < 200 lines by pushing reusable bits into helpers. If it
  approaches the limit, split UI construction vs event handlers into a second module (e.g.
  `app_handlers.py`). Decide at end of this phase.
- `app.py` MUST `import tts_engine` (which sets HF_HOME) BEFORE anything imports omnivoice. Importing
  the engine module at the top of app.py satisfies this.

## Requirements

### Functional (this phase = single sentence only)
- Launch: `app.py` builds a `gr.Blocks`, binds `127.0.0.1:7860`, `inbrowser=True`, serial queue.
- Tab "Tạo giọng nói":
  - `gr.Textbox` (lines ~8, label "Văn bản cần đọc") for input text.
  - Collapsible `gr.Accordion("Giọng mẫu", open=False)` containing:
    - `gr.Dropdown` listing files in `refs/` (label "Chọn giọng mẫu có sẵn"), with a refresh button
      ("Tải lại danh sách") that returns `gr.update(choices=list_refs())`.
    - `gr.Audio(sources=["upload","microphone"], type="filepath", label "Tải lên hoặc thu âm")`.
    - `gr.Textbox` (label "Lời mẫu (lời thoại trong giọng mẫu)").
    - Note text: empty giọng mẫu = giọng mặc định.
  - `gr.Slider(8, 32, value=16, step=1, label "Số bước (steps)")`.
  - `gr.Checkbox(label "Dùng CPU", value=False)`.
  - `gr.Button("Đọc", variant="primary")`.
  - Outputs: `gr.Audio(label "Kết quả", type="filepath", autoplay or interactive=False)` + a
    `gr.Textbox(label "Đường dẫn file")` showing the saved path.
  - `gr.Button("Giải phóng VRAM")` + a small status textbox.
- Generate handler (single sentence):
  - resolve giọng mẫu: uploaded/recorded path takes priority, else dropdown selection, else None.
  - `device,dtype = pick_device(use_cpu)`; `engine.ensure_loaded(device,dtype)`;
    `audio = engine.generate_one(text, ref_audio, ref_text, steps)`.
  - save to `outputs/<auto-name>.wav` via `sf.write` (filename scheme finalized in Phase 5; for now a
    timestamp name is fine, sidecar JSON comes in Phase 5).
  - return the saved path to both the audio player and the path textbox.
- "Giải phóng VRAM" handler: `engine.unload()` -> status "Đã giải phóng VRAM."
- OOM handling: catch `torch.cuda.OutOfMemoryError` / RuntimeError containing "out of memory" ->
  user-facing `gr.Warning` "Hết VRAM. Hãy bật 'Dùng CPU' hoặc giảm số bước." (do not crash the server).

### Non-functional
- All labels/buttons/messages in Vietnamese WITH full diacritics.
- ASCII punctuation only in code/comments.
- `start-ui.bat` is kebab-case; Python files snake_case.
- UTF-8 console (engine already reconfigures; app.py can rely on it after import).

## Architecture

```
app.py
  import tts_engine           # sets HF_HOME before omnivoice loads
  from tts_engine import engine, pick_device, REFS_DIR, OUTPUTS_DIR, SAMPLE_RATE
  import gradio as gr, soundfile as sf

  list_refs() -> [str]        # *.wav/*.mp3 in refs/
  on_generate(text, dd_ref, audio_ref, ref_text, steps, use_cpu, progress=gr.Progress()) -> (audio_path, path_str)
  on_release_vram() -> status
  build_ui() -> gr.Blocks
  if __name__ == "__main__":
      build_ui().queue(default_concurrency_limit=1).launch(server_name="127.0.0.1", inbrowser=True)
```

start-ui.bat (kebab-case, double-click):
```
@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
uv run python app.py
pause
```

## Related Code Files

- **Create:** `D:\source-code\omnivoice-vietnamese\app.py`
- **Create:** `D:\source-code\omnivoice-vietnamese\start-ui.bat`
- **Maybe create:** `D:\source-code\omnivoice-vietnamese\app_handlers.py` (only if app.py >= 200 lines)
- **Modify:** none (engine already exists from Phase 1)
- **Delete:** none

## Implementation Steps

1. Install: `UV_LINK_MODE=copy uv pip install "gradio==6.16.0"`. Confirm import:
   `uv run python -c "import gradio; print(gradio.__version__)"` -> `6.16.0`.
2. Create `app.py` importing `tts_engine` first (HF_HOME ordering), then gradio.
3. Implement `list_refs()` (glob `refs/*.wav`, `refs/*.mp3`).
4. Build the "Tạo giọng nói" tab UI exactly per the spec (Vietnamese labels w/ diacritics).
5. Implement `on_generate` for a SINGLE sentence (no chunking). Wire OOM warning.
6. Implement `on_release_vram`.
7. Wire `.click` handlers with `concurrency_limit=1`; wire dropdown refresh button.
8. Configure `.queue(default_concurrency_limit=1).launch(server_name="127.0.0.1", inbrowser=True)`.
9. Create `start-ui.bat`.
10. Compile-check: `uv run python -c "import app"` (import must not auto-launch the server -
    launch is guarded by `__main__`).
11. Manual smoke (short sentence) is allowed here but the FORMAL GPU smoke test is Phase 6.
12. If `app.py` >= 200 lines, extract handlers to `app_handlers.py` and re-check.

## Todo List

- [ ] gradio==6.16.0 installed via `UV_LINK_MODE=copy uv pip install`, version verified
- [ ] `app.py` imports tts_engine before gradio (HF_HOME ordering preserved)
- [ ] "Tạo giọng nói" tab built with all widgets, Vietnamese labels + diacritics
- [ ] Giọng mẫu accordion: dropdown(refs) + refresh + upload/mic Audio + lời mẫu textbox
- [ ] Single-sentence `on_generate` works end to end, returns audio + path
- [ ] OOM caught -> gr.Warning, server stays alive
- [ ] "Giải phóng VRAM" calls engine.unload()
- [ ] Serial queue pinned (default_concurrency_limit=1 + per-click limit)
- [ ] launch binds 127.0.0.1:7860, inbrowser=True
- [ ] `start-ui.bat` created (kebab-case, PYTHONUTF8=1)
- [ ] `import app` compiles without launching; app.py < 200 lines (or split done)

## Success Criteria

- `start-ui.bat` double-click -> browser opens at 127.0.0.1:7860.
- Typing a short Vietnamese sentence + "Đọc" -> audio plays inline + a .wav exists in `outputs/`.
- Uploading or recording a giọng mẫu + lời mẫu -> cloned-voice output.
- "Giải phóng VRAM" frees memory (no crash; subsequent generate reloads lazily).
- Server bound to localhost only (not 0.0.0.0).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| gradio import pulls omnivoice indirectly before HF_HOME set | Low | High | `import tts_engine` is the FIRST import in app.py; it sets HF_HOME on import. gradio does not import omnivoice. |
| Parallel generations OOM the 4GB card | Med | High | Serial queue pinned at both Blocks and click level. |
| `server_name="0.0.0.0"` accidentally exposes UI on LAN | Low | Med | Hardcode `127.0.0.1`; document in success criteria; no `share=True`. |
| gradio 6.16.0 install slow / fails (cross-fs hardlink) | Low | Low | `UV_LINK_MODE=copy` already handles cross-filesystem; documented. |
| Mic recording returns a path the model can't read | Low | Med | `type="filepath"` yields a real temp wav; omnivoice reads paths. Verify in manual smoke. |
| app.py exceeds 200 lines mid-build | Med | Low | Extract handlers to app_handlers.py (step 12). |

## Security Considerations

- Localhost bind only, single-user tool, no auth needed by design.
- No `share=True` (would tunnel to public Gradio URL) - explicitly avoid.
- Uploaded audio stays in Gradio temp + (optionally) refs/; no external upload.

## Next Steps

- Unblocks Phase 4 (replace single-sentence generate with the long-text pipeline).
- Phase 5 will add sidecar JSON at save time and the History tab.

## Resolved questions

- ~~Should uploaded/recorded giọng mẫu be auto-saved into `refs/`?~~ **USER DECIDED (260608):**
  ephemeral by default + a "Lưu vào refs/" button next to the upload/mic widget. Clicking it copies
  the current ref audio into `refs/ref-<timestamp>.<ext>` and refreshes the dropdown (new file
  selected). No audio uploaded -> friendly status message, no error.
