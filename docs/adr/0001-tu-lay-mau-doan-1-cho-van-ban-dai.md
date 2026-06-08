# Tự lấy mẫu đoạn 1 cho văn bản dài

OmniVoice là model zero-shot voice cloning: khi không có giọng mẫu, mỗi lần generate có thể ra giọng mặc định khác nhau, nên văn bản dài (cắt thành nhiều đoạn, sinh riêng từng đoạn) có nguy cơ mỗi đoạn một giọng. Quyết định: khi người dùng không chọn giọng mẫu, sinh đoạn 1 bằng giọng mặc định rồi dùng chính audio + text của đoạn 1 làm giọng mẫu cho mọi đoạn còn lại — đồng nhất giọng 100% mà không cần Whisper (lời mẫu = chính text đoạn 1).

## Considered Options

- **Bắt buộc chọn giọng mẫu khi đọc văn bản dài** — code đơn giản hơn nhưng bắt người dùng luôn phải chuẩn bị file mẫu (refs/ hiện đang trống).
- **Ghép thẳng, không xử lý** — giả định giọng mặc định ổn định giữa các lần generate; nếu sai thì file dài hỏng giữa chừng, phải làm lại từ đầu.
- **Tự lấy mẫu đoạn 1 (đã chọn)** — đảm bảo đồng nhất, không cần người dùng chuẩn bị gì, chi phí chỉ là dùng đoạn 1 làm ref cho các đoạn sau.
