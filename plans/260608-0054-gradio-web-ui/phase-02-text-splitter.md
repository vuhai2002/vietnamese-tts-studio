# Phase 2: text_splitter.py + GPU-free unit tests

## Context Links

- Glossary (Đoạn / Chunk, Văn bản dài): `D:\source-code\omnivoice-vietnamese\CONTEXT.md`
- ADR (why long text is chunked): `D:\source-code\omnivoice-vietnamese\docs\adr\0001-tu-lay-mau-doan-1-cho-van-ban-dai.md`
- Overview: [plan.md](plan.md)

## Overview

- **Priority:** P1 (Phase 4 depends on it; fully testable without GPU so do it early)
- **Status:** pending
- **Description:** Pure-Python function that splits long Vietnamese text into chunks (roughly one
  sentence each) on `. ! ?` and newlines, WITHOUT falsely splitting on abbreviations ("TP.", "v.v.")
  or decimal numbers ("3.5"), and merges too-short fragments into neighbours.

## Key Insights

- This is the only component that can be fully unit-tested offline - lean into it. The model phases
  can only be smoke-tested; this one gets a real test matrix.
- Vietnamese false-split traps to guard:
  - Abbreviations ending in a dot: `TP.` (Thành phố), `v.v.` (vân vân), `Tp.`, `Q.` (Quận),
    `P.` (Phường), `Tr.` (trang), `ĐT.`, `TS.`, `Th.S`, `GS.`, `PGS.` - keep a small configurable set.
  - Decimal numbers: `3.5`, `1.000.000` (VN uses `.` as thousands separator too) - a dot between two
    digits is NOT a sentence end.
  - Ellipsis `...` - treat the run of dots as one boundary, not three empty chunks.
- "Too short" merging matters because a 1-2 word chunk wastes a whole model.generate() call and can
  sound clipped. Merge fragments below a min length into the previous (or next) chunk.
- Keep it dependency-free (stdlib `re` only). No nltk/underthesea - YAGNI for a single-user tool and
  avoids a heavy install on a 4GB machine.

## Requirements

### Functional
- Public API (suggested):
  - `split_text(text: str, min_chars: int = 30, max_chars: int = 280) -> list[str]`
  - Returns a list of non-empty, stripped chunks. Empty / whitespace input -> `[]`.
  - A single short sentence -> `[that_sentence]` (list of one; never returns the raw string).
- Splitting rules:
  1. Split on sentence-ending punctuation `.`, `!`, `?` (and `...`) that is a real terminator,
     plus hard newlines (`\n`, blank lines force a boundary).
  2. Do NOT split when the `.` is part of a known abbreviation or sits between two digits.
  3. Keep the terminating punctuation attached to its chunk (so the model reads it naturally).
  4. Merge any chunk shorter than `min_chars` into the previous chunk (or the next one if it is the
     first). Goal: avoid 1-3 word fragments.
  5. If a single sentence exceeds `max_chars` (rare run-on with no punctuation), soft-split on the
     last comma/space before `max_chars` so no chunk is unboundedly long (4GB VRAM safety).

### Non-functional
- `text_splitter.py` < 200 lines, stdlib only.
- Deterministic (same input -> same chunks).
- Diacritics preserved exactly (never normalize/strip Vietnamese letters).

## Architecture

```
split_text(text)
  -> normalize newlines, collapse excessive blank lines
  -> protect abbreviations + decimals (mask their dots so regex won't break there)
  -> regex split on [.!?]+ (and \n) keeping delimiters
  -> unmask dots
  -> strip + drop empties
  -> merge_short(chunks, min_chars)
  -> soft_split_long(chunks, max_chars)
  -> return chunks
```

Masking approach (KISS): temporarily replace the dot in a matched abbreviation/decimal with a
sentinel like `\x00`, split, then restore. Avoids fragile lookbehind/lookahead soup.

## Related Code Files

- **Create:** `D:\source-code\omnivoice-vietnamese\text_splitter.py`
- **Create:** `D:\source-code\omnivoice-vietnamese\tests\test_text_splitter.py`
- **Modify:** none
- **Delete:** none

## Implementation Steps

1. Create `text_splitter.py` with the abbreviation set as a module constant (easy to extend).
2. Implement dot-masking for abbreviations and for `digit.digit` runs.
3. Implement the regex split keeping delimiters; unmask.
4. Implement `merge_short` and `soft_split_long` helpers.
5. Create `tests/test_text_splitter.py` using stdlib `unittest` (no pytest dependency needed; runs
   with `uv run python -m unittest`). Cover the matrix below.
6. Run tests: `uv run python -m unittest tests.test_text_splitter -v` -> all green, NO GPU touched.

## Test Matrix (must all pass, GPU-free)

| Case | Input | Expected |
|------|-------|----------|
| Single short sentence | `"Xin chào."` | `["Xin chào."]` |
| Two sentences | `"Trời đẹp. Đi chơi thôi."` | 2 chunks |
| Question + exclamation | `"Bạn khỏe không? Tuyệt vời!"` | 2 chunks |
| Abbreviation "TP." | `"Tôi sống ở TP. Hồ Chí Minh từ nhỏ."` | 1 chunk (no split after TP.) |
| Abbreviation "v.v." | `"Có táo, cam, v.v. trong giỏ."` | 1 chunk |
| Decimal number | `"Giá là 3.5 triệu đồng."` | 1 chunk |
| Thousands separator | `"Tổng cộng 1.000.000 đồng nhé."` | 1 chunk |
| Ellipsis | `"Ừ thì... cũng được."` | not 3 empty chunks; 1-2 sensible chunks |
| Newline as boundary | `"Dòng một\nDòng hai"` | 2 chunks |
| Blank-line paragraph | `"Đoạn A.\n\nĐoạn B."` | 2 chunks |
| Short-fragment merge | `"Ừ. Tôi đồng ý hoàn toàn với bạn về điều này."` | "Ừ." merged into next -> 1 chunk |
| Empty / whitespace | `"   "` | `[]` |
| Run-on > max_chars | 400-char no-period string | multiple chunks, each <= max_chars |
| Diacritics intact | `"Nguyễn Thị Hoè ở Huế."` | chunk text byte-identical incl. tone marks |

## Todo List

- [ ] `text_splitter.py` created (stdlib only, < 200 lines)
- [ ] Abbreviation set + decimal masking implemented
- [ ] Regex split keeps delimiters; merge_short + soft_split_long done
- [ ] `tests/test_text_splitter.py` covers every row of the matrix
- [ ] `uv run python -m unittest tests.test_text_splitter -v` all pass
- [ ] No GPU / no omnivoice imported by the test (verify: test file imports only text_splitter)
- [ ] Diacritics verified byte-identical in at least one assertion

## Success Criteria

- All matrix rows pass as real assertions (not skipped).
- Tests run on a machine with no CUDA and complete in < 1s.
- `split_text("")` -> `[]`; `split_text("Xin chào.")` -> `["Xin chào."]`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Over-aggressive abbreviation list eats real sentence ends | Med | Med | Keep list small + explicit; only mask when followed by space + capital is NOT required (VN nouns vary). Cover with matrix cases. |
| Thousands-separator `1.000.000` split into pieces | Med | Med | Decimal mask treats any `digit.digit` as protected; test the million case. |
| Unicode width / combining-mark edge cases corrupt diacritics | Low | High | Operate on `str` (not bytes); never call `.encode`/normalize; assert byte-identity in a test. |
| max_chars soft-split lands mid-word | Low | Low | Prefer last comma, then last space, before the limit; acceptable if rare. |

## Security Considerations

- None. Pure string processing, no I/O, no eval.

## Next Steps

- Unblocks Phase 4 (the long-text pipeline imports `split_text`).
- Independent of Phase 1; can be built in parallel.
