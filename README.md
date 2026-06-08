# Vietnamese TTS Studio

TTS tiếng Việt + nhân bản giọng nói (voice cloning), chạy **offline 100%** trên GPU local.
Nhập văn bản tiếng Việt -> file `.wav`; hoặc đưa giọng mẫu 3-10 giây -> clone giọng đó.
Có **giao diện web** (khuyên dùng) và **CLI**.

> **Đây là công cụ/giao diện sử dụng (consumer app), KHÔNG phải model.** Toàn bộ chất lượng
> giọng nói là công sức của các tác giả model/engine gốc - xem mục [Ghi nhận](#ghi-nhận-credits).

## Tính năng

- Nhập một câu hoặc **cả bài dài** -> tự cắt câu, đọc tuần tự rồi ghép thành **một file liền mạch,
  một giọng duy nhất** (hợp cả GPU VRAM thấp như 4GB).
- **Clone giọng** từ file mẫu hoặc **thu âm micro** ngay trên trình duyệt.
- Quản lý **giọng mẫu** (lưu/xóa) và **lịch sử** file đã sinh (nghe lại / xóa).
- Giao diện web sáng/tối; hoặc dùng CLI cho tự động hóa.

## Yêu cầu

- **Python 3.12** (PyTorch chưa hỗ trợ 3.13/3.14).
- GPU NVIDIA có CUDA (khuyên >= 4GB VRAM). Không có GPU vẫn chạy được bằng **CPU** (chậm hơn).
- [uv](https://github.com/astral-sh/uv) để quản lý môi trường Python.

## Cài đặt

```bash
git clone https://github.com/vuhai2002/vietnamese-tts-studio.git
cd vietnamese-tts-studio

uv venv --python 3.12
# Windows (cache uv ở ổ khác venv): set UV_LINK_MODE=copy
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128   # đổi cu128 theo CUDA của bạn
uv pip install omnivoice soundfile fastapi "uvicorn[standard]" python-multipart
```

Lần chạy đầu sẽ **tự tải model (~3GB)** từ HuggingFace vào thư mục `.cache/` ngay trong dự án
(không vương ra ngoài, muốn xóa chỉ cần xóa `.cache/`).

## Giao diện web (khuyên dùng)

```bash
uv run python web_server.py          # hoặc double-click start-ui.bat (Windows)
```

Trình duyệt tự mở tại `http://127.0.0.1:7860` - **chỉ máy này truy cập được**, không mở ra mạng.
Lần bấm **Đọc** đầu tiên chờ 30-60 giây tải model; các lần sau gần như tức thì (model giữ trong VRAM).

**Tab "Tạo giọng nói":**
- Dán văn bản bất kỳ - một câu hay cả bài đều được. Bài dài tự cắt câu, đọc lần lượt (có thanh
  tiến độ "đang đọc đoạn 3/12...") rồi ghép thành một file liền mạch.
- Muốn clone giọng: mở khối **Giọng mẫu** - chọn file có sẵn trong `refs/`, tải file lên, hoặc
  **thu âm bằng micro**. Nên gõ *Lời mẫu* (đúng câu trong file mẫu) để đỡ tốn VRAM. Bấm
  **Lưu vào refs/** để giữ giọng dùng lần sau, hoặc nút thùng rác để xóa giọng mẫu.
- Hết VRAM giữa chừng? Phần đã đọc xong vẫn được lưu (`..._partial.wav`); bật **Dùng CPU** hoặc
  giảm số bước rồi đọc lại.
- Nút **Giải phóng VRAM**: trả VRAM cho việc khác mà không cần tắt app.

**Tab "Lịch sử":** xem lại các file đã sinh, bấm play để nghe ngay tại dòng, hoặc xóa.

## Dùng CLI

```bash
# TTS cơ bản
uv run python run.py --text "Xin chào các bạn, hôm nay trời đẹp quá." --out outputs/test.wav

# Clone giọng từ file mẫu (nên gõ --ref-text đúng lời trong mẫu để đỡ tốn VRAM)
uv run python run.py --text "Câu đọc bằng giọng mẫu." --ref refs/mau.wav \
  --ref-text "lời thoại có trong mau.wav" --out outputs/clone.wav

# Ép chạy CPU khi hết VRAM
uv run python run.py --text "..." --cpu
```

Tham số `run.py`: `--text` `--out` `--ref` `--ref-text` `--steps`(16) `--cpu`.

## Cấu trúc

```
vietnamese-tts-studio/
├── web_server.py         # Backend FastAPI - phục vụ web + API (giao diện chính)
├── web/                  # Frontend tĩnh (HTML/CSS/JS) + font Be Vietnam Pro
├── run.py                # CLI (terminal)
├── tts_engine.py         # Lõi model dùng chung (load/unload/generate)
├── text_splitter.py      # Cắt văn bản dài thành câu (tiếng Việt)
├── long_text.py          # Pipeline đọc văn bản dài (ghép đoạn, giữ 1 giọng)
├── history.py            # Đặt tên file output + metadata + lịch sử
├── app.py app_theme.py app_history_tab.py   # Bản giao diện Gradio cũ (tùy chọn)
├── tests/                # Unit test (không cần GPU) + smoke test e2e
├── docs/                 # ADR + changelog
├── refs/                 # (tự tạo) bỏ giọng mẫu vào đây - KHÔNG commit
├── outputs/              # (tự tạo) file .wav sinh ra - KHÔNG commit
└── .cache/  .venv/       # model weights + môi trường - KHÔNG commit
```

## Ghi nhận (Credits)

Dự án này chỉ là lớp giao diện/công cụ. Mọi công sức tạo ra giọng nói thuộc về:

- **Model giọng tiếng Việt:** [`kjanh/KhanhTTS-OmniVoice`](https://huggingface.co/kjanh/KhanhTTS-OmniVoice)
  - tác giả **kjanh** (fine-tune ~1.500h tiếng Việt + Anh, output 24kHz, backbone Qwen3-0.6B). License: Apache-2.0.
- **Engine / model gốc:** [`k2-fsa/OmniVoice`](https://github.com/k2-fsa/OmniVoice)
  ([HuggingFace](https://huggingface.co/k2-fsa/OmniVoice)) - **k2-fsa / Xiaomi Corp** (tác giả Han Zhu). License: Apache-2.0.
- **Font:** [Be Vietnam Pro](https://fonts.google.com/specimen/Be+Vietnam+Pro) (SIL Open Font License).

## License

- **Code của repo này:** MIT (xem file [LICENSE](LICENSE)) - ai dùng cũng được.
- **Model + dữ liệu:** theo license của tác giả gốc ở trên (Apache-2.0 cho model/engine).
- **Lưu ý thương mại:** model card KhanhTTS ghi Apache-2.0 nhưng **chưa nói rõ license của dataset
  train**. Nếu dùng giọng sinh ra cho mục đích thương mại, hãy tự xác minh / liên hệ tác giả model trước.
