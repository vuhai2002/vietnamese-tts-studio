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
import vietnamese_number_normalizer
from tts_engine import DEFAULT_TEXT, SAMPLE_RATE, HfAuthError, engine

# Alias ngan cho --model (id day du nam trong tts_engine.AVAILABLE_MODELS).
MODEL_ALIASES = {"gomni": "g-group-ai-lab/g-omnivoice", "khanhtts": "kjanh/KhanhTTS-OmniVoice"}


def build_parser():
    p = argparse.ArgumentParser(
        description="Omnivoice Tieng Viet - TTS tieng Viet (model + cache nam trong folder du an)"
    )
    p.add_argument("--text", default=DEFAULT_TEXT, help="Cau van can doc (giu nguyen dau tieng Viet)")
    p.add_argument("--out", default="outputs/out.wav", help="Duong dan file wav xuat ra")
    p.add_argument("--ref", default=None, help="File am thanh mau 3-10s de clone giong")
    p.add_argument("--ref-text", dest="ref_text", default=None,
                   help="Loi thoai trong file mau (NEN nhap tay de do ton VRAM cho Whisper)")
    p.add_argument("--steps", type=int, default=24,
                   help="So buoc diffusion: it=nhanh/nhe, nhieu=muot hon (mac dinh 24, dai 8-32)")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Toc do doc: <1 cham, >1 nhanh (mac dinh 1.0)")
    p.add_argument("--model", choices=list(MODEL_ALIASES), default="gomni",
                   help="Model: gomni (g-omnivoice, mac dinh, can HF token) | khanhtts (khong can token)")
    p.add_argument("--no-normalize-numbers", dest="normalize_numbers", action="store_false",
                   help="TAT doc so thanh chu (mac dinh BAT: 1.250.000 -> mot trieu hai tram...)")
    p.set_defaults(normalize_numbers=True)
    p.add_argument("--cpu", action="store_true", help="Ep chay bang CPU (cham nhung khong gioi han VRAM)")
    return p


def main():
    args = build_parser().parse_args()

    device, dtype = tts_engine.pick_device(args.cpu)
    model_id = MODEL_ALIASES[args.model]

    # Nở số thành chữ (mặc định) để model đọc "1.250.000" đúng.
    text = vietnamese_number_normalizer.normalize(args.text) if args.normalize_numbers else args.text

    print(f"[i] Thiet bi : {device} | dtype: {dtype}")
    print(f"[i] Model    : {model_id}")
    print(f"[i] Cache HF : {os.environ['HF_HOME']}")
    try:
        engine.ensure_loaded(device, dtype, model_id)
    except HfAuthError as exc:
        print(f"[LOI] {exc}")
        print("      -> Chay: .venv\\Scripts\\hf auth login  (dan token tu https://huggingface.co/settings/tokens)")
        print("      -> Hoac dung --model khanhtts (KhanhTTS public, khong can token).")
        return

    if args.ref:
        print(f"[i] Clone giong tu file mau: {args.ref}")

    print(f"[i] Dang sinh am thanh cho cau: {text!r}")
    # ref_text chỉ có nghĩa khi đi kèm ref (giữ đúng hành vi CLI cũ).
    audio = engine.generate_one(
        text,
        ref_audio=args.ref,
        ref_text=args.ref_text if args.ref else None,
        steps=args.steps,
        speed=args.speed,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), audio, SAMPLE_RATE)
    print(f"[OK] Da luu: {out_path.resolve()}")


if __name__ == "__main__":
    main()
