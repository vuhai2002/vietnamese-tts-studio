#!/usr/bin/env python3
"""
Smoke test end-to-end trên model THẬT (không mock) - chạy thủ công khi cần xác nhận wiring:

    uv run python tests/smoke_e2e.py          # GPU (mặc định nếu có)
    uv run python tests/smoke_e2e.py --cpu    # ép CPU khi GPU bận/hết VRAM

GPU-bound nên KHÔNG nằm trong unittest suite (suite unit phải chạy được không cần GPU).
Câu test cố tình NGẮN để vừa 4GB VRAM - smoke kiểm tra WIRING giữa các module,
không kiểm tra chất lượng giọng (chất lượng nghe bằng tai qua UI).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Cho phép chạy từ root dự án lẫn từ trong tests/.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import soundfile as sf  # noqa: E402

import tts_engine  # noqa: E402  (set HF_HOME truoc khi dung model)
from tts_engine import SAMPLE_RATE, engine  # noqa: E402
import long_text  # noqa: E402
import history  # noqa: E402


def main() -> int:
    force_cpu = "--cpu" in sys.argv
    device, dtype = tts_engine.pick_device(force_cpu)
    print(f"[smoke] device={device} | dtype={dtype}")

    # 1. Một câu ngắn qua engine (đường cơ bản nhất).
    engine.ensure_loaded(device, dtype)
    audio_single = engine.generate_one("Xin chào.", steps=12)
    assert audio_single is not None and len(audio_single) > 0, "generate_one tra ve rong"
    print(f"[smoke] 1) cau don OK ({len(audio_single) / SAMPLE_RATE:.1f}s)")

    # 2. Văn bản 3 câu KHÔNG giọng mẫu -> bắt buộc đi đường tự lấy mẫu (ADR 0001).
    text = ("Hôm nay trời đẹp quá. Chúng ta cùng đi dạo công viên nhé. "
            "Nhớ mang theo nước uống đầy đủ.")
    result = long_text.generate_long(text, steps=12, device=device, dtype=dtype)
    assert result["partial"] is False, f"pipeline bao partial: {result}"
    assert result["failed_at"] is None, f"failed_at phai None: {result}"
    assert result["n_chunks"] >= 2, f"van ban phai tach >= 2 doan, duoc {result['n_chunks']}"
    assert len(result["audio"]) > len(audio_single), "audio ghep phai dai hon 1 cau don"
    print(f"[smoke] 2) van ban dai OK ({result['n_chunks']} doan, "
          f"{len(result['audio']) / SAMPLE_RATE:.1f}s)")

    # 3. Lưu wav + sidecar, round-trip phải giữ nguyên dấu tiếng Việt.
    wav_path, json_path = history.build_output_paths(text)
    sf.write(str(wav_path), result["audio"], SAMPLE_RATE)
    history.write_sidecar(json_path, {
        "text": text, "ref_voice": None, "ref_text": None, "steps": 12,
        "device": device, "created": datetime.now().isoformat(timespec="seconds"),
        "sample_rate": SAMPLE_RATE, "n_chunks": result["n_chunks"],
        "partial": result["partial"], "failed_at": result["failed_at"],
        "wav": wav_path.name,
    })
    assert wav_path.exists() and json_path.exists(), "thieu wav hoac sidecar"
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    assert meta["text"] == text, "text trong sidecar khac ban goc (mat dau tieng Viet?)"
    entries = history.list_history()
    assert entries and entries[0]["wav"] == wav_path.name, "entry moi phai dung dau lich su"
    print(f"[smoke] 3) sidecar + lich su OK: {wav_path.name}")

    # 4. Giải phóng VRAM.
    engine.unload()
    assert engine.is_loaded is False, "unload xong van bao is_loaded"
    print("[smoke] 4) unload OK")

    print("[smoke] ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
