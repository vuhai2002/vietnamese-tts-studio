# Project Changelog

## 2026-06-08 - Web UI riêng (FastAPI) + tốc độ đọc + quản lý giọng mẫu

**Thay đổi lớn:**
- Thay giao diện Gradio bằng **web riêng**: backend FastAPI (`web_server.py`) + frontend tĩnh
  (`web/`: HTML/CSS/JS, font Be Vietnam Pro, tông slate + xanh dương, sáng/tối). Lõi tái dùng nguyên.
- **Tốc độ đọc**: dropdown 5 mức (rất chậm -> rất nhanh) qua tham số `speed`, áp cả giọng mặc định
  lẫn clone + văn bản dài; CLI thêm `--speed`.
- **Quản lý giọng mẫu**: lưu giữ ĐÚNG tên file gốc (trùng tự thêm `-2`), nút xóa giọng mẫu, nút bỏ
  chọn, chặn lưu trùng nhiều lần cùng một file.
- **Lịch sử**: bấm play phát ngay tại dòng (bỏ thanh audio tách rời ở cuối).

**Gỡ bỏ:**
- "Mô tả giọng" (voice design / `instruct`): đã test, model KhanhTTS tiếng Việt không đổi giọng theo
  mô tả (chỉ cao độ ăn nhẹ) -> gỡ khỏi UI. Xem cảnh báo trong `CLAUDE.md`.

## 2026-06-08 - Giao diện web Gradio + đọc văn bản dài

**Thêm mới:**
- Giao diện web Gradio (`app.py` + `app_history_tab.py`), mở bằng `start-ui.bat`,
  bind `127.0.0.1:7860` (chỉ máy này), không `share=True`.
  - Tab "Tạo giọng nói": textbox văn bản (1 câu hay cả bài), khối giọng mẫu
    (dropdown `refs/` + upload + thu âm mic + nút "Lưu vào refs/"), slider steps 8-32,
    checkbox "Dùng CPU", progress từng đoạn, nút "Giải phóng VRAM".
  - Tab "Lịch sử": bảng file đã sinh (thời gian / nội dung / giọng mẫu), nghe lại,
    xóa (xóa cả wav + json).
- Đọc văn bản dài: `text_splitter.py` (cắt câu tiếng Việt, né viết tắt "TP."/"v.v." và
  số "3.5"/"1.000.000") + `long_text.py` (sinh tuần tự từng đoạn, ghép + khoảng lặng 0.25s,
  lưu `..._partial.wav` khi lỗi giữa chừng - thiết kế cho máy 4GB VRAM).
- Đồng nhất giọng văn bản dài bằng cơ chế "tự lấy mẫu" (xem `docs/adr/0001`):
  đoạn 1 sinh giọng mặc định rồi làm giọng mẫu cho mọi đoạn sau, không cần Whisper.
- Sidecar JSON cạnh mỗi wav (`history.py`): text đầy đủ GIỮ DẤU, giọng mẫu, steps,
  device, thời điểm; tên file `YYYYMMDD-HHMM_<slug>.wav`, tự né trùng tên.
- Test: `tests/test_text_splitter.py` (21 case, không cần GPU) +
  `tests/smoke_e2e.py` (end-to-end model THẬT trên GPU, không mock).

**Thay đổi:**
- `run.py` tách thành CLI mỏng + `tts_engine.py` (lõi chung CLI/UI: lazy load,
  giữ VRAM, unload, đổi device; HF_HOME ordering chuyển về đầu `tts_engine.py`).
  CLI giữ nguyên 100% tham số + stdout - đã regression cả GPU lẫn CPU.
- Cài thêm `gradio==6.16.0` (bare `.venv`, `UV_LINK_MODE=copy`, không thêm pyproject.toml).

**Tài liệu:** `CONTEXT.md` (glossary domain), `docs/adr/0001` (quyết định tự lấy mẫu),
`README.md` (mục "Giao diện web"), `CLAUDE.md` (cấu trúc + ràng buộc mới).
