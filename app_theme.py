#!/usr/bin/env python3
"""
Theme, CSS tùy chỉnh và nút chuyển sáng/tối cho giao diện Gradio.

Tách khỏi app.py để app.py giữ dưới 200 dòng và phần trình bày gom một chỗ.
"""
import gradio as gr

# Theme Soft (bo tròn mềm, tông indigo). Mặc định Soft tô nhãn component bằng màu
# primary (tím) + có nền badge ở chế độ tối -> rối mắt. Ở đây làm PHẲNG nhãn:
# bỏ nền, chữ xám trung tính, áp dụng cho CẢ sáng lẫn tối (token *_dark riêng).
THEME = gr.themes.Soft(
    primary_hue="indigo",
    neutral_hue="slate",
    radius_size=gr.themes.sizes.radius_lg,
).set(
    # Nhãn chính của component ("Văn bản cần đọc", "Kết quả"...) = block_title.
    block_title_background_fill="transparent",
    block_title_background_fill_dark="transparent",
    block_title_text_color="*neutral_600",
    block_title_text_color_dark="*neutral_300",
    block_title_text_weight="600",
    # Badge nhãn góc = block_label (dọn cho đồng bộ, khỏi badge tím ở dark).
    block_label_background_fill="transparent",
    block_label_background_fill_dark="transparent",
    block_label_border_width="0px",
    block_label_border_width_dark="0px",
    block_label_text_color="*neutral_600",
    block_label_text_color_dark="*neutral_300",
)

# CSS: căn giữa, giới hạn bề ngang cho dễ đọc; nút Đọc to nổi bật; nút phụ không
# bị xuống dòng; vùng tải/thu giọng mẫu thấp lại; ẩn footer "Built with Gradio".
CUSTOM_CSS = """
.gradio-container { max-width: 900px !important; margin: 0 auto !important; }
#header-row { align-items: center; margin-bottom: 2px; }
#header-row h3 { white-space: nowrap; margin: 0; }
#go-btn { min-height: 54px; font-size: 1.15rem; font-weight: 700; margin-top: 4px; }
#theme-btn { max-width: 116px; }
#unload-btn { white-space: nowrap; }
#ref-audio .audio-container, #ref-audio .wrap { min-height: 120px !important; }
footer { display: none !important; }
"""

# Đổi nền sáng <-> tối: đặt lại URL param __theme rồi tải lại trang.
# Đây là cách chính thức của Gradio - render đúng TOÀN BỘ theme (kể cả màu
# bên trong từng component), chắc ăn xuyên phiên bản hơn là tự bật/tắt class.
# Đánh đổi: tải lại trang nên mất văn bản đang gõ dở (thường chỉ chuyển 1 lần lúc mở).
THEME_TOGGLE_JS = """
() => {
  const url = new URL(window.location.href);
  const cur = url.searchParams.get('__theme');
  let isDark;
  if (cur === 'dark') { isDark = true; }
  else if (cur === 'light') { isDark = false; }
  else {
    const app = document.querySelector('gradio-app');
    isDark = (app && app.classList.contains('dark'))
             || window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  url.searchParams.set('__theme', isDark ? 'light' : 'dark');
  window.location.href = url.href;
}
"""
