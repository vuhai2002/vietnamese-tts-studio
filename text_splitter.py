#!/usr/bin/env python3
"""
Cắt văn bản tiếng Việt dài thành các đoạn (chunk) ngắn để sinh TTS từng phần.

Quy tắc (xem plans/260608-0054-gradio-web-ui/phase-02-text-splitter.md):
- Cắt theo dấu kết câu (. ! ? và chuỗi ...) và xuống dòng (xuống dòng LUÔN là ranh giới).
- KHÔNG cắt nhầm tại chữ viết tắt ("TP.", "v.v.") hay dấu chấm giữa hai chữ số
  ("3.5" thập phân, "1.000.000" phân cách nghìn kiểu Việt Nam).
- Gộp đoạn quá ngắn (< min_chars) vào đoạn bên cạnh để khỏi tốn 1 lần generate cho 1-2 từ.
- Bẻ nhỏ câu quá dài (> max_chars) tại dấu phẩy/khoảng trắng gần cuối (an toàn VRAM 4GB).
- Giữ nguyên 100% dấu tiếng Việt - tuyệt đối không normalize/strip ký tự.

Chỉ dùng stdlib (re) - không kéo thêm nltk/underthesea cho công cụ 1 người dùng.
"""
import re

# Chữ viết tắt thường gặp có dấu chấm - dấu chấm trong đó KHÔNG kết thúc câu.
# Muốn mở rộng: thêm phần tử vào tuple này (sẽ tự ưu tiên chuỗi dài hơn trước).
ABBREVIATIONS = (
    "TP.", "Tp.", "tp.",          # Thành phố
    "Q.", "P.", "Tr.",            # Quận, Phường, trang
    "ĐT.", "TS.", "ThS.", "Th.S", "GS.", "PGS.",  # học hàm/học vị, điện thoại
    "v.v.", "v.v",                # vân vân
    "Mr.", "Mrs.", "Dr.", "St.",
)

_SENTINEL = "\x00"  # thay tạm dấu chấm cần bảo vệ, khôi phục sau khi cắt
# Ưu tiên chuỗi dài trước để "v.v." được mask trọn vẹn trước khi "v.v" kịp khớp.
_ABBR_PATTERNS = [
    (re.compile(r"(?<!\w)" + re.escape(abbr)), abbr.replace(".", _SENTINEL))
    for abbr in sorted(ABBREVIATIONS, key=len, reverse=True)
]
_DECIMAL_DOT = re.compile(r"(?<=\d)\.(?=\d)")   # dấu chấm kẹp giữa 2 chữ số
_SENT_END = re.compile(r"([.!?]+)")             # chuỗi dấu kết câu (gộp "..." làm một)


def _mask_protected_dots(text: str) -> str:
    """Thay dấu chấm trong viết tắt/số bằng sentinel để regex cắt câu bỏ qua chúng."""
    masked = _DECIMAL_DOT.sub(_SENTINEL, text)
    for pattern, replacement in _ABBR_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


def _split_sentences(line: str) -> list[str]:
    """Cắt một dòng thành các câu, dấu kết câu dính theo câu của nó."""
    parts = _SENT_END.split(line)
    sentences = []
    # parts xen kẽ [văn bản, dấu kết câu, văn bản, ...] - ghép từng cặp lại.
    for i in range(0, len(parts), 2):
        body = parts[i]
        delim = parts[i + 1] if i + 1 < len(parts) else ""
        sentence = (body + delim).strip()
        if sentence:
            sentences.append(sentence)
    return sentences


def _merge_short(chunks: list[str], min_chars: int) -> list[str]:
    """Gộp đoạn ngắn hơn min_chars vào đoạn kế tiếp (hoặc đoạn trước nếu là đoạn cuối)."""
    merged: list[str] = []
    for chunk in chunks:
        if merged and len(merged[-1]) < min_chars:
            merged[-1] = merged[-1] + " " + chunk
        else:
            merged.append(chunk)
    # Đoạn cuối cùng vẫn ngắn -> gộp ngược vào đoạn trước nó.
    if len(merged) >= 2 and len(merged[-1]) < min_chars:
        last = merged.pop()
        merged[-1] = merged[-1] + " " + last
    return merged


def _soft_split_long(chunks: list[str], max_chars: int) -> list[str]:
    """Bẻ đoạn dài quá max_chars tại dấu phẩy (ưu tiên) hoặc khoảng trắng cuối cùng trước giới hạn."""
    out: list[str] = []
    for chunk in chunks:
        while len(chunk) > max_chars:
            window = chunk[:max_chars]
            cut = window.rfind(",")
            if cut <= 0:
                cut = window.rfind(" ")
            if cut <= 0:
                # Chuỗi đặc không có chỗ cắt mềm -> cắt cứng tại giới hạn.
                head, chunk = chunk[:max_chars], chunk[max_chars:]
            else:
                head, chunk = chunk[: cut + 1], chunk[cut + 1 :]
            head = head.strip()
            if head:
                out.append(head)
            chunk = chunk.strip()
        if chunk:
            out.append(chunk)
    return out


def split_text(text: str, min_chars: int = 30, max_chars: int = 280) -> list[str]:
    """Cắt văn bản thành danh sách đoạn sạch (đã strip, không rỗng).

    - Văn bản rỗng/toàn khoảng trắng -> [].
    - Một câu ngắn -> danh sách 1 phần tử (không bao giờ trả chuỗi trần).
    - Dấu tiếng Việt được giữ nguyên từng byte.
    """
    if not text or not text.strip():
        return []

    masked = _mask_protected_dots(text.replace("\r\n", "\n"))

    chunks: list[str] = []
    # Xuống dòng là ranh giới cứng: xử lý từng dòng độc lập.
    for line in masked.split("\n"):
        if line.strip():
            chunks.extend(_split_sentences(line))

    # Khôi phục các dấu chấm đã bảo vệ.
    chunks = [c.replace(_SENTINEL, ".") for c in chunks]

    chunks = _merge_short(chunks, min_chars)
    chunks = _soft_split_long(chunks, max_chars)
    return chunks
