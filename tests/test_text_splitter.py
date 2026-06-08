#!/usr/bin/env python3
"""
Unit test cho text_splitter.py - chạy hoàn toàn offline, KHÔNG đụng GPU/omnivoice.

Chạy: uv run python -m unittest tests.test_text_splitter -v

Lưu ý cách test: các case kiểm tra LOGIC CẮT dùng min_chars=1 (tắt gộp đoạn ngắn)
để quan sát đúng hành vi cắt; các case kiểm tra GỘP dùng min_chars mặc định (30).
"""
import unittest

from text_splitter import split_text


class TestBasicSplitting(unittest.TestCase):
    """Logic cắt câu thuần - min_chars=1 để tắt gộp."""

    def test_single_short_sentence(self):
        # Một câu ngắn -> danh sách 1 phần tử, mặc định cũng vậy (không có gì để gộp).
        self.assertEqual(split_text("Xin chào."), ["Xin chào."])

    def test_two_sentences(self):
        self.assertEqual(
            split_text("Trời đẹp. Đi chơi thôi.", min_chars=1),
            ["Trời đẹp.", "Đi chơi thôi."],
        )

    def test_question_and_exclamation(self):
        self.assertEqual(
            split_text("Bạn khỏe không? Tuyệt vời!", min_chars=1),
            ["Bạn khỏe không?", "Tuyệt vời!"],
        )

    def test_terminator_stays_attached(self):
        chunks = split_text("Bạn khỏe không? Tốt lắm!", min_chars=1)
        self.assertTrue(chunks[0].endswith("?"))
        self.assertTrue(chunks[1].endswith("!"))


class TestProtectedDots(unittest.TestCase):
    """Dấu chấm trong viết tắt/số KHÔNG được coi là kết câu."""

    def test_abbreviation_tp(self):
        self.assertEqual(
            split_text("Tôi sống ở TP. Hồ Chí Minh từ nhỏ.", min_chars=1),
            ["Tôi sống ở TP. Hồ Chí Minh từ nhỏ."],
        )

    def test_abbreviation_vv(self):
        self.assertEqual(
            split_text("Có táo, cam, v.v. trong giỏ.", min_chars=1),
            ["Có táo, cam, v.v. trong giỏ."],
        )

    def test_decimal_number(self):
        self.assertEqual(
            split_text("Giá là 3.5 triệu đồng.", min_chars=1),
            ["Giá là 3.5 triệu đồng."],
        )

    def test_thousands_separator(self):
        self.assertEqual(
            split_text("Tổng cộng 1.000.000 đồng nhé.", min_chars=1),
            ["Tổng cộng 1.000.000 đồng nhé."],
        )

    def test_ellipsis_not_empty_chunks(self):
        chunks = split_text("Ừ thì... cũng được.", min_chars=1)
        # "..." là MỘT ranh giới, không sinh đoạn rỗng; chấp nhận 1-2 đoạn hợp lý.
        self.assertIn(len(chunks), (1, 2))
        for c in chunks:
            self.assertTrue(c.strip())

    def test_protected_dots_restored(self):
        # Sentinel phải được khôi phục lại thành dấu chấm, không lọt ra ngoài.
        chunks = split_text("Giá 3.5 triệu ở TP. Huế.", min_chars=1)
        joined = " ".join(chunks)
        self.assertIn("3.5", joined)
        self.assertIn("TP.", joined)
        self.assertNotIn("\x00", joined)


class TestNewlineBoundaries(unittest.TestCase):
    def test_newline_is_boundary(self):
        self.assertEqual(
            split_text("Dòng một\nDòng hai", min_chars=1),
            ["Dòng một", "Dòng hai"],
        )

    def test_blank_line_paragraphs(self):
        self.assertEqual(
            split_text("Đoạn A.\n\nĐoạn B.", min_chars=1),
            ["Đoạn A.", "Đoạn B."],
        )

    def test_crlf_normalized(self):
        self.assertEqual(
            split_text("Dòng một\r\nDòng hai", min_chars=1),
            ["Dòng một", "Dòng hai"],
        )


class TestMergeShort(unittest.TestCase):
    """Gộp đoạn ngắn - dùng min_chars mặc định (30)."""

    def test_short_fragment_merged_into_next(self):
        self.assertEqual(
            split_text("Ừ. Tôi đồng ý hoàn toàn với bạn về điều này."),
            ["Ừ. Tôi đồng ý hoàn toàn với bạn về điều này."],
        )

    def test_trailing_short_fragment_merged_back(self):
        chunks = split_text(
            "Hôm nay chúng ta sẽ bàn về kế hoạch quý tới của cả nhóm. Nhé."
        )
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].endswith("Nhé."))


class TestLongRunOn(unittest.TestCase):
    def test_run_on_longer_than_max_is_split(self):
        # 400+ ký tự không có dấu chấm -> phải bẻ nhỏ, mỗi đoạn <= max_chars.
        text = "từ ngữ " * 60  # ~420 ký tự
        chunks = split_text(text, max_chars=280)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 280)
            self.assertTrue(c.strip())

    def test_solid_string_hard_split(self):
        # Chuỗi đặc không khoảng trắng/phẩy -> cắt cứng, không treo vòng lặp.
        text = "a" * 700
        chunks = split_text(text, max_chars=280)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 280)


class TestEdgeCases(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(split_text(""), [])

    def test_whitespace_only(self):
        self.assertEqual(split_text("   "), [])

    def test_diacritics_byte_identical(self):
        src = "Nguyễn Thị Hoè ở Huế."
        chunks = split_text(src, min_chars=1)
        self.assertEqual(chunks, [src])
        # So sánh ở mức byte để chắc chắn không bị normalize/strip dấu.
        self.assertEqual(chunks[0].encode("utf-8"), src.encode("utf-8"))

    def test_returns_list_never_raw_string(self):
        result = split_text("Một câu duy nhất.")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
