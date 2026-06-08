# Phase 6: End-to-end smoke test + README/docs update

## Context Links

- All prior phases (engine, splitter, app, pipeline, history)
- Project docs to update: `D:\source-code\omnivoice-vietnamese\README.md`, `CLAUDE.md`
- Overview: [plan.md](plan.md)

## Overview

- **Priority:** P2 (gate before "done")
- **Status:** pending (blocked by Phase 5)
- **Description:** Prove the whole thing works on the real GPU with NO model mocking, confirm the CLI
  did not regress, then update user + agent docs to describe the new UI.

## Key Insights

- **Project rule: no fake/mock data to pass builds.** The end-to-end smoke MUST run the real
  `omnivoice` model on the real RTX 3050 Ti with a SHORT sentence (short = stays within 4GB). Mocking
  the model would violate the project rule and prove nothing about VRAM behavior.
- The text_splitter unit tests (Phase 2) are the GPU-free safety net and must stay green; the smoke
  test is the GPU-bound complement. Two different layers - keep both.
- The CLI regression is the contract guard for Phase 1: `run.py` must still behave exactly as before
  the refactor. This is cheap to verify and catches the highest-impact regression.
- Docs are part of "done" per documentation-management rules: README (user-facing, Vietnamese),
  CLAUDE.md (agent context - note new files + how to launch the UI), and a changelog entry.

## Requirements

### Functional - test layers
1. **Unit (GPU-free), already from Phase 2:** `uv run python -m unittest tests.test_text_splitter -v`
   -> all pass. Re-run here as a gate.
2. **CLI regression (GPU or CPU):**
   - `uv run python run.py --text "Xin chào, đây là kiểm tra hồi quy." --out outputs/_reg_cli.wav`
     -> exits 0, valid 24000 Hz wav, same stdout lines as pre-refactor.
   - `uv run python run.py --text "Kiểm tra CPU." --cpu --out outputs/_reg_cpu.wav` -> runs on CPU.
3. **End-to-end smoke (REAL GPU, no mock):** a small script `tests/smoke_e2e.py` (run manually /
   `uv run`) that:
   - imports `tts_engine`, `long_text`, `history`,
   - generates a SHORT single sentence via the engine -> asserts a non-empty 24000 Hz array,
   - generates a SHORT 2-3 sentence text via `generate_long` (self-reference path, no giọng mẫu) ->
     asserts ONE joined array longer than a single chunk, `partial is False`,
   - writes via `history.build_output_paths` + `write_sidecar` -> asserts both wav + json exist and
     the json round-trips with diacritics intact,
   - calls `engine.unload()` -> asserts `is_loaded` is False.
   - This script is GPU-bound; it is NOT part of the unittest suite (which must stay GPU-free).
4. **Manual UI smoke (checklist, real browser):**
   - `start-ui.bat` opens browser at 127.0.0.1:7860.
   - Single short sentence -> audio plays + file saved + appears in Lịch sử.
   - Short paragraph (no giọng mẫu) -> one seamless file, consistent voice, progress counted.
   - Upload/record a giọng mẫu -> cloned output.
   - "Giải phóng VRAM" works; a generate after it reloads lazily.
   - Lịch sử replay + delete (removes wav + json).

### Docs
- **README.md** (Vietnamese, diacritics): add a "Giao diện web (Gradio)" section - how to launch
  (`start-ui.bat` or `uv run python app.py`), the 2 tabs, long-text behavior, where files + sidecars
  land, the localhost-only note. Keep CLI section intact.
- **CLAUDE.md:** add the new files (`tts_engine.py`, `text_splitter.py`, `long_text.py`, `history.py`,
  `app.py`, `start-ui.bat`) to the structure, note that HF_HOME ordering now lives in tts_engine.py,
  note gradio==6.16.0 pin + bare-venv install command, and that the UI binds 127.0.0.1:7860.
- **docs/project-changelog.md** (create if missing): entry for "Thêm giao diện web Gradio + đọc văn
  bản dài (tự lấy mẫu, ghép đoạn)".

### Non-functional
- No new file > 200 lines (re-check app.py, long_text.py, history.py final sizes).
- Diacritics intact in all docs prose; ASCII punctuation in code/comments.

## Architecture

Test pyramid:
```
                 manual UI checklist (real browser, real GPU)   <- human
   tests/smoke_e2e.py  (real model, short inputs, GPU-bound)     <- 1 script
   CLI regression (run.py unchanged contract)                    <- 2 commands
   tests/test_text_splitter.py  (pure, GPU-free, many cases)     <- unittest gate
```

## Related Code Files

- **Create:** `D:\source-code\omnivoice-vietnamese\tests\smoke_e2e.py`
- **Create (if missing):** `D:\source-code\omnivoice-vietnamese\docs\project-changelog.md`
- **Modify:** `D:\source-code\omnivoice-vietnamese\README.md`
- **Modify:** `D:\source-code\omnivoice-vietnamese\CLAUDE.md`
- **Delete:** the temp regression wavs (`outputs/_reg*.wav`) after verifying, optional cleanup.

## Implementation Steps

1. Re-run the splitter unit tests as a gate -> all green.
2. Run the two CLI regression commands; eyeball stdout vs pre-refactor; confirm valid wavs.
3. Write `tests/smoke_e2e.py` (real model, short inputs) and run it on the GPU; fix any integration
   issues surfaced (this is where engine + long_text + history meet for real).
4. Walk the manual UI checklist in a browser; note any defects -> fix in the owning phase's file scope.
5. Update README.md (Vietnamese), CLAUDE.md (structure + pins + ordering note), changelog.
6. Final size check on all code files (< 200 lines).

## Todo List

- [ ] Splitter unit tests pass (GPU-free gate)
- [ ] CLI regression: default + --cpu produce valid wavs, stdout unchanged
- [ ] `tests/smoke_e2e.py` runs the REAL model (no mock) on short inputs and passes all asserts
- [ ] smoke covers: single sentence, self-reference long text (partial=False), sidecar round-trip w/ diacritics, unload
- [ ] Manual UI checklist walked in real browser - all items OK
- [ ] README.md updated with "Giao diện web (Gradio)" section (Vietnamese, diacritics)
- [ ] CLAUDE.md updated (new files, HF_HOME-in-engine note, gradio 6.16.0 pin + install cmd, 127.0.0.1)
- [ ] docs/project-changelog.md entry added
- [ ] All code files < 200 lines (final check)

## Success Criteria

- Three automated layers all pass: splitter unit tests, CLI regression, GPU smoke script.
- Manual UI checklist fully green.
- A new contributor reading README can launch the UI and use both tabs without asking questions.
- CLAUDE.md accurately reflects the new module layout + pins (an agent opening the repo cold gets it right).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Smoke test tempted to mock the model to "pass" | Med | High | Explicit rule: real model, SHORT inputs to fit 4GB. If GPU truly unavailable, run smoke with `--cpu` device, never mock. |
| Smoke OOMs even on short input | Low | Med | Use steps=8-12 and a very short sentence; smoke is about wiring, not quality. Fall back to CPU device for the smoke if needed. |
| CLI stdout drifted during Phase 1 refactor (silent regression) | Med | Med | Compare stdout lines against the pre-refactor run.py text captured in Phase 1. |
| Docs strip Vietnamese diacritics (global rule misread) | Med | High | Author prose with full diacritics; ASCII only for typographic punctuation, never for letters. |
| A code file crept over 200 lines across phases | Med | Low | Final size sweep; split handlers/UI if needed. |

## Security Considerations

- Confirm the shipped app binds 127.0.0.1 (not 0.0.0.0) and has no `share=True` before declaring done.
- Confirm `delete_entry` path-traversal guard from Phase 5 is present.

## Next Steps

- This is the final phase. On completion: mark all phase tasks complete, set plan.md status to
  completed, and report to the user with the launch instructions.

## Unresolved questions (non-blocking)

- Whether to keep `tests/smoke_e2e.py` in the repo long-term or treat as a one-off. Default: keep it
  (cheap, documents the integration contract). User can prune later.
