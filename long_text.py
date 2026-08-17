#!/usr/bin/env python3
"""
Pipeline đọc văn bản dài: cắt đoạn -> sinh tuần tự MỘT giọng -> ghép thành MỘT file.

Đồng nhất giọng (xem docs/adr/0001 + CONTEXT.md mục "Tự lấy mẫu"):
- Người dùng đã chọn giọng mẫu -> dùng giọng đó cho MỌI đoạn.
- Chưa chọn -> đoạn 1 sinh bằng giọng mặc định, rồi chính audio + text của đoạn 1
  làm giọng mẫu cho các đoạn 2..n (không cần Whisper vì lời mẫu = text đoạn 1).

Lỗi giữa chừng (hết VRAM...) là tình huống BÌNH THƯỜNG trên máy 4GB VRAM:
trả về phần đã sinh xong (partial) + vị trí đoạn lỗi để app lưu file và báo người dùng.
"""
import os
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

import vietnamese_number_normalizer
from text_splitter import split_text
from tts_engine import SAMPLE_RATE, engine

# Ghép đoạn cho MƯỢT. Mỗi đoạn model đã tự fade + đệm ~0.1s lặng 2 mép; nếu mình chèn
# thêm lặng thô -> ~0.45s/câu nghe khựng. Nên: cắt đệm thừa, chuẩn hoá âm lượng đều nhau,
# nối bằng khoảng nghỉ tự nhiên ngắn + cross-fade chống click.
GAP_SECONDS = 0.16        # nghỉ tự nhiên giữa câu
XFADE_SECONDS = 0.02      # cross-fade ngắn ở mối nối + 2 mép file (chống click)
TARGET_RMS = 0.12         # mức âm lượng chung -> các câu đều nhau, không nhảy to/nhỏ
_TRIM_THRESH = 0.008      # ngưỡng coi là "lặng" khi cắt mép
_TRIM_KEEP_MS = 25        # chừa lại chút ở mép để không cụt phụ âm


def _trim_edges(audio: np.ndarray) -> np.ndarray:
    """Cắt phần lặng/đệm thừa ở đầu-cuối một đoạn (post-process thêm ~0.1s pad mỗi bên)."""
    mask = np.abs(audio) > _TRIM_THRESH
    if not mask.any():
        return audio
    keep = int(_TRIM_KEEP_MS / 1000 * SAMPLE_RATE)
    start = max(0, int(np.argmax(mask)) - keep)
    end = min(len(audio), len(audio) - int(np.argmax(mask[::-1])) + keep)
    return audio[start:end]


def _norm_rms(audio: np.ndarray) -> np.ndarray:
    """Đưa đoạn về mức âm lượng (RMS) chung để các câu nghe đều nhau."""
    rms = float(np.sqrt(np.mean(audio * audio))) if len(audio) else 0.0
    return audio * (TARGET_RMS / rms) if rms > 1e-5 else audio


def _join_chunks(audios: list[np.ndarray]) -> np.ndarray | None:
    """Ghép các đoạn 1-D: cắt mép -> chuẩn hoá âm lượng -> nối + nghỉ ngắn + cross-fade."""
    chunks = []
    for a in audios:
        c = _trim_edges(np.asarray(a, dtype=np.float32))
        if len(c):
            chunks.append(_norm_rms(c))
    if not chunks:
        return None

    n = int(XFADE_SECONDS * SAMPLE_RATE)
    gap = np.zeros(int(GAP_SECONDS * SAMPLE_RATE), dtype=np.float32)
    out = chunks[0].copy()
    for c in chunks[1:]:
        c = c.copy()
        k = min(n, len(out), len(c))
        if k > 0:
            out[-k:] *= np.linspace(1, 0, k, dtype=np.float32)   # fade-out cuối đoạn trước
            c[:k] *= np.linspace(0, 1, k, dtype=np.float32)      # fade-in đầu đoạn sau
        out = np.concatenate([out, gap, c])

    # Vuốt nhẹ 2 mép file + chống clip.
    k = min(n, len(out) // 2)
    if k > 0:
        out[:k] *= np.linspace(0, 1, k, dtype=np.float32)
        out[-k:] *= np.linspace(1, 0, k, dtype=np.float32)
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    if peak > 0.99:
        out = out * (0.99 / peak)
    return out


def _is_oom(exc: Exception) -> bool:
    """Nhận diện lỗi hết VRAM (omnivoice có thể ném nhiều kiểu khác nhau)."""
    return isinstance(exc, torch.cuda.OutOfMemoryError) or "out of memory" in str(exc).lower()


def generate_long(text: str, ref_audio: str | None = None, ref_text: str | None = None,
                  steps: int = 24, device: str = "cpu", dtype=torch.float32,
                  progress=None, speed: float | None = None, model_id: str | None = None,
                  language: str | None = "Vietnamese", normalize_numbers: bool = True) -> dict:
    """Sinh âm thanh cho văn bản (1 câu hay nhiều đoạn đều đi chung đường này).

    speed: tốc độ đọc áp cho TỪNG đoạn -> cả bài cùng tốc độ.
    model_id: chọn model (None = mặc định g-omnivoice). language: chỉ định ngôn ngữ.
    normalize_numbers: nở số/ngày/tiền thành chữ tiếng Việt trước khi cắt câu (model đọc số đúng hơn).

    Trả về dict:
    - audio:     mảng 1-D 24000 Hz đã ghép, hoặc None nếu chưa sinh được đoạn nào
    - n_chunks:  tổng số đoạn sau khi cắt
    - failed_at: số thứ tự đoạn bị lỗi (1-based), None nếu trọn vẹn
    - partial:   True nếu dừng giữa chừng (audio chỉ chứa các đoạn đã xong)
    """
    # Nở số THÀNH CHỮ trước khi cắt câu, để "1.250.000" không bị cắt và được đọc đúng.
    if normalize_numbers:
        text = vietnamese_number_normalizer.normalize(text)

    chunks = split_text(text)
    if not chunks:
        return {"audio": None, "n_chunks": 0, "failed_at": None, "partial": False}

    engine.ensure_loaded(device, dtype, model_id)

    audios: list[np.ndarray] = []
    failed_at: int | None = None
    active_ref_audio = ref_audio
    active_ref_text = ref_text if ref_audio else None
    temp_ref: Path | None = None  # file tạm chứa đoạn 1 khi tự lấy mẫu

    try:
        for i, chunk in enumerate(chunks):
            if progress is not None:
                progress(i / len(chunks), desc=f"Đang đọc đoạn {i + 1}/{len(chunks)}...")
            try:
                audio = engine.generate_one(chunk, ref_audio=active_ref_audio,
                                            ref_text=active_ref_text, steps=steps, speed=speed,
                                            language=language)
            except (torch.cuda.OutOfMemoryError, RuntimeError) as exc:
                if _is_oom(exc):
                    failed_at = i + 1
                    engine.empty_cache()
                    break
                raise
            audios.append(np.asarray(audio, dtype=np.float32))
            engine.empty_cache()

            # Tự lấy mẫu (ADR 0001): sau đoạn 1, nếu chưa có giọng mẫu thì dùng chính đoạn 1.
            if i == 0 and active_ref_audio is None and len(chunks) > 1:
                fd, tmp_name = tempfile.mkstemp(suffix=".wav", prefix="khanhtts-selfref-")
                os.close(fd)
                temp_ref = Path(tmp_name)
                sf.write(str(temp_ref), audios[0], SAMPLE_RATE)
                active_ref_audio = str(temp_ref)
                active_ref_text = chunk
    finally:
        # Dọn file tạm tự lấy mẫu - không để rác trong thư mục temp.
        if temp_ref is not None:
            temp_ref.unlink(missing_ok=True)

    return {
        "audio": _join_chunks(audios),
        "n_chunks": len(chunks),
        "failed_at": failed_at,
        "partial": failed_at is not None,
    }
