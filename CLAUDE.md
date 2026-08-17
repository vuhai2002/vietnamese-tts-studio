# CLAUDE.md - Context cho AI agent

> File này để AI agent (Claude Code...) đọc đầu tiên, hiểu nhanh project làm gì, dùng
> resource nào, và các ràng buộc BẮT BUỘC phải nhớ. Người dùng đọc `README.md` để biết cách dùng.

## Project này là gì

TTS (text-to-speech) + voice cloning **tiếng Việt**, chạy **offline 100% trên máy** (GPU local).
Mục tiêu: nhập văn bản tiếng Việt -> sinh file `.wav`; hoặc đưa giọng mẫu 3-10s -> clone giọng đó.

- Đây là **project sử dụng** (consumer), KHÔNG phải train model. Chỉ nạp weights có sẵn rồi inference.
- Engine = thư viện `omnivoice` (cài qua pip). Weights = tải từ HuggingFace.
- **Entry chính: `web_server.py`** (giao diện web FastAPI + frontend tĩnh trong `web/`, mở qua
  `start-ui.bat`). Ngoài ra có `run.py` (CLI argparse). Bản Gradio cũ `app.py` giữ làm tùy chọn,
  KHÔNG còn là UI chính. Tất cả gọi lõi chung `tts_engine.py`.
- Tính năng hiện có: TTS, clone giọng (file/mic), đọc văn bản dài (tự cắt + ghép 1 giọng), tốc độ
  đọc (slider 0.5-2.0x), quản lý giọng mẫu (lưu đúng tên/xóa), lịch sử (nghe inline/xóa), sáng/tối.

## Resource / Link đang dùng

| Thành phần | Nguồn |
|---|---|
| **Model đang dùng** (weights tiếng Việt) | https://huggingface.co/kjanh/KhanhTTS-OmniVoice |
| Engine code (thư viện `omnivoice`) | https://github.com/k2-fsa/OmniVoice + PyPI `omnivoice` |
| Model gốc (đa ngôn ngữ, KhanhTTS fine-tune từ đây) | https://huggingface.co/k2-fsa/OmniVoice |
| Model VN thay thế (nếu cần so sánh) | https://huggingface.co/splendor1811/omnivoice-vietnamese |
| App desktop liên quan (cùng hệ OmniVoice) | https://github.com/debpalash/OmniVoice-Studio |

- **Model mặc định = `g-group-ai-lab/g-omnivoice`** (đổi 2026-08-17; đọc số/chữ chuẩn hơn). KhanhTTS
  thành lựa chọn. Danh sách trong `tts_engine.AVAILABLE_MODELS`; chọn qua dropdown UI hoặc `run.py --model`.
- **g-omnivoice là repo GATED -> cần HuggingFace token.** `hf_token.py` tự tìm token (env HF_TOKEN /
  `$HF_HOME/token` / `~/.cache/huggingface/token`); UI có ô nhập key khi thiếu (`POST /api/hf-token`).
  KhanhTTS public, KHÔNG cần token -> dùng làm lựa chọn an toàn khi không có key.
- KhanhTTS / g-omnivoice đều = fine-tune OmniVoice tiếng Việt; output 24000 Hz; backbone Qwen3-0.6B.

## Tech stack (phiên bản đã cài, đã verify chạy được)

- Python **3.12.0** (trong `.venv`) - KHÔNG dùng Python 3.14 hệ thống (PyTorch chưa hỗ trợ 3.14).
- PyTorch **2.8.0+cu128** + torchaudio 2.8.0+cu128 (CUDA 12.8).
- omnivoice **0.2.1** (nâng từ 0.1.5 ngày 2026-08-17), transformers 5.10.2, numpy 2.4.6, soundfile 0.14.0.
- Web UI chính: **fastapi + uvicorn[standard] + python-multipart** (cài bare vào .venv qua
  `UV_LINK_MODE=copy uv pip install ...`). Frontend là HTML/CSS/JS thuần + font Be Vietnam Pro (local, offline).
- gradio **6.16.0** (chỉ cho bản UI cũ `app.py`, tùy chọn). Project KHÔNG có pyproject.toml/uv.lock -
  đừng tự thêm, đó là quyết định riêng cần hỏi user.
- Package manager: **uv** (không dùng pip/npm trực tiếp).

## RÀNG BUỘC BẮT BUỘC (lesson learned - đừng lặp lại lỗi)

1. **HF cache phải nằm trong project.** `tts_engine.py` tự set `HF_HOME = ./.cache/huggingface`
   ở KHỐI ĐẦU FILE, TRƯỚC khi import omnivoice. Mọi entrypoint (run.py, app.py) phải
   `import tts_engine` trước khi đụng model. Mục đích: model không tải ra `C:\Users\...\.cache`
   mặc định -> dễ xóa, không vương vãi.
2. **GPU yếu: RTX 3050 Ti Laptop, chỉ 4GB VRAM.**
   - Đọc câu ngắn; khi clone luôn truyền `--ref-text` để KHÔNG phải load Whisper (đỡ tốn VRAM).
   - Nếu `CUDA out of memory` -> chạy `--cpu` (chậm nhưng chắc).
3. **uv install dùng `UV_LINK_MODE=copy`** (cache uv ở ổ C:, venv ở D: -> khác filesystem,
   không hardlink được; copy trên đĩa thật thì nhanh, vô hại).
4. **Encoding:** chạy script nên đặt `PYTHONUTF8=1`; `run.py` đã `sys.stdout.reconfigure(utf-8)`
   để in tiếng Việt không lỗi trên console Windows.

## Cách chạy (tóm tắt - chi tiết xem README.md)

```bash
cd /d/source-code/omnivoice-vietnamese
uv run python web_server.py                                                 # UI web FastAPI (hoặc double-click start-ui.bat)
uv run python run.py --text "Câu tiếng Việt." --out outputs/a.wav          # TTS cơ bản (CLI)
uv run python run.py --text "..." --ref refs/mau.wav --ref-text "..." --out outputs/clone.wav  # clone giọng
uv run python run.py --text "..." --speed 0.8 --cpu                         # đọc chậm + ép CPU khi hết VRAM
uv run python -m unittest tests.test_text_splitter                          # unit test (không cần GPU)
uv run python tests/smoke_e2e.py                                            # smoke e2e (GPU, model thật, không mock)
```

Tham số `run.py`: `--text --out --ref --ref-text --steps(16) --speed(1.0) --cpu`.
Web bind `127.0.0.1:7860` (chỉ máy này truy cập được), tuyệt đối KHÔNG bật `share=True`/`0.0.0.0`.
API chính: `POST /api/generate` (multipart), `/api/refs` (GET/DELETE), `/api/save-ref`, `/api/history`,
`/api/audio/{name}`, `/api/progress`, `/api/unload`. Chống path traversal ở mọi chỗ nhận tên file.

## Cấu trúc

```
omnivoice-vietnamese/  (repo GitHub: vietnamese-tts-studio)
├── .venv/                # Python 3.12 + torch + omnivoice + fastapi (~8GB) - KHÔNG commit
├── .cache/huggingface/   # model weights (~3.1GB) - KHÔNG commit, xóa được
├── outputs/              # file .wav sinh ra + sidecar .json metadata - gitignore
├── refs/                 # giọng mẫu để clone - gitignore (file cá nhân)
├── web/                  # FRONTEND: index.html, styles.css, app.js, recorder.js, fonts/*.ttf
├── tests/                # test_text_splitter.py (GPU-free) + smoke_e2e.py (GPU thật)
├── docs/                 # adr/0001 (tự lấy mẫu) + project-changelog.md
├── notebooks/            # voxcpm2-kaggle: chạy VoxCPM2 trên GPU Kaggle (NHÁNH SONG SONG,
│                         # không phải app local - xem changelog 2026-08-18)
├── plans/                # plan nội bộ - gitignore, KHÔNG track
├── web_server.py         # ENTRY CHÍNH: FastAPI serve web/ + API generate/refs/history/...
├── run.py                # CLI mỏng gọi tts_engine
├── tts_engine.py         # lõi model: HF_HOME (đặt đầu file!), load/unload/generate, đổi model, singleton `engine`
├── hf_token.py           # tìm/lưu HF token + nhận diện lỗi 401/gated (cho model g-omnivoice)
├── vietnamese_number_normalizer.py  # nở số/ngày/tiền/% thành chữ tiếng Việt (Miền Bắc) trước khi đọc
├── text_splitter.py      # cắt văn bản tiếng Việt thành đoạn (né viết tắt, số thập phân...)
├── long_text.py          # pipeline văn bản dài: chuẩn hóa số -> tự lấy mẫu (ADR 0001), ghép đoạn, partial, speed
├── history.py            # đặt tên file output (giữ tên gốc), sidecar JSON, liệt kê/xóa
├── app.py app_theme.py app_history_tab.py   # bản UI Gradio CŨ (tùy chọn, không phải UI chính)
├── start-ui.bat          # double-click chạy web_server.py
├── CONTEXT.md  README.md  CLAUDE.md  LICENSE  .gitignore
```

## Cảnh báo / việc còn mở

- **License cần kiểm tra trước khi DÙNG THƯƠNG MẠI:** model card KhanhTTS ghi Apache-2.0 nhưng
  KHÔNG nói rõ license của dataset train. Model VN khác (splendor1811) train trên dataset
  CC-BY-NC-SA (cấm thương mại). => Nếu định kiếm tiền từ giọng sinh ra, phải xác minh/liên hệ tác giả trước.
- Cảnh báo "symlink not supported" lúc tải model là vô hại (Windows tắt symlink) - chỉ tốn thêm disk.
- Biểu cảm phi ngôn ngữ (`[laughter]`, `[sigh]`...) là tính năng của OmniVoice gốc, CHƯA verify
  hoạt động tốt trên bản tiếng Việt KhanhTTS - cần test thực tế rồi nghe.
- **"Mô tả giọng" (voice design / tham số `instruct`: nam/nữ, tuổi, cao độ...) KHÔNG dùng được
  trên KhanhTTS** - đã test 2026-06-08: giới tính nữ/nam ra f0 ~126/130Hz (không đổi giọng); cao độ
  có đổi nhẹ (+47Hz) nhưng không tạo giọng mới hữu ích. Đã gỡ khỏi UI theo yêu cầu user. ĐỪNG thêm
  lại. Muốn đổi giọng (nam/nữ/người cụ thể) -> CHỈ có cách clone bằng file giọng mẫu trong `refs/`.
- Chưa có: batch nhiều file. (Web UI + đọc văn bản dài đã xong 2026-06-08, xem `docs/project-changelog.md`.)
- Giọng mặc định KHÔNG ổn định giữa các lần generate -> văn bản dài dùng cơ chế "tự lấy mẫu"
  (đoạn 1 làm giọng mẫu cho các đoạn sau) - xem `docs/adr/0001`. ĐỪNG bỏ cơ chế này khi refactor.
- **Chất lượng audio văn bản dài (bài học 2026-06-09):**
  - Ghép đoạn phải MƯỢT: mỗi đoạn model đã tự fade + đệm ~0.1s 2 mép; `long_text._join_chunks` cắt
    đệm thừa + chuẩn hoá RMS đều + nghỉ ngắn ~0.16s + cross-fade. ĐỪNG chèn lặng thô (gây "khựng").
  - `num_step` mặc định = 24 (trước 16) cho bớt glitch. Nâng tới 32 KHÔNG tốn thêm VRAM (chỉ chậm
    hơn) - num_step chỉ là số vòng lặp trên cùng tensor. Thứ ngốn VRAM là ĐỘ DÀI đoạn + clone/Whisper.
  - **ĐỪNG cắt câu theo dấu phẩy.** Đã thử 2026-06-09: fix được lỗi "lag/giãn" giữa câu dài NHƯNG
    làm giọng đều đều, mất ngữ điệu tự nhiên (nghe như AI đọc) -> đã GỠ. Điểm mạnh model là đọc
    NGUYÊN CÂU với prosody tự nhiên. `text_splitter` CHỈ cắt theo `. ! ?` + xuống dòng.
  - **GIỌNG MẪU QUYẾT ĐỊNH NHỊP ĐỌC - nguyên nhân chính của "khựng" (xác nhận 2026-08-17).**
    OmniVoice chốt độ dài đầu ra TRƯỚC khi sinh: `số giây = (ký tự câu) x (độ dài mẫu) / (ký tự lời mẫu)`,
    và KHÔNG có token kết thúc -> buộc phải lấp đầy khung đã cấp. Mẫu nhiều khoảng lặng -> model tưởng
    người nói chậm -> cấp dư khung -> nhồi khoảng lặng vào giữa câu = tiếng "khựng khựng".
    => **Giọng mẫu phải nén hết khoảng lặng thừa** (giữ nguyên lời nói thì `ref_text` vẫn khớp).
    Đo thật: mẫu 14.3s/26% lặng -> 11.8s/0% lặng làm output giảm 33% số chỗ ngắt, giảm gần nửa im lặng.
    **Lời mẫu phải gõ ĐÚNG TỪNG CHỮ** - thiếu chữ làm phình phi tuyến (gõ đủ 60% -> dư 56% thời gian).
    Bỏ trống lời mẫu -> Whisper chạy lại cho TỪNG câu (tốn VRAM + sót chữ tiếng Việt).
  - `position_temperature` (5.0 -> 1.0) KHÔNG cải thiện - đã đo, không phải lever. num_step giữ 24.
    TUYỆT ĐỐI KHÔNG quay lại cắt phẩy.
  - **ĐÃ THỬ VÀ LOẠI - đừng mất thời gian làm lại (2026-08-17):** viXTTS (dở hơn), VieNeu-TTS (dở hơn
    + lệch giọng gốc). Khảo sát GitHub: GPT-SoVITS / IndexTTS / CosyVoice / VibeVoice / MegaTTS3 /
    Zonos / Spark-TTS / Orpheus **KHÔNG hỗ trợ tiếng Việt**; Chatterbox có mác "vi" nhưng CER 75%
    (chính nhà phát triển khuyến cáo không dùng); Higgs Audio v3 có tiếng Việt tốt nhưng cần **16GB VRAM**.
    => g-omnivoice vẫn là lựa chọn tốt nhất cho máy 4GB.
- Các thay đổi đợt 2026-06-09 (ghép mượt `_join_chunks` + num_step 24; đã revert cắt phẩy) CHƯA push
  lên GitHub - commit mới nhất trên remote vẫn là `2bf9c48`.
