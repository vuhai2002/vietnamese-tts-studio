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

from text_splitter import split_text
from tts_engine import SAMPLE_RATE, engine

SILENCE_SECONDS = 0.25  # khoảng lặng giữa hai đoạn - chỉnh ở đây nếu nghe dồn/rời quá


def _join_with_silence(audios: list[np.ndarray]) -> np.ndarray:
    """Ghép các đoạn audio 1-D, chèn khoảng lặng GIỮA các đoạn (không thêm đầu/cuối)."""
    silence = np.zeros(int(SILENCE_SECONDS * SAMPLE_RATE), dtype=np.float32)
    parts: list[np.ndarray] = []
    for i, audio in enumerate(audios):
        if i > 0:
            parts.append(silence)
        parts.append(audio)
    return np.concatenate(parts)


def _is_oom(exc: Exception) -> bool:
    """Nhận diện lỗi hết VRAM (omnivoice có thể ném nhiều kiểu khác nhau)."""
    return isinstance(exc, torch.cuda.OutOfMemoryError) or "out of memory" in str(exc).lower()


def generate_long(text: str, ref_audio: str | None = None, ref_text: str | None = None,
                  steps: int = 16, device: str = "cpu", dtype=torch.float32,
                  progress=None, speed: float | None = None) -> dict:
    """Sinh âm thanh cho văn bản (1 câu hay nhiều đoạn đều đi chung đường này).

    speed: tốc độ đọc áp cho TỪNG đoạn -> cả bài cùng tốc độ.

    Trả về dict:
    - audio:     mảng 1-D 24000 Hz đã ghép, hoặc None nếu chưa sinh được đoạn nào
    - n_chunks:  tổng số đoạn sau khi cắt
    - failed_at: số thứ tự đoạn bị lỗi (1-based), None nếu trọn vẹn
    - partial:   True nếu dừng giữa chừng (audio chỉ chứa các đoạn đã xong)
    """
    chunks = split_text(text)
    if not chunks:
        return {"audio": None, "n_chunks": 0, "failed_at": None, "partial": False}

    engine.ensure_loaded(device, dtype)

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
                                            ref_text=active_ref_text, steps=steps, speed=speed)
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
        "audio": _join_with_silence(audios) if audios else None,
        "n_chunks": len(chunks),
        "failed_at": failed_at,
        "partial": failed_at is not None,
    }
