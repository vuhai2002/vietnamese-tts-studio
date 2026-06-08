# Phase 5: History tab + sidecar JSON metadata

## Context Links

- Save points from Phase 4: `long_text.py` / `app.py` `on_generate`
- Engine dirs: `tts_engine.OUTPUTS_DIR`
- Overview: [plan.md](plan.md)

## Overview

- **Priority:** P2
- **Status:** pending (blocked by Phase 4)
- **Description:** Finalize the auto-filename scheme, write a sidecar JSON next to every generated wav
  (full text, ref voice, steps, device, timestamp), and add the "Lịch sử" tab: a table of past
  generations (datetime / text / giọng mẫu used) with replay and delete.

## Key Insights

- A sidecar JSON per wav (same basename, `.json`) is the simplest durable store for a single-user tool -
  no DB, survives restarts, trivially deletable alongside its wav (DRY with the "delete folder to
  clean" project philosophy). YAGNI says no SQLite.
- The filename scheme was approved: `outputs/YYYYMMDD-HHmm_<slug>.wav` where `<slug>` is derived from
  the first few words of the text (diacritics-folded + non-alnum stripped for filesystem safety - this
  is the ONE place stripping diacritics is correct, because it is a filename token, not user-facing
  prose; the FULL original text with diacritics is preserved inside the JSON and shown in the UI).
- Partial outputs get the same scheme + `_partial` suffix (Phase 4 already names them); they should
  also get a sidecar JSON with `"partial": true` and `"failed_at": k` so History shows them honestly.
- The History table must be REFRESHABLE (new generations appear) - either a "Tải lại" button or refresh
  on tab-select. Keep KISS: a "Tải lại lịch sử" button returning the rebuilt table.

## Requirements

### Functional
- New module `history.py` exposing:
  - `slugify(text, max_words=6) -> str` - lowercased, Vietnamese diacritics folded to ASCII, spaces ->
    `-`, non `[a-z0-9-]` removed, trimmed; empty -> `"khong-tieu-de"`.
  - `build_output_paths(text, partial=False) -> tuple[Path, Path]` - returns (`wav_path`, `json_path`)
    using `YYYYMMDD-HHmm_<slug>(_partial).wav`. Handle name collisions (append `-2`, `-3`...).
  - `write_sidecar(json_path, meta: dict) -> None` - dump UTF-8 JSON (`ensure_ascii=False` so the
    stored Vietnamese text keeps diacritics), keys: `text`, `ref_voice` (path or null), `ref_text`
    (or null), `steps`, `device`, `created` (ISO 8601 local), `sample_rate`, `n_chunks`,
    `partial` (bool), `failed_at` (int or null), `wav` (basename).
  - `list_history() -> list[dict]` - scan `outputs/*.json`, parse, sort by `created` desc; tolerate a
    malformed/orphan json (skip with a logged note) and a wav with no json (synthesize a minimal row).
  - `delete_entry(wav_basename) -> None` - remove both the wav and its json if present.
- app.py wiring:
  - In `on_generate` (both full and partial paths), after `sf.write`, call `write_sidecar` with the
    real metadata used.
  - Tab "Lịch sử":
    - `gr.Dataframe` (read-only) columns: "Thời gian", "Nội dung" (truncated preview), "Giọng mẫu".
    - "Tải lại lịch sử" button -> repopulate the dataframe from `list_history()`.
    - Select a row -> load that wav into a `gr.Audio` player (replay). (Use the dataframe `.select`
      event to get the row; map back to the wav basename - keep the basename in a hidden column or a
      parallel state list.)
    - "Xóa" button on the selected row -> `delete_entry` + refresh the table + clear the player.

### Non-functional
- `history.py` < 200 lines. app.py stays < 200 (handlers in app_handlers.py if needed).
- All UI text Vietnamese w/ diacritics; JSON content keeps diacritics (`ensure_ascii=False`).
- Slug is the only place ASCII-folding of Vietnamese is intentional - comment it so a future reader
  does not "fix" it into stripping diacritics elsewhere.

## Architecture

```
on_generate(...) -> audio, meta
   wav_path, json_path = build_output_paths(text, partial)
   sf.write(wav_path, audio, SAMPLE_RATE)
   write_sidecar(json_path, meta)

Lịch sử tab:
   list_history() -> [{created, text, ref_voice, wav, partial, ...}, ...]
       -> Dataframe rows [[created, preview, ref_or_"mặc định"]]
   row select -> wav basename -> gr.Audio(value=outputs/<wav>)
   Xóa -> delete_entry(wav) -> refresh
```

Sidecar JSON example (stored with diacritics intact):
```json
{
  "text": "Xin chào, đây là một đoạn văn bản dài...",
  "ref_voice": "refs/mau.wav",
  "ref_text": "đúng lời trong file mẫu",
  "steps": 16,
  "device": "cuda:0",
  "created": "2026-06-08T01:05:30",
  "sample_rate": 24000,
  "n_chunks": 7,
  "partial": false,
  "failed_at": null,
  "wav": "20260608-0105_xin-chao-day-la.wav"
}
```

## Related Code Files

- **Create:** `D:\source-code\omnivoice-vietnamese\history.py`
- **Modify:** `D:\source-code\omnivoice-vietnamese\app.py` (and/or app_handlers.py) - add Lịch sử tab + sidecar writes
- **Modify:** `D:\source-code\omnivoice-vietnamese\long_text.py` only if filename building was inlined there in Phase 4 (prefer centralizing in history.py)
- **Delete:** none

## Implementation Steps

1. Create `history.py` with `slugify`, `build_output_paths`, `write_sidecar`, `list_history`,
   `delete_entry`. Use `json.dump(..., ensure_ascii=False, indent=2)`.
2. Replace the temporary timestamp naming from Phase 3/4 with `build_output_paths`.
3. Write the sidecar in both full-success and partial paths of `on_generate`.
4. Build the "Lịch sử" tab: Dataframe + "Tải lại lịch sử" + row-select replay + "Xóa".
5. Implement row->basename mapping (hidden basename column or parallel `gr.State` list).
6. Compile-check: `uv run python -c "import history, app"`.
7. Functional check: generate 2-3 clips, open Lịch sử, confirm rows/replay, delete one, confirm both
   wav + json gone and table refreshed.

## Todo List

- [ ] `history.py`: slugify (diacritics-folded, commented as intentional), build_output_paths w/ collision suffix
- [ ] write_sidecar uses ensure_ascii=False (stored text keeps diacritics)
- [ ] list_history sorts desc, tolerates orphan json and json-less wav
- [ ] delete_entry removes wav + json
- [ ] on_generate writes sidecar on BOTH full and partial saves
- [ ] Lịch sử tab: Dataframe (Thời gian/Nội dung/Giọng mẫu) + Tải lại + replay + Xóa
- [ ] Row-select maps to correct wav (hidden basename or State)
- [ ] `import history, app` compiles; files < 200 lines
- [ ] Functional: generate -> appears in history -> replay -> delete removes both files

## Success Criteria

- Every generate produces `outputs/<name>.wav` AND `outputs/<name>.json` with correct metadata
  (text incl. diacritics, ref voice, steps, device, timestamp).
- "Lịch sử" lists past clips newest-first; selecting one replays it; "Xóa" deletes wav+json and the
  row disappears after refresh.
- Deleting all heavy folders still works (no DB lock / external state) - sidecars live with the wavs.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Slug stripping mistaken as license to strip diacritics in UI prose | Med | High | Slug is filename-only; explicit comment; UI + JSON keep full diacritics (ensure_ascii=False). |
| Filename collision overwrites a prior clip | Med | Med | build_output_paths appends -2/-3 on collision. |
| Malformed/partial JSON crashes list_history | Med | Med | try/except per file; skip bad ones, synthesize minimal row for json-less wav. |
| gr.Dataframe row-select -> wrong wav after delete reindex | Med | Med | Map via stable basename (hidden col / State), not row index. |
| JSON written without ensure_ascii=False -> escaped \uXXXX (ugly but valid) | Low | Low | Pin ensure_ascii=False; assert in functional check that file contains readable Vietnamese. |

## Security Considerations

- `delete_entry` must only delete within `outputs/` - validate the basename has no path separators /
  `..` before unlinking (path traversal guard, even for a local tool).

## Next Steps

- Unblocks Phase 6 (smoke test verifies sidecar + history; docs document the outputs/ layout).
