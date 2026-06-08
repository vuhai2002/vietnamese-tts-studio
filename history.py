#!/usr/bin/env python3
"""
Quản lý file output + lịch sử sinh âm thanh: đặt tên file, sidecar JSON, liệt kê, xóa.

Mỗi file .wav sinh ra có 1 file .json cùng tên nằm cạnh (sidecar) chứa metadata:
text đầy đủ (GIỮ NGUYÊN dấu tiếng Việt), giọng mẫu, steps, device, thời điểm...
Không dùng database - xóa folder outputs/ là sạch (triết lý "xóa folder là xong" của dự án).
"""
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from tts_engine import OUTPUTS_DIR

DEFAULT_SLUG = "khong-tieu-de"


def slugify(text: str, max_words: int = 6) -> str:
    """Tạo slug ASCII cho TÊN FILE từ vài từ đầu của văn bản.

    LƯU Ý: đây là chỗ DUY NHẤT trong dự án được phép bỏ dấu tiếng Việt - vì slug
    chỉ là token trong tên file (an toàn filesystem). Văn bản đầy đủ CÓ DẤU luôn
    nằm trong sidecar JSON và hiển thị trên UI. Đừng tái dùng hàm này cho chữ hiển thị.
    """
    words = text.strip().split()[:max_words]
    raw = " ".join(words).lower()
    raw = raw.replace("đ", "d")  # chữ đ không tách được dấu bằng NFD nên thay riêng
    raw = unicodedata.normalize("NFD", raw)
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")  # bỏ dấu thanh/mũ
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return raw or DEFAULT_SLUG


def build_output_paths(text: str, partial: bool = False) -> tuple[Path, Path]:
    """Sinh cặp đường dẫn (wav, json): outputs/YYYYMMDD-HHMM_<slug>(_partial).wav.

    Trùng tên (sinh nhiều lần trong cùng một phút) -> tự thêm -2, -3...
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    suffix = "_partial" if partial else ""
    base = f"{stamp}_{slugify(text)}{suffix}"
    candidate = base
    counter = 2
    while (OUTPUTS_DIR / f"{candidate}.wav").exists() or (OUTPUTS_DIR / f"{candidate}.json").exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return OUTPUTS_DIR / f"{candidate}.wav", OUTPUTS_DIR / f"{candidate}.json"


def write_sidecar(json_path: Path, meta: dict) -> None:
    """Ghi metadata cạnh file wav. ensure_ascii=False để text tiếng Việt giữ nguyên dấu."""
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def list_history() -> list[dict]:
    """Đọc mọi sidecar trong outputs/, trả về danh sách mới nhất trước.

    Sidecar hỏng -> bỏ qua (không làm sập tab Lịch sử).
    File wav mồ côi (không có json, ví dụ file regression cũ) -> vẫn liệt kê dòng tối thiểu.
    """
    if not OUTPUTS_DIR.exists():
        return []
    entries: list[dict] = []
    seen_wavs: set[str] = set()
    for json_path in sorted(OUTPUTS_DIR.glob("*.json")):
        try:
            with open(json_path, encoding="utf-8") as f:
                meta = json.load(f)
            if not isinstance(meta, dict):
                continue
        except (json.JSONDecodeError, OSError):
            continue
        meta.setdefault("wav", json_path.with_suffix(".wav").name)
        meta.setdefault("created", "")
        meta.setdefault("text", "")
        entries.append(meta)
        seen_wavs.add(meta["wav"])
    for wav_path in OUTPUTS_DIR.glob("*.wav"):
        if wav_path.name not in seen_wavs:
            entries.append({
                "wav": wav_path.name,
                "created": datetime.fromtimestamp(wav_path.stat().st_mtime).isoformat(timespec="seconds"),
                "text": "(không có metadata)",
                "ref_voice": None,
            })
    entries.sort(key=lambda m: m.get("created") or "", reverse=True)
    return entries


def delete_entry(wav_basename: str) -> None:
    """Xóa file wav + sidecar tương ứng trong outputs/.

    Chỉ chấp nhận TÊN FILE trần - chặn path traversal kiểu "..\\x.wav" (dù là tool local).
    """
    name = Path(wav_basename).name
    if not name or name != wav_basename:
        raise ValueError(f"Tên file không hợp lệ: {wav_basename!r}")
    wav_path = OUTPUTS_DIR / name
    wav_path.unlink(missing_ok=True)
    wav_path.with_suffix(".json").unlink(missing_ok=True)
