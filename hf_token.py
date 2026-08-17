#!/usr/bin/env python3
"""
Quản lý HuggingFace token cho model GATED (g-omnivoice cần đăng nhập mới tải được).

- `resolve_token()`: tìm token (env HF_TOKEN -> $HF_HOME/token -> ~/.cache/huggingface/token),
  set vào os.environ để huggingface_hub tự dùng. Nhờ vậy nếu user đã `hf auth login` (token nằm
  ở thư mục mặc định) thì app vẫn tải được, dù HF_HOME đã trỏ vào .cache trong project.
- `save_token()`: lưu token do user nhập trên UI vào $HF_HOME/token (nơi hub tự đọc) + set env ngay.
- `is_auth_error()`: nhận diện lỗi 401/gated để UI hiện ô nhập key.

Phải import SAU khi HF_HOME đã được set (tts_engine set ở đầu file) - các hàm đọc env lúc gọi.
"""
import os
from pathlib import Path

# Link để hướng dẫn user lấy token khi thiếu key.
TOKEN_HELP_URL = "https://huggingface.co/settings/tokens"


def _project_token_path() -> Path | None:
    """Đường dẫn token trong project cache ($HF_HOME/token) - nơi huggingface_hub tự đọc."""
    hf_home = os.environ.get("HF_HOME")
    return Path(hf_home) / "token" if hf_home else None


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    proj = _project_token_path()
    if proj:
        paths.append(proj)
    paths.append(Path.home() / ".cache" / "huggingface" / "token")  # nơi `hf auth login` lưu mặc định
    return paths


def resolve_token() -> str | None:
    """Trả token nếu tìm được, đồng thời set HF_TOKEN vào env cho tiến trình hiện tại."""
    tok = os.environ.get("HF_TOKEN")
    if tok and tok.strip():
        return tok.strip()
    for p in _candidate_paths():
        try:
            if p.exists():
                t = p.read_text(encoding="utf-8").strip()
                if t:
                    os.environ["HF_TOKEN"] = t
                    return t
        except OSError:
            pass
    return None


def has_token() -> bool:
    return bool(resolve_token())


def save_token(token: str) -> None:
    """Lưu token user nhập vào $HF_HOME/token + set env ngay (áp dụng cho lần tải kế tiếp)."""
    token = (token or "").strip()
    if not token:
        raise ValueError("Token rỗng.")
    dest = _project_token_path() or (Path.home() / ".cache" / "huggingface" / "token")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(token, encoding="utf-8")
    os.environ["HF_TOKEN"] = token


def is_auth_error(exc: Exception) -> bool:
    """True nếu lỗi do thiếu/sai token khi tải repo gated (401, Gated, restricted...)."""
    if type(exc).__name__ == "GatedRepoError":
        return True
    s = str(exc).lower()
    markers = ("gated", "401", "restricted", "must have access",
               "authenticated to access", "unauthorized", "you must be authenticated")
    return any(m in s for m in markers)
