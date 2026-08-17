#!/usr/bin/env python3
"""
Chuẩn hóa SỐ trong văn bản tiếng Việt thành CHỮ trước khi đưa vào TTS.

Vì sao cần: model KhanhTTS/OmniVoice đọc chuỗi số thô ("1.250.000 đồng", "3,5%") sai hoặc
không tự nhiên; tham số `normalize_text` built-in của omnivoice 0.2.1 KHÔNG nở số tiếng Việt
(đã kiểm chứng 2026-08-17). Nên ta tự nở: "1.250.000" -> "một triệu hai trăm năm mươi nghìn".

Quy ước tiếng Việt: dấu "." là phân cách nghìn, dấu "," là phân cách thập phân.
Giọng đọc số: mặc định Miền Bắc ("nghìn", "lẻ"); có thể đổi "ngàn" cho Miền Nam.

Chỉ dùng stdlib (re) - không thêm thư viện, đồng nhất với text_splitter.py.
"""
import re

_DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")

# Từ hàng nghìn khác nhau theo miền; "triệu"/"tỉ" giống nhau.
_THOUSAND = {"bac": "nghìn", "nam": "ngàn"}

# Bắt token số: có phân cách nghìn (1.250.000) HOẶC số thường, kèm phần thập phân tùy chọn (,5).
_NUMBER_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _read_three(n: int, force_hundreds: bool) -> list[str]:
    """Đọc một nhóm 3 chữ số (0..999). force_hundreds=True thì thêm 'không trăm' khi thiếu hàng trăm
    (dùng cho nhóm không phải nhóm cao nhất, ví dụ '...không trăm lẻ năm')."""
    h, t, u = n // 100, (n % 100) // 10, n % 10
    words: list[str] = []
    if h > 0:
        words += [_DIGITS[h], "trăm"]
    elif force_hundreds and (t > 0 or u > 0):
        words += ["không", "trăm"]

    if t > 1:
        words += [_DIGITS[t], "mươi"]
        if u == 1:
            words.append("mốt")            # 21 -> hai mươi mốt
        elif u == 4:
            words.append("tư")             # 24 -> hai mươi tư (đọc kiểu Bắc)
        elif u == 5:
            words.append("lăm")            # 25 -> hai mươi lăm
        elif u > 0:
            words.append(_DIGITS[u])
    elif t == 1:
        words.append("mười")
        if u == 5:
            words.append("lăm")            # 15 -> mười lăm
        elif u > 0:
            words.append(_DIGITS[u])       # 11 -> mười một, 14 -> mười bốn
    else:  # t == 0
        if u > 0:
            if h > 0 or force_hundreds:
                words.append("lẻ")         # 105 -> một trăm lẻ năm
            words.append(_DIGITS[u])
    return words


def _scale_word(group_index: int, thousand: str) -> str:
    """Từ bậc cho nhóm thứ i (0=đơn vị, 1=nghìn, 2=triệu, 3=tỉ, 4=nghìn tỉ, ...)."""
    base = ("", thousand, "triệu")[group_index % 3]
    ti = group_index // 3
    parts = ([base] if base else []) + ["tỉ"] * ti
    return " ".join(parts)


def read_integer(n: int, dialect: str = "bac") -> str:
    """Đọc số nguyên không âm thành chữ tiếng Việt. 0 -> 'không'."""
    if n == 0:
        return "không"
    thousand = _THOUSAND.get(dialect, _THOUSAND["bac"])
    groups: list[int] = []
    while n > 0:
        groups.append(n % 1000)
        n //= 1000
    leading = len(groups) - 1
    out: list[str] = []
    for i in range(leading, -1, -1):
        if groups[i] == 0:
            continue
        out += _read_three(groups[i], force_hundreds=(i != leading))
        scale = _scale_word(i, thousand)
        if scale:
            out.append(scale)
    return " ".join(out)


def _read_decimal(dec_digits: str) -> str:
    """Phần thập phân đọc từng chữ số: '5' -> 'năm', '05' -> 'không năm'."""
    return " ".join(_DIGITS[int(c)] for c in dec_digits)


def normalize(text: str, dialect: str = "bac") -> str:
    """Thay mọi token số + '%' trong văn bản bằng chữ đọc tiếng Việt. Giữ nguyên phần chữ + xuống dòng.

    Ví dụ: 'doanh thu 1.250.000 đồng, tăng 3,5%' ->
           'doanh thu một triệu hai trăm năm mươi nghìn đồng, tăng ba phẩy năm phần trăm'.
    """
    if not text:
        return text

    # '%' -> ' phần trăm' (xử lý trước để token số phía trước được đọc riêng).
    text = re.sub(r"\s*%", " phần trăm", text)

    def _repl(m: re.Match) -> str:
        tok = m.group(0)
        if "," in tok:
            int_part, dec_part = tok.split(",", 1)
            int_part = int_part.replace(".", "")
            words = read_integer(int(int_part), dialect) if int_part else "không"
            return f"{words} phẩy {_read_decimal(dec_part)}"
        return read_integer(int(tok.replace(".", "")), dialect)

    text = _NUMBER_RE.sub(_repl, text)
    # Gộp khoảng trắng thừa nhưng GIỮ xuống dòng.
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    return text
