# OmniVoice Vietnamese TTS

Công cụ cá nhân chuyển văn bản tiếng Việt thành giọng nói + clone giọng, chạy offline 100% trên máy local (GPU 4GB VRAM). Một người dùng, không có server/multi-user.

## Language

**Giọng mẫu (Reference Voice)**:
File âm thanh 3-10 giây chứa giọng của một người, dùng để model bắt chước giọng đó khi sinh âm thanh.
_Avoid_: ref, voice sample, giọng tham chiếu

**Lời mẫu (Reference Text)**:
Lời thoại đúng nguyên văn có trong giọng mẫu. Nhập tay để model không phải tự nghe-chép (đỡ tốn VRAM).
_Avoid_: ref-text, transcript

**Giọng mặc định (Default Voice)**:
Giọng model tự sinh khi không đưa giọng mẫu. KHÔNG đảm bảo giống nhau giữa các lần sinh.
_Avoid_: giọng gốc, giọng chuẩn

**Clone giọng (Voice Cloning)**:
Sinh âm thanh đọc văn bản bất kỳ bằng giọng lấy từ giọng mẫu.
_Avoid_: nhái giọng, voice clone

**Văn bản dài (Long Text)**:
Văn bản nhiều câu cần đọc thành MỘT file âm thanh liền mạch, một giọng duy nhất từ đầu đến cuối.

**Đoạn (Chunk)**:
Phần văn bản ngắn (thường là một câu) được cắt ra từ văn bản dài; mỗi đoạn được sinh âm thanh riêng rồi ghép lại.
_Avoid_: segment, câu (khi nói về đơn vị xử lý)

**Tự lấy mẫu (Self-Reference)**:
Cơ chế giữ giọng đồng nhất cho văn bản dài khi người dùng không chọn giọng mẫu: đoạn đầu tiên sinh bằng giọng mặc định, rồi chính âm thanh + lời của đoạn đó trở thành giọng mẫu cho mọi đoạn còn lại.
