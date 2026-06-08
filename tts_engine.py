#!/usr/bin/env python3
"""
TTS engine cho KhanhTTS-OmniVoice - phần lõi dùng chung cho CLI (run.py) và UI (app.py).

QUAN TRỌNG: khối HF_HOME bên dưới PHẢI chạy TRƯỚC khi import omnivoice/huggingface_hub,
để toàn bộ cache model nằm trong .cache/huggingface của dự án (không vương ra C:\\Users).
Vì thế mọi entrypoint chỉ cần `import tts_engine` trước khi đụng tới model là an toàn.
"""
import gc
import os
import sys
from pathlib import Path

# --- BẮT BUỘC đặt TRƯỚC khi import omnivoice/huggingface_hub ---
PROJECT_DIR = Path(__file__).resolve().parent
CACHE_DIR = PROJECT_DIR / ".cache" / "huggingface"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(CACHE_DIR))

# Tránh lỗi UnicodeEncodeError khi in tiếng Việt ra console Windows.
# Không được làm crash việc import nếu stdout không hỗ trợ reconfigure.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import torch  # noqa: E402
from omnivoice import OmniVoice  # noqa: E402

MODEL_ID = "kjanh/KhanhTTS-OmniVoice"
SAMPLE_RATE = 24000
DEFAULT_TEXT = "Xin chào, đây là giọng nói tiếng Việt được tạo bởi Omnivoice Tiếng Việt."
OUTPUTS_DIR = PROJECT_DIR / "outputs"
REFS_DIR = PROJECT_DIR / "refs"


def pick_device(force_cpu: bool = False):
    """Chọn (device, dtype): cuda:0 + float16 nếu có GPU và không ép CPU, ngược lại cpu + float32."""
    use_cuda = torch.cuda.is_available() and not force_cpu
    device = "cuda:0" if use_cuda else "cpu"
    dtype = torch.float16 if use_cuda else torch.float32
    return device, dtype


class TtsEngine:
    """Quản lý vòng đời model: lazy load, giữ trong VRAM, unload khi cần, đổi device."""

    def __init__(self):
        self.model = None
        self._device = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    @property
    def current_device(self):
        """Device đang giữ model ("cuda:0"/"cpu") hoặc None nếu chưa load."""
        return self._device

    def ensure_loaded(self, device: str, dtype) -> None:
        """Lazy load model. Nếu đang load ở device khác -> unload rồi load lại."""
        if self.model is not None and self._device != device:
            self.unload()
        if self.model is None:
            print(f"[i] Dang tai model {MODEL_ID} (lan dau tai ~1.2GB tu HuggingFace, cac lan sau dung cache)...")
            self.model = OmniVoice.from_pretrained(MODEL_ID, device_map=device, dtype=dtype)
            self._device = device

    def generate_one(self, text: str, ref_audio=None, ref_text=None, steps: int = 16):
        """Sinh âm thanh cho MỘT đoạn text, trả về mảng 1-D (24000 Hz).

        ref_audio: đường dẫn file giọng mẫu 3-10s (clone giọng); ref_text: lời thoại trong mẫu.
        Giữ fallback TypeError: phòng khi phiên bản omnivoice khác tên tham số num_step.
        """
        if self.model is None:
            raise RuntimeError("Model chua duoc load - goi ensure_loaded() truoc.")
        kwargs = {"text": text, "num_step": steps}
        if ref_audio:
            kwargs["ref_audio"] = ref_audio
        if ref_text:
            kwargs["ref_text"] = ref_text
        try:
            audio = self.model.generate(**kwargs)
        except TypeError:
            kwargs.pop("num_step", None)
            audio = self.model.generate(**kwargs)
        return audio[0]

    def unload(self) -> None:
        """Giải phóng model khỏi RAM/VRAM. An toàn khi gọi lúc chưa load hoặc đang ở CPU."""
        if self.model is not None:
            del self.model
            self.model = None
        self._device = None
        gc.collect()
        self.empty_cache()

    def empty_cache(self) -> None:
        """Dọn cache CUDA (gọi giữa các lần sinh để tránh phân mảnh VRAM). An toàn khi không có GPU."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Singleton dùng chung cho run.py và app.py (1 process chỉ nên có 1 model trong VRAM).
engine = TtsEngine()
