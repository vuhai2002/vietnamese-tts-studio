#!/usr/bin/env python3
"""
Omnivoice Tieng Viet runner - TTS tieng Viet + voice cloning, chay offline.

CLI mỏng: toàn bộ logic model nằm trong tts_engine.py (dùng chung với app.py).
`import tts_engine` phải đứng trước mọi thứ đụng tới omnivoice vì chính nó set
HF_HOME vào .cache/huggingface của dự án (xem đầu file tts_engine.py).
"""
import argparse
import os
from pathlib import Path

import soundfile as sf

import tts_engine
from tts_engine import DEFAULT_TEXT, SAMPLE_RATE, engine


def build_parser():
    p = argparse.ArgumentParser(
        description="Omnivoice Tieng Viet - TTS tieng Viet (model + cache nam trong folder du an)"
    )
    p.add_argument("--text", default=DEFAULT_TEXT, help="Cau van can doc (giu nguyen dau tieng Viet)")
    p.add_argument("--out", default="outputs/out.wav", help="Duong dan file wav xuat ra")
    p.add_argument("--ref", default=None, help="File am thanh mau 3-10s de clone giong")
    p.add_argument("--ref-text", dest="ref_text", default=None,
                   help="Loi thoai trong file mau (NEN nhap tay de do ton VRAM cho Whisper)")
    p.add_argument("--steps", type=int, default=16,
                   help="So buoc diffusion: it=nhanh/nhe (16), nhieu=muot hon (32)")
    p.add_argument("--cpu", action="store_true", help="Ep chay bang CPU (cham nhung khong gioi han VRAM)")
    return p


def main():
    args = build_parser().parse_args()

    device, dtype = tts_engine.pick_device(args.cpu)

    print(f"[i] Thiet bi : {device} | dtype: {dtype}")
    print(f"[i] Cache HF : {os.environ['HF_HOME']}")
    engine.ensure_loaded(device, dtype)

    if args.ref:
        print(f"[i] Clone giong tu file mau: {args.ref}")

    print(f"[i] Dang sinh am thanh cho cau: {args.text!r}")
    # ref_text chỉ có nghĩa khi đi kèm ref (giữ đúng hành vi CLI cũ).
    audio = engine.generate_one(
        args.text,
        ref_audio=args.ref,
        ref_text=args.ref_text if args.ref else None,
        steps=args.steps,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), audio, SAMPLE_RATE)
    print(f"[OK] Da luu: {out_path.resolve()}")


if __name__ == "__main__":
    main()
