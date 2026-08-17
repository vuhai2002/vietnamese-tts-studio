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

import hf_token  # noqa: E402  (import sau khi HF_HOME set - hf_token doc env luc goi)

# Model mặc định = g-omnivoice (đọc số/chữ tốt hơn KhanhTTS theo benchmark + nghe thử 2026-08).
# Repo GATED nên cần HF token (xem hf_token.py). KhanhTTS public, không cần token -> để làm lựa chọn.
DEFAULT_MODEL_ID = "g-group-ai-lab/g-omnivoice"
AVAILABLE_MODELS = {
    "g-group-ai-lab/g-omnivoice": {"label": "g-omnivoice (mặc định)", "gated": True},
    "kjanh/KhanhTTS-OmniVoice": {"label": "KhanhTTS (không cần key)", "gated": False},
}
MODEL_ID = DEFAULT_MODEL_ID  # giữ tên cũ cho tương thích
DEFAULT_LANGUAGE = "Vietnamese"  # chỉ định ngôn ngữ -> phát âm tự nhiên hơn (đã nghe xác nhận)
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


class HfAuthError(RuntimeError):
    """Model gated cần HF token nhưng chưa có / không hợp lệ - UI bắt lỗi này để hiện ô nhập key."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(f"Model '{model_id}' cần HuggingFace token (repo gated).")


class TtsEngine:
    """Quản lý vòng đời model: lazy load, giữ trong VRAM, unload khi cần, đổi device/đổi model."""

    def __init__(self):
        self.model = None
        self._device = None
        self._model_id = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    @property
    def current_device(self):
        """Device đang giữ model ("cuda:0"/"cpu") hoặc None nếu chưa load."""
        return self._device

    @property
    def current_model(self):
        """Model id đang giữ trong VRAM, hoặc None nếu chưa load."""
        return self._model_id

    def ensure_loaded(self, device: str, dtype, model_id: str | None = None) -> None:
        """Lazy load model. Đổi device HOẶC đổi model_id -> unload rồi load lại.

        Model gated (g-omnivoice) mà thiếu/sai token -> raise HfAuthError để UI hiện ô nhập key.
        """
        model_id = model_id or DEFAULT_MODEL_ID
        if self.model is not None and (self._device != device or self._model_id != model_id):
            self.unload()
        if self.model is None:
            gated = AVAILABLE_MODELS.get(model_id, {}).get("gated", False)
            if gated:
                hf_token.resolve_token()  # tìm token (env / file) -> set HF_TOKEN cho hub
            print(f"[i] Dang tai model {model_id} (lan dau tai vai GB tu HuggingFace, cac lan sau dung cache)...")
            try:
                self.model = OmniVoice.from_pretrained(model_id, device_map=device, dtype=dtype)
            except Exception as exc:
                if gated and hf_token.is_auth_error(exc):
                    raise HfAuthError(model_id) from exc
                raise
            self._device = device
            self._model_id = model_id

    def generate_one(self, text: str, ref_audio=None, ref_text=None, steps: int = 24,
                     speed: float | None = None, language: str | None = DEFAULT_LANGUAGE):
        """Sinh âm thanh cho MỘT đoạn text, trả về mảng 1-D (24000 Hz).

        ref_audio: đường dẫn file giọng mẫu 3-10s (clone giọng); ref_text: lời thoại trong mẫu.
        speed: tốc độ đọc (>1 nhanh, <1 chậm); None/1.0 = mặc định. Áp cho cả giọng mặc định lẫn clone.
        language: chỉ định ngôn ngữ (mặc định "Vietnamese") -> phát âm tự nhiên hơn; None = tự đoán.
        Giữ fallback TypeError: phòng khi phiên bản omnivoice khác tên tham số num_step.
        """
        if self.model is None:
            raise RuntimeError("Model chua duoc load - goi ensure_loaded() truoc.")
        kwargs = {"text": text, "num_step": steps}
        if language:
            kwargs["language"] = language
        if ref_audio:
            kwargs["ref_audio"] = ref_audio
        if ref_text:
            kwargs["ref_text"] = ref_text
        if speed and speed != 1.0:
            kwargs["speed"] = speed
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
        self._model_id = None
        gc.collect()
        self.empty_cache()

    def empty_cache(self) -> None:
        """Dọn cache CUDA (gọi giữa các lần sinh để tránh phân mảnh VRAM). An toàn khi không có GPU."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Singleton dùng chung cho run.py và app.py (1 process chỉ nên có 1 model trong VRAM).
engine = TtsEngine()
