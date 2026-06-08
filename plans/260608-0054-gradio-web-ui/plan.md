---
title: "Gradio Web UI for Vietnamese TTS"
description: "Add a 2-tab local Gradio UI (generate + history) over the existing KhanhTTS CLI, with long-text auto-chunking and self-reference voice consistency."
status: completed
priority: P2
effort: 13h
branch: (no git repo - local only)
tags: [gradio, ui, tts, vietnamese, refactor]
created: 2026-06-08
---

# Gradio Web UI for Vietnamese TTS

Wrap the existing `run.py` KhanhTTS-OmniVoice CLI in a local single-user Gradio web UI.
Design is APPROVED (brainstorm/grill done) - phases below only break it into work.

## Goal (observable "done")

- Double-click `start-ui.bat` -> browser opens at `http://127.0.0.1:7860`.
- Tab "Tạo giọng nói": paste text (1 sentence or long), optionally pick/upload/record a giọng mẫu, click "Đọc" -> hear audio inline + get a saved `.wav`.
- Long text is auto-split, generated chunk-by-chunk on 4GB VRAM, joined into ONE seamless 24000 Hz file, one consistent voice start to finish.
- Tab "Lịch sử": see past files (time / text / voice), replay, delete.
- `run.py` CLI still works identically (regression-safe).

## Architecture at a glance

```
                 +-------------------+
 run.py (CLI) -->|                   |
                 |   tts_engine.py   |---> OmniVoice model (lazy, VRAM-resident)
 app.py (UI) --->|  load/unload/gen  |
   |             +-------------------+
   |                      ^
   +--> text_splitter.py--+  (long text -> chunks)
   +--> sidecar JSON (outputs/*.json) <-- History tab reads these
```

HF_HOME -> `<project>/.cache/huggingface` MUST be set before omnivoice import.
Owner of that ordering moves from `run.py` top to `tts_engine.py` top (Phase 1).

## Phases

| # | Phase | File | Status | Blocks on |
|---|-------|------|--------|-----------|
| 1 | Refactor run.py -> tts_engine.py (CLI regression-safe) | [phase-01-tts-engine-refactor.md](phase-01-tts-engine-refactor.md) | completed | - |
| 2 | text_splitter.py + GPU-free unit tests | [phase-02-text-splitter.md](phase-02-text-splitter.md) | completed | - |
| 3 | Install gradio + app.py basic TTS tab + start-ui.bat | [phase-03-gradio-app-basic.md](phase-03-gradio-app-basic.md) | completed | 1 |
| 4 | Long-text pipeline + self-reference + partial-failure | [phase-04-long-text-pipeline.md](phase-04-long-text-pipeline.md) | completed | 2, 3 |
| 5 | History tab + sidecar JSON metadata | [phase-05-history-sidecar.md](phase-05-history-sidecar.md) | completed | 4 |
| 6 | End-to-end smoke test + README/docs update | [phase-06-smoke-test-docs.md](phase-06-smoke-test-docs.md) | completed | 5 |

Phases 1 and 2 are independent (different files) - can run in parallel.

## Key dependencies / pinned facts (from research)

- **gradio 6.16.0** (latest stable, 2026-06-03; Python 3.12 in classifiers). Pin this exact version.
- `gr.Audio(sources=["upload","microphone"], type="filepath")` -> returns a temp path (matches omnivoice `ref_audio` which wants a path).
- `gr.Progress`: declare `progress=gr.Progress()` as last param; call `progress(i/n, desc="...")`.
- Serial generation: default concurrency is 1, but pin `demo.queue(default_concurrency_limit=1)` explicitly (4GB VRAM, no parallel gen).
- `gr.Dropdown` refresh of `refs/`: return `gr.update(choices=[...])` from a refresh handler.

## Hard constraints carried into every phase

1. HF_HOME set before importing omnivoice/huggingface_hub (Phase 1 moves this to tts_engine.py top).
2. cuda:0 + float16 when available, else cpu + float32. RTX 3050 Ti, 4GB VRAM.
3. No pyproject.toml / uv.lock - install bare into .venv via `uv pip install` + `UV_LINK_MODE=copy`.
4. Python = snake_case; .bat = kebab-case. Each code file < 200 lines.
5. Vietnamese UI strings keep FULL diacritics. ASCII punctuation only in code/comments.
6. Windows 11 / PowerShell. UTF-8 stdout reconfigure like run.py.
7. omnivoice 0.1.5: `OmniVoice.from_pretrained(MODEL_ID, device_map=device, dtype=dtype)`,
   `model.generate(text=, num_step=, ref_audio=, ref_text=)` -> array; `sf.write(path, audio[0], 24000)`.
   Preserve the existing `TypeError` fallback (retry without `num_step`).

## Unresolved questions (for user, non-blocking)

- See phase files; none block starting Phase 1/2.
