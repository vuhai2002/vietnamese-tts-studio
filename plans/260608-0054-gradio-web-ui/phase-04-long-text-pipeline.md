# Phase 4: Long-text pipeline + self-reference + partial-failure

## Context Links

- ADR (self-reference decision): `D:\source-code\omnivoice-vietnamese\docs\adr\0001-tu-lay-mau-doan-1-cho-van-ban-dai.md`
- Glossary (Tự lấy mẫu / Self-Reference): `D:\source-code\omnivoice-vietnamese\CONTEXT.md`
- Splitter from Phase 2: `text_splitter.split_text`
- Engine from Phase 1: `tts_engine.engine`
- Overview: [plan.md](plan.md)

## Overview

- **Priority:** P1 (the headline feature)
- **Status:** pending (blocked by Phases 2 and 3)
- **Description:** Replace the single-sentence `on_generate` with the full long-text pipeline: split ->
  generate chunks sequentially with one consistent voice -> concatenate with short silences -> ONE
  24000 Hz wav. Show per-chunk progress. On mid-stream failure (e.g. OOM at chunk 17/40) save what
  completed as `..._partial.wav` and tell the user which chunk failed + how to recover.

## Key Insights

- **Voice consistency is the whole point** (ADR 0001). Two paths:
  - User PICKED a giọng mẫu -> use that same `ref_audio` + `ref_text` for ALL chunks.
  - User picked NONE -> generate chunk 1 with the default voice, then use **chunk 1's audio array +
    chunk 1's text** as the reference (`ref_audio`, `ref_text`) for chunks 2..n. No Whisper needed
    because ref_text is literally chunk 1's text. This is "Tự lấy mẫu".
- `engine.generate_one` currently takes `ref_audio` as a PATH (omnivoice wants a path). For
  self-reference we have chunk 1 as an in-memory numpy array. Two clean options - pick one in this phase:
  - (A) Write chunk 1 to a temp wav file and pass its path as `ref_audio` for later chunks. Simple,
    matches the existing path-based API, costs one temp file. RECOMMENDED (KISS).
  - (B) Extend `generate_one` to accept an array ref. Only if omnivoice supports array refs; needs
    verifying and likely changes the engine signature. Avoid unless (A) proves insufficient.
- **Sequential only.** 4GB VRAM cannot hold parallel generations. Loop chunks, and call
  `torch.cuda.empty_cache()` between chunks (expose a tiny `engine.empty_cache()` helper or call it
  inside `generate_one`'s caller). Keep the model LOADED across chunks (don't unload between chunks -
  reloading per chunk would be brutally slow); only clear the cache.
- **Concatenation:** all chunks are 24000 Hz mono float arrays from the same model. Insert ~0.25s of
  silence (`np.zeros(int(0.25 * SAMPLE_RATE), dtype=audio.dtype)`) between consecutive chunks, then
  `np.concatenate(...)`. Do NOT add silence before the first or after the last chunk.
- **Partial failure is expected on this hardware** - design for it, don't treat as edge case. If chunk
  k fails, we still have chunks 1..k-1: concatenate them, save `<base>_partial.wav`, and report
  "Lỗi ở đoạn k/n" with the recovery hint.

## Requirements

### Functional
- New module `long_text.py` (keeps app.py thin) exposing:
  - `generate_long(text, ref_audio, ref_text, steps, device, dtype, progress=None) -> dict`
    returning `{"audio": np.ndarray | None, "n_chunks": int, "failed_at": int | None, "partial": bool}`
    (app.py turns this into the saved file + user messages).
- Pipeline behavior:
  1. `chunks = split_text(text)`. If `len(chunks) <= 1` -> behave like single-sentence (still go
     through the same path for consistency; n_chunks may be 1).
  2. `engine.ensure_loaded(device, dtype)` once, before the loop.
  3. Determine reference strategy (user-picked vs self-reference) per Key Insights.
  4. For i, chunk in enumerate(chunks):
     - `progress(i/len, desc=f"đang đọc đoạn {i+1}/{len(chunks)}...")` if progress provided.
     - generate this chunk with the active ref (None for chunk 1 in self-ref mode).
     - after chunk 1 in self-ref mode: persist chunk-1 audio to a temp wav, set it + chunk-1 text as
       the ref for subsequent chunks.
     - `engine.empty_cache()` after each chunk.
     - on exception (OOM/RuntimeError): break, record `failed_at = i+1`, set partial.
  5. Concatenate completed chunks with 0.25s silence between -> `audio`.
  6. Return the result dict (audio may be a partial concat, or None if chunk 1 itself failed).
- app.py `on_generate` (updated):
  - builds device/dtype, resolves ref, calls `generate_long(..., progress=progress)`.
  - if full success -> save `<auto-name>.wav`, return audio + path + success message.
  - if partial -> save `<auto-name>_partial.wav`, return that audio + a `gr.Warning`:
    "Dừng ở đoạn k/n (hết VRAM?). Đã lưu phần hoàn thành vào ..._partial.wav. Thử bật 'Dùng CPU' hoặc giảm số bước."
  - if nothing completed -> `gr.Warning` only, no file.

### Non-functional
- `long_text.py` < 200 lines. app.py stays < 200 (handlers may live in app_handlers.py from Phase 3).
- Progress messages in Vietnamese with diacritics ("đang đọc đoạn 3/12...").
- Temp self-reference wav cleaned up (or written under a temp dir) so it doesn't pollute outputs/.

## Architecture

Data flow:
```
text --split_text--> [c1, c2, ... cn]
                         |
        +----------------+ user picked ref? ------> ref=(user_audio, user_text) for ALL
        | no
        v
   gen c1 (ref=None) --> a1 ; write a1 to temp.wav ; ref=(temp.wav, c1)
                         |
   for c2..cn: gen ci with ref=(temp.wav, c1)  [self-reference, ADR 0001]
                         |
   each iter: progress(i/n, "đang đọc đoạn i/n...") ; empty_cache()
                         |
   on failure at k: stop, partial=True, failed_at=k
                         v
   concat([a1, sil, a2, sil, ..., a_{k-1}])  -> final/partial audio (24000 Hz)
```

Silence helper:
```
SIL = np.zeros(int(0.25 * SAMPLE_RATE), dtype=np.float32)
joined = audios[0]
for a in audios[1:]:
    joined = np.concatenate([joined, SIL, a])
```

OOM detection (broad, since omnivoice may surface different types):
```
except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
    if "out of memory" in str(e).lower() or isinstance(e, torch.cuda.OutOfMemoryError):
        failed_at = i + 1; partial = True; engine.empty_cache(); break
    raise
```

## Related Code Files

- **Create:** `D:\source-code\omnivoice-vietnamese\long_text.py`
- **Modify:** `D:\source-code\omnivoice-vietnamese\app.py` (and/or `app_handlers.py`) - swap single-sentence generate for `generate_long`
- **Modify:** `D:\source-code\omnivoice-vietnamese\tts_engine.py` - add `empty_cache()` helper if not already present (cuda-guarded)
- **Delete:** none

## Implementation Steps

1. Add `engine.empty_cache()` to tts_engine.py (guarded by `torch.cuda.is_available()`).
2. Create `long_text.py` with `generate_long(...)` per the spec. Use temp-file self-reference (option A).
3. Implement the silence-joined concatenation helper.
4. Implement broad OOM-aware try/except inside the chunk loop; populate `failed_at`/`partial`.
5. Update app.py `on_generate` to call `generate_long`, handle full/partial/none outcomes, wire
   `gr.Progress` and the partial `gr.Warning`.
6. Ensure the temp self-reference wav is written to a temp location and removed in a `finally`.
7. Compile-check: `uv run python -c "import long_text, app"`.
8. Functional check on a multi-sentence paragraph (real GPU; formal smoke is Phase 6) - confirm single
   joined file, audible silences between sentences, consistent voice.

## Todo List

- [ ] `engine.empty_cache()` added (cuda-guarded)
- [ ] `long_text.generate_long` splits, loops sequentially, clears cache between chunks
- [ ] User-picked ref used for all chunks; else self-reference from chunk 1 (ADR 0001)
- [ ] Self-reference uses a temp wav of chunk 1, cleaned up in finally
- [ ] Chunks concatenated with 0.25s silence (none at start/end)
- [ ] OOM/RuntimeError mid-stream -> partial concat, failed_at set, no crash
- [ ] app.py: full success saves `.wav`; partial saves `_partial.wav` + gr.Warning; none -> warning only
- [ ] gr.Progress shows "đang đọc đoạn i/n..." (Vietnamese + diacritics)
- [ ] `import long_text, app` compiles; both files < 200 lines
- [ ] Multi-sentence functional check: one joined 24000 Hz file, consistent voice

## Success Criteria

- A 6-8 sentence Vietnamese paragraph with NO giọng mẫu -> one seamless `.wav`, same voice throughout
  (self-reference working), short pauses between sentences.
- The same paragraph WITH a giọng mẫu -> one seamless `.wav` in the cloned voice.
- Forcing OOM (high steps on GPU, or a very long input) -> a `_partial.wav` is saved, the UI reports
  the failing chunk number, and the server keeps running.
- Progress updates visibly count chunks during generation.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Voice drifts between chunks (self-ref not actually applied) | Med | High | After chunk 1, ALWAYS pass chunk-1 temp wav + text as ref for 2..n; verify by ear in success criteria. |
| VRAM creeps up across chunks -> OOM mid-paragraph | High | High | empty_cache() every chunk; keep steps modest; partial-save path makes failure recoverable not catastrophic. |
| Concatenation dtype/shape mismatch -> garbled audio | Low | High | All chunks come from same model at 24000 Hz mono; build SIL with matching dtype; np.concatenate on 1-D arrays. |
| Temp self-ref wav leaks into outputs/ or never deleted | Med | Low | Write under tempfile dir; remove in finally. |
| Self-ref reads array but engine API only takes path | - | - | Resolved by option A (write temp wav). Do NOT change engine signature unless A fails. |
| Partial save itself fails (disk) | Low | Med | Wrap save in try/except; if partial save fails, still surface the chunk-failure warning. |

## Security Considerations

- Temp files under the OS temp dir; clean up. No new network surface.

## Next Steps

- Unblocks Phase 5 (sidecar JSON written at the same save points; History reads them).
- Phase 6 smoke test exercises this pipeline on real GPU.

## Unresolved questions (non-blocking)

- Silence length 0.25s is the approved default; if paragraphs sound rushed/draggy, it can be made a
  constant tweak later. Not a blocker.
