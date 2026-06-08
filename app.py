#!/usr/bin/env python3
"""
Giao diện web Gradio cho Omnivoice Tiếng Việt - chạy local, 1 người dùng.

Khởi động: double-click start-ui.bat hoặc `uv run python app.py`
-> mở browser tại http://127.0.0.1:7860 (chỉ máy này truy cập được).

QUAN TRỌNG: `import tts_engine` phải đứng TRƯỚC mọi import khác đụng tới model,
vì chính nó set HF_HOME vào .cache/huggingface của dự án.
"""
import tts_engine  # noqa: F401  (set HF_HOME ngay khi import - giữ dòng này đầu tiên)
from tts_engine import REFS_DIR, SAMPLE_RATE, engine, pick_device

import shutil
from datetime import datetime
from pathlib import Path

import gradio as gr
import soundfile as sf

import app_history_tab
import app_theme
import history
import long_text

REF_EXTENSIONS = (".wav", ".mp3", ".flac")


def list_refs() -> list[str]:
    """Liệt kê tên file giọng mẫu có sẵn trong refs/."""
    if not REFS_DIR.exists():
        return []
    return sorted(p.name for p in REFS_DIR.iterdir() if p.suffix.lower() in REF_EXTENSIONS)


def _resolve_ref(dd_ref: str | None, audio_ref: str | None) -> str | None:
    """Chọn giọng mẫu: file vừa tải lên/thu âm ưu tiên hơn lựa chọn trong dropdown."""
    if audio_ref:
        return audio_ref
    if dd_ref:
        path = REFS_DIR / dd_ref
        if path.exists():
            return str(path)
    return None


def on_generate(text, dd_ref, audio_ref, ref_text, steps, use_cpu, progress=gr.Progress()):
    """Sinh âm thanh: 1 câu hay cả bài đều qua pipeline văn bản dài (long_text)."""
    text = (text or "").strip()
    if not text:
        raise gr.Error("Hãy nhập văn bản cần đọc.")

    ref_path = _resolve_ref(dd_ref, audio_ref)
    ref_words = (ref_text or "").strip() or None

    device, dtype = pick_device(bool(use_cpu))
    if not engine.is_loaded or engine.current_device != device:
        progress(0.0, desc="Đang tải model (lần đầu mất 30-60 giây)...")

    try:
        result = long_text.generate_long(
            text,
            ref_audio=ref_path,
            ref_text=ref_words if ref_path else None,
            steps=int(steps),
            device=device,
            dtype=dtype,
            progress=progress,
        )
    except RuntimeError as exc:
        # OOM giữa các đoạn đã được pipeline xử lý; đây là OOM lúc TẢI model.
        if "out of memory" in str(exc).lower():
            engine.empty_cache()
            raise gr.Error("Hết VRAM khi tải model. Hãy bật 'Dùng CPU' rồi thử lại.")
        raise

    if result["audio"] is None:
        raise gr.Error(
            f"Không sinh được âm thanh (lỗi ngay đoạn 1/{result['n_chunks']} - hết VRAM?). "
            "Hãy bật 'Dùng CPU' hoặc giảm số bước rồi thử lại."
        )

    out_path, json_path = history.build_output_paths(text, partial=result["partial"])
    sf.write(str(out_path), result["audio"], SAMPLE_RATE)
    history.write_sidecar(json_path, {
        "text": text,
        "ref_voice": ref_path,
        "ref_text": ref_words if ref_path else None,
        "steps": int(steps),
        "device": device,
        "created": datetime.now().isoformat(timespec="seconds"),
        "sample_rate": SAMPLE_RATE,
        "n_chunks": result["n_chunks"],
        "partial": result["partial"],
        "failed_at": result["failed_at"],
        "wav": out_path.name,
    })

    if result["partial"]:
        gr.Warning(
            f"Dừng ở đoạn {result['failed_at']}/{result['n_chunks']} (hết VRAM?). "
            f"Đã lưu phần hoàn thành vào {out_path.name}. "
            "Thử bật 'Dùng CPU' hoặc giảm số bước rồi đọc lại."
        )
    progress(1.0, desc="Xong")
    return str(out_path), str(out_path.resolve())


def on_release_vram() -> str:
    """Giải phóng model khỏi VRAM (lần Đọc kế tiếp sẽ tự load lại)."""
    engine.unload()
    return "Đã giải phóng VRAM. Lần đọc kế tiếp sẽ tải lại model."


def on_refresh_refs():
    return gr.update(choices=list_refs())


def on_save_ref(audio_ref):
    """Lưu giọng mẫu vừa tải lên/thu âm vào refs/ để dùng lại lần sau."""
    if not audio_ref:
        return gr.update(), "Chưa có giọng mẫu nào để lưu - hãy tải lên hoặc thu âm trước."
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio_ref).suffix.lower() or ".wav"
    dest = REFS_DIR / f"ref-{datetime.now().strftime('%Y%m%d-%H%M%S')}{suffix}"
    try:
        shutil.copy2(audio_ref, dest)
    except OSError as exc:
        raise gr.Error(f"Không lưu được giọng mẫu: {exc}")
    return gr.update(choices=list_refs(), value=dest.name), f"Đã lưu giọng mẫu: {dest.name}"


def build_ui() -> gr.Blocks:
    # Gradio 6: theme/css truyền ở launch() (xem khối __main__), không phải ở Blocks().
    with gr.Blocks(title="Omnivoice Tiếng Việt - TTS offline") as demo:
        with gr.Row(elem_id="header-row"):
            gr.Markdown("### Omnivoice Tiếng Việt")
            btn_theme = gr.Button("Sáng / Tối", elem_id="theme-btn", scale=0)
        gr.Markdown("TTS tiếng Việt offline - nhập văn bản rồi bấm **Đọc**. "
                    "Muốn clone giọng thì mở mục *Giọng mẫu*.")

        with gr.Tab("Tạo giọng nói"):
            text_in = gr.Textbox(
                lines=6, label="Văn bản cần đọc",
                placeholder="Nhập một câu hoặc dán cả bài viết tiếng Việt - bài dài sẽ tự cắt câu...",
            )

            # Giọng mẫu + tùy chọn nâng cao gập lại (ít dùng) để màn hình gọn.
            with gr.Accordion("Giọng mẫu (tùy chọn - bỏ trống sẽ dùng giọng mặc định)", open=False):
                with gr.Row():
                    dd_ref = gr.Dropdown(choices=list_refs(), value=None, scale=3,
                                         label="Chọn giọng mẫu có sẵn (refs/)")
                    btn_refresh = gr.Button("Tải lại", scale=1, min_width=80)
                audio_ref = gr.Audio(sources=["upload", "microphone"], type="filepath",
                                     label="Hoặc tải lên / thu âm giọng mẫu mới (3-10 giây)",
                                     elem_id="ref-audio")
                with gr.Row():
                    ref_text = gr.Textbox(scale=3, label="Lời mẫu (lời thoại đúng trong giọng mẫu)",
                                          placeholder="Gõ đúng câu trong file mẫu để đỡ tốn VRAM...")
                    btn_save_ref = gr.Button("Lưu vào refs/", scale=1, min_width=120)

            with gr.Accordion("Tùy chọn nâng cao", open=False):
                with gr.Row():
                    steps = gr.Slider(8, 32, value=16, step=1,
                                      label="Số bước (ít: nhanh, nhiều: mượt hơn)")
                    use_cpu = gr.Checkbox(value=False,
                                          label="Dùng CPU (chậm nhưng không giới hạn VRAM)")

            btn_go = gr.Button("Đọc", variant="primary", elem_id="go-btn")

            # Kết quả hiện ngay dưới nút Đọc.
            audio_out = gr.Audio(label="Kết quả", type="filepath", interactive=False)
            path_out = gr.Textbox(label="Đường dẫn file", interactive=False)
            with gr.Row():
                btn_unload = gr.Button("Giải phóng VRAM", scale=1, min_width=180, elem_id="unload-btn")
                status_out = gr.Textbox(label="Trạng thái", interactive=False, scale=3)

        app_history_tab.build_history_tab()

        btn_theme.click(None, None, None, js=app_theme.THEME_TOGGLE_JS)
        btn_go.click(
            on_generate,
            inputs=[text_in, dd_ref, audio_ref, ref_text, steps, use_cpu],
            outputs=[audio_out, path_out],
            concurrency_limit=1,  # 4GB VRAM: tuyệt đối không sinh song song
        )
        btn_refresh.click(on_refresh_refs, outputs=dd_ref)
        btn_save_ref.click(on_save_ref, inputs=audio_ref, outputs=[dd_ref, status_out])
        btn_unload.click(on_release_vram, outputs=status_out)

    return demo


if __name__ == "__main__":
    ui = build_ui()
    ui.queue(default_concurrency_limit=1)  # hàng đợi tuần tự - xem chú thích concurrency ở trên
    ui.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, share=False,
              theme=app_theme.THEME, css=app_theme.CUSTOM_CSS)
