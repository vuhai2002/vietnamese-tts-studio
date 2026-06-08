#!/usr/bin/env python3
"""
Backend FastAPI cho Omnivoice Tiếng Việt - phục vụ web tĩnh + API sinh giọng nói.

Chạy: uv run python web_server.py  (hoặc double-click start-ui.bat)
-> mở http://127.0.0.1:7860 (chỉ máy này).

`import tts_engine` đứng đầu để set HF_HOME trước khi đụng omnivoice. Toàn bộ lõi
(tts_engine, long_text, history) tái dùng y nguyên từ bản CLI/Gradio.
"""
import tts_engine  # noqa: F401  (set HF_HOME khi import - giữ dòng này đầu tiên)
from tts_engine import OUTPUTS_DIR, REFS_DIR, SAMPLE_RATE, engine, pick_device

import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import history
import long_text

WEB_DIR = Path(__file__).resolve().parent / "web"
REF_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg")

app = FastAPI(title="Omnivoice Tiếng Việt")

# Sinh tuần tự (4GB VRAM, 1 người dùng): chỉ 1 lần generate chạy tại một thời điểm.
_gen_lock = threading.Lock()
_progress = {"running": False, "frac": 0.0, "desc": ""}


def _set_progress(frac: float, desc: str = "") -> None:
    _progress.update(running=True, frac=float(frac), desc=desc)


def list_refs() -> list[str]:
    if not REFS_DIR.exists():
        return []
    return sorted(p.name for p in REFS_DIR.iterdir() if p.suffix.lower() in REF_EXTENSIONS)


@app.get("/api/refs")
async def api_refs():
    return {"refs": list_refs()}


@app.get("/api/progress")
async def api_progress():
    return _progress


@app.get("/api/history")
async def api_history():
    return {"items": history.list_history()}


@app.post("/api/unload")
async def api_unload():
    await run_in_threadpool(engine.unload)
    return {"ok": True, "message": "Đã giải phóng VRAM. Lần đọc kế tiếp sẽ tải lại model."}


@app.delete("/api/history/{name}")
async def api_delete_history(name: str):
    try:
        history.delete_entry(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@app.get("/api/audio/{name}")
async def api_audio(name: str):
    path = OUTPUTS_DIR / Path(name).name  # chặn path traversal
    if not path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file.")
    return FileResponse(str(path), media_type="audio/wav")


async def _save_upload(upload: UploadFile, dest_dir: Path, prefix: str) -> Path:
    """Lưu file tải lên với tên timestamp - dùng cho file TẠM khi clone (tên không quan trọng)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "ref.wav").suffix.lower() or ".wav"
    dest = dest_dir / f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{suffix}"
    dest.write_bytes(await upload.read())
    return dest


def _safe_ref_name(filename: str | None) -> str:
    """GIỮ NGUYÊN tên file gốc cho refs/ - chỉ bỏ ký tự cấm Windows + chống trùng tên."""
    raw = Path(filename or "giong-mau.wav").name              # chặn path traversal
    raw = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", raw).strip(" .") or "giong-mau.wav"
    if not Path(raw).suffix:
        raw += ".wav"
    base, ext = Path(raw).stem, Path(raw).suffix
    candidate, n = raw, 2
    while (REFS_DIR / candidate).exists():                     # trùng -> thêm -2, -3...
        candidate = f"{base}-{n}{ext}"
        n += 1
    return candidate


@app.post("/api/save-ref")
async def api_save_ref(ref_file: UploadFile = File(...)):
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    dest = REFS_DIR / _safe_ref_name(ref_file.filename)       # giữ tên gốc
    dest.write_bytes(await ref_file.read())
    return {"name": dest.name, "refs": list_refs()}


@app.delete("/api/refs/{name}")
async def api_delete_ref(name: str):
    safe = Path(name).name                                    # chặn path traversal
    if not safe or safe != name or Path(safe).suffix.lower() not in REF_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Tên giọng mẫu không hợp lệ.")
    (REFS_DIR / safe).unlink(missing_ok=True)
    return {"ok": True, "refs": list_refs()}


@app.post("/api/generate")
async def api_generate(
    text: str = Form(...),
    ref_name: str = Form(""),
    ref_text: str = Form(""),
    steps: int = Form(16),
    speed: float = Form(1.0),
    use_cpu: bool = Form(False),
    ref_file: UploadFile | None = File(None),
):
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Hãy nhập văn bản cần đọc.")
    if not _gen_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Đang sinh âm thanh khác, vui lòng đợi.")

    tmp_ref: Path | None = None
    try:
        _set_progress(0.0, "Chuẩn bị...")
        ref_audio = None
        if ref_file is not None:
            tmp_ref = await _save_upload(ref_file, Path(tempfile.gettempdir()), "omnivoice-ref")
            ref_audio = str(tmp_ref)
        elif ref_name:
            candidate = REFS_DIR / Path(ref_name).name
            if candidate.exists():
                ref_audio = str(candidate)

        device, dtype = pick_device(bool(use_cpu))
        result = await run_in_threadpool(
            long_text.generate_long, text, ref_audio,
            (ref_text.strip() or None) if ref_audio else None,
            int(steps), device, dtype, _set_progress, float(speed),
        )
        if result["audio"] is None:
            raise HTTPException(status_code=500,
                                detail=f"Lỗi ngay đoạn 1/{result['n_chunks']} (hết VRAM?). "
                                       "Hãy bật 'Dùng CPU' hoặc giảm số bước.")

        wav_path, json_path = history.build_output_paths(text, partial=result["partial"])
        sf.write(str(wav_path), result["audio"], SAMPLE_RATE)
        history.write_sidecar(json_path, {
            "text": text, "ref_voice": ref_audio, "ref_text": ref_text.strip() or None,
            "steps": int(steps), "speed": float(speed), "device": device,
            "created": datetime.now().isoformat(timespec="seconds"),
            "sample_rate": SAMPLE_RATE, "n_chunks": result["n_chunks"],
            "partial": result["partial"], "failed_at": result["failed_at"], "wav": wav_path.name,
        })
        return {
            "wav": wav_path.name, "url": f"/api/audio/{wav_path.name}",
            "partial": result["partial"], "failed_at": result["failed_at"],
            "n_chunks": result["n_chunks"],
        }
    finally:
        _progress.update(running=False, frac=1.0, desc="")
        if tmp_ref is not None:
            tmp_ref.unlink(missing_ok=True)
        _gen_lock.release()


# Phục vụ web tĩnh ở "/" - đăng ký SAU các route /api để API được ưu tiên khớp.
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


if __name__ == "__main__":
    import threading
    import webbrowser

    url = "http://127.0.0.1:7860"
    # Tự mở browser sau khi server kịp khởi động (giống trải nghiệm double-click trước đây).
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"[i] Omnivoice Tiếng Việt - mở {url}")
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")
