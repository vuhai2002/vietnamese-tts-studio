# Project Changelog

## 2026-08-18 - Notebook Kaggle chạy VoxCPM2 (lựa chọn chất lượng cao, KHÔNG thay app local)

**Thêm `notebooks/voxcpm2-kaggle-clone-giong.ipynb`** - chạy VoxCPM2 trên GPU T4 miễn phí của Kaggle.
Đây là NHÁNH SONG SONG, không đụng gì tới app local (vẫn dùng g-omnivoice, vẫn offline 100%).

**Vì sao cần:** model local bị giới hạn 4GB VRAM nên chỉ chạy được cỡ 0.6 tỷ tham số. VoxCPM2 là
2 tỷ tham số, xuất 48kHz, Apache-2.0 (thương mại thoải mái), và người dùng đánh giá giọng hay hơn
hẳn g-omnivoice. Cần GPU 16GB nên phải chạy trên Kaggle (30 giờ/tuần miễn phí).

**Các bẫy đã xử lý trong notebook (đều tốn thời gian mới tìm ra):**
- T4 là Turing sm_75 KHÔNG hỗ trợ bf16, mà model mặc định bfloat16 -> phải sửa `config.json` sang
  float16 TRƯỚC khi nạp. Không sửa thì crash.
- Cài `--no-deps` (voxcpm kéo theo gradio/funasr/modelscope không dùng tới, cài đủ hỏng môi trường Kaggle).
- `HF_HOME` phải đặt vào `/kaggle/temp` trước khi import huggingface_hub, tránh ăn hạn mức 20GB.
- Tự dọn VRAM + tự chọn GPU trống (chạy lại ô nạp model 2 lần là tràn).
- Lọc tham số theo `inspect.signature` - phiên bản cài thực tế không có `seed` dù tài liệu ghi có.

**Hiểu biết về VoxCPM2 (đọc từ mã nguồn, quan trọng nếu quay lại làm tiếp):**
- Hai chế độ clone KHÁC HẲN nhau:
  - `reference_wav_path` một mình = **chất giọng** (audio không có lời thoại đi kèm) + cho phép
    chỉ thị phong cách `(...)` ở đầu văn bản (phải viết tiếng Anh/Trung).
  - Thêm `prompt_wav_path` + `prompt_text` = **Ultimate Cloning**: giống giọng nhất NHƯNG sao chép
    luôn NHỊP ĐIỆU của mẫu, và TẮT chỉ thị phong cách (chỉ thị bị đọc to thành lời).
- Nhịp đọc đến từ ô `prompt`, chất giọng đến từ ô `reference` - hai ô độc lập trong kiến trúc.
- KHÔNG có tham số `speed`/`rate`/`tempo`/`duration`, KHÔNG hỗ trợ SSML `<break>`. Xuống dòng bị
  xóa (`text.replace("\n", " ")`).
- `normalize=False` là ĐÚNG cho tiếng Việt: bộ chuẩn hóa của nó chọn ngôn ngữ bằng
  `"zh" if contains_chinese else "en"` -> tiếng Việt rơi vào nhánh tiếng Anh, số bị đọc thành tiếng Anh.

**Cách làm chậm KHÔNG gây méo tiếng (bài học đắt giá):**
- SAI: kéo giãn tín hiệu giọng mẫu (`librosa.effects.time_stretch`) - phase vocoder tạo tiếng méo,
  rồi model clone lại luôn cái méo đó. Đã thử, người dùng bác bỏ.
- ĐÚNG: **chỉ giãn các khoảng LẶNG giữa từ** trong file mẫu, giữ nguyên phần có tiếng.
  Đã kiểm chứng: 323.569 mẫu khác 0 giống hệt, năng lượng lệch 1e-13 - chỉ thêm số 0 vào nên
  KHÔNG THỂ gây méo. Notebook có thanh trượt "Giãn lặng mẫu" làm việc này.
- Cách tốt nhất còn lại (chưa làm): thu 10s đọc chậm làm `prompt` (neo nhịp), giữ file cũ làm
  `reference` (neo chất giọng) - cùng một người nên chất giọng không đổi.

## 2026-08-17 (đợt 2) - Ngắt nghỉ theo dấu câu + sửa lỗi cắt câu ở "…"

**Sửa lỗi:**
- `text_splitter` KHÔNG cắt câu tại ký tự "…" (U+2026) vì regex chỉ có `[.!?]`. Văn bản dán từ
  Word/bản dịch hay dùng ký tự này -> đo được một đoạn 174 ký tự dồn thành MỘT câu -> model sinh
  một hơi quá dài -> rè tiếng + ngắt sai nhịp. Đã thêm "…" vào `_SENT_END`.

**Ngắt nghỉ theo loại ranh giới (cải thiện lớn nhất về "có nhịp"):**
- Trước: `_join_chunks` chèn CHUNG một khoảng nghỉ 0.16s cho mọi mối nối -> hết câu và hết đoạn
  nghe y hệt nhau, cả bài trôi tuồn tuột không ra nhịp.
- Nay: `split_text_with_boundaries()` (mới) gắn nhãn `para` / `sent` / `minor` cho từng đoạn;
  `_join_chunks` nghỉ theo `GAP_BY_BOUNDARY` = hết đoạn 0.65s · hết câu 0.32s · cắt kỹ thuật 0.10s.
  Câu quá dài bị bẻ giữa chừng nhận nhãn `minor` (không phải chỗ ngắt thật -> nghỉ rất ngắn).
- `split_text()` GIỮ NGUYÊN chữ ký cũ (trả list chuỗi) để không phá test/smoke test.
- Đo trên một bài tin: ngắt trung bình 243ms -> 373ms (tầm tự nhiên), số chỗ ngắt gần như không đổi
  (24 -> 25) tức KHÔNG thêm ngắt vụn, chỉ kéo dài đúng chỗ ngắt vốn có. Thời lượng +6.5%.

**Điều tra chất lượng (kết quả để lại cho lần sau, không đổi code):**
- **Giọng mẫu quyết định nhịp đọc.** OmniVoice chốt độ dài đầu ra TRƯỚC khi sinh theo công thức
  `số giây = (ký tự câu) x (độ dài mẫu) / (ký tự lời mẫu)` và KHÔNG có token kết thúc -> buộc phải
  lấp đầy. Mẫu nhiều khoảng lặng -> model tưởng người nói chậm -> cấp dư khung -> nhồi khoảng lặng.
  Đo thật: mẫu 14.3s có 26% im lặng -> dư ~21% thời gian mỗi câu.
  Làm sạch mẫu (nén lặng, giữ nguyên lời nói nên `ref_text` vẫn khớp): 14.3s/26% -> 11.8s/0%
  => output giảm 33% số chỗ ngắt, giảm gần một nửa thời lượng im lặng. Áp dụng cho MỌI model clone.
- **Lời mẫu gõ thiếu làm phình phi tuyến**: gõ đủ 80% -> dư 15%; 60% -> dư 56%; 50% -> dư 84%.
  Bỏ trống thì Whisper tự chạy lại cho TỪNG câu (tốn VRAM + dễ sót chữ tiếng Việt).
- `position_temperature` 5.0 -> 1.0: KHÔNG cải thiện (đo: cùng số chỗ ngắt). Không phải lever.
- **Đã thử và loại các model khác**: viXTTS (dở hơn), VieNeu-TTS (dở hơn + lệch giọng gốc).
  Khảo sát GitHub: GPT-SoVITS/IndexTTS/CosyVoice/VibeVoice/MegaTTS3/Zonos/Spark-TTS **không hỗ trợ
  tiếng Việt**; Chatterbox có mác "vi" nhưng CER 75% (nhà phát triển khuyến cáo không dùng);
  Higgs Audio v3 có tiếng Việt tốt nhưng cần 16GB VRAM. => g-omnivoice vẫn là lựa chọn tốt nhất
  cho máy 4GB. ĐỪNG mất thời gian thử lại các model này.

## 2026-08-17 - Nâng engine 0.2.1 + g-omnivoice mặc định + đọc số thành chữ

**Engine:**
- Nâng `omnivoice` 0.1.5 -> **0.2.1** (chỉ đổi 1 gói, GIỮ NGUYÊN torch 2.8.0+cu128). API 0.2.1:
  `num_step` chuyển vào generation config (vẫn nhận qua `**kwargs`), thêm `language`, `normalize_text`,
  `voice_clone_prompt`, `audio_chunk_duration`/`threshold`, `pad_duration`/`fade_duration`.

**Model (đổi mặc định + chọn được):**
- Mặc định giờ là **`g-group-ai-lab/g-omnivoice`** (đọc số/chữ chuẩn hơn KhanhTTS - WER thấp hơn ~30%
  theo benchmark tác giả + nghe A/B cùng giọng xác nhận). **KhanhTTS thành lựa chọn** (dropdown UI / `--model`).
- g-omnivoice là repo **GATED** -> cần HuggingFace token. `hf_token.py` (mới): tìm token (env/file mặc định),
  lưu token, nhận diện lỗi 401/gated. `tts_engine`: bỏ hardcode MODEL_ID -> `AVAILABLE_MODELS` +
  `ensure_loaded(model_id)` (đổi model -> reload) + `HfAuthError`.
- UI: dropdown chọn model + panel nhập HF key khi thiếu/sai key (`POST /api/hf-token`), tự thử lại sau khi lưu.
  CLI: `--model gomni|khanhtts`. Thiếu key -> báo + hướng dẫn thay vì lỗi khó hiểu.

**Đọc số thành chữ (số tiếng Việt):**
- `vietnamese_number_normalizer.py` (mới) + `tests/test_vietnamese_number_normalizer.py`: nở số/thập phân/
  phần trăm/năm thành chữ Miền Bắc. VD `1.250.000` -> "một triệu hai trăm năm mươi nghìn"; `3,5%` -> "ba phẩy
  năm phần trăm"; `2026` -> "hai nghìn không trăm hai mươi sáu". (`normalize_text` built-in của omnivoice
  KHÔNG xử lý số tiếng Việt - đã kiểm chứng.)
- Áp trong `long_text` TRƯỚC khi cắt câu; toggle "Đọc số thành chữ" (mặc định BẬT) + cờ CLI `--no-normalize-numbers`.

**Chất lượng:**
- `language="Vietnamese"` mặc định trong lời gọi generate (nghe tự nhiên hơn - đã xác nhận).
- Điều tra lỗi lag câu dài: XÁC NHẬN do **sampling ngẫu nhiên** (3 lần sinh cùng câu ra waveform/khoảng lặng
  khác nhau), KHÔNG phải lỗi hệ thống -> không config nào sửa dứt điểm; num_step giữ 24.

**Verify:** 32 unit test pass, smoke e2e pass (g-omnivoice), API model/token pass, đổi model g-omnivoice<->KhanhTTS pass.

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
