#!/usr/bin/env python3
"""
Tab "Lịch sử" của app Gradio: bảng các file đã sinh, nghe lại, xóa.

Tách khỏi app.py để mỗi file giữ dưới 200 dòng. Gọi build_history_tab() bên trong
`with gr.Blocks(...)` của app.py - hàm tự tạo gr.Tab và tự wire toàn bộ handler.
"""
from pathlib import Path

import gradio as gr

import history
from tts_engine import OUTPUTS_DIR

HISTORY_COLUMNS = ["Thời gian", "Nội dung", "Giọng mẫu", "File"]
PREVIEW_CHARS = 80  # cắt ngắn nội dung hiển thị trong bảng (text đầy đủ vẫn nằm trong JSON)


def _history_rows() -> list[list[str]]:
    """Chuyển list_history() thành các dòng cho gr.Dataframe."""
    rows: list[list[str]] = []
    for meta in history.list_history():
        created = (meta.get("created") or "").replace("T", " ")
        text = meta.get("text") or ""
        preview = text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 3] + "..."
        if meta.get("partial"):
            preview = "[dở dang] " + preview
        ref_voice = meta.get("ref_voice")
        ref_label = Path(ref_voice).name if ref_voice else "giọng mặc định"
        rows.append([created, preview, ref_label, meta.get("wav") or ""])
    return rows


def on_reload_history():
    return gr.update(value=_history_rows())


def on_history_select(table_data, evt: gr.SelectData):
    """Chọn một dòng -> nạp file wav tương ứng vào player."""
    try:
        basename = table_data[evt.index[0]][3]
    except (IndexError, TypeError):
        return None, ""
    wav_path = OUTPUTS_DIR / str(basename)
    if not wav_path.exists():
        gr.Warning(f"File {basename} không còn trên đĩa - bấm 'Tải lại lịch sử'.")
        return None, ""
    return str(wav_path), str(basename)


def on_history_delete(basename: str):
    """Xóa file đang chọn (cả wav lẫn json) rồi làm mới bảng."""
    if not basename:
        gr.Warning("Hãy chọn một dòng trong bảng trước khi xóa.")
        return gr.update(), None, ""
    history.delete_entry(basename)
    gr.Info(f"Đã xóa {basename}.")
    return gr.update(value=_history_rows()), None, ""


def build_history_tab() -> None:
    """Tạo tab Lịch sử + wire handler. Gọi bên trong context gr.Blocks của app.py."""
    with gr.Tab("Lịch sử"):
        btn_reload = gr.Button("Tải lại lịch sử", scale=0)
        table = gr.Dataframe(
            value=_history_rows(), headers=HISTORY_COLUMNS, type="array",
            interactive=False, wrap=True, label="Các file đã sinh (mới nhất trước)",
        )
        audio_replay = gr.Audio(label="Nghe lại", type="filepath", interactive=False)
        btn_delete = gr.Button("Xóa file đang chọn", variant="stop", scale=0)
        selected_wav = gr.State("")

        btn_reload.click(on_reload_history, outputs=table)
        table.select(on_history_select, inputs=table, outputs=[audio_replay, selected_wav])
        btn_delete.click(on_history_delete, inputs=selected_wav,
                         outputs=[table, audio_replay, selected_wav])
