#!/usr/bin/env python3
"""
Unit test cho vietnamese_number_normalizer (không cần GPU).

    uv run python -m unittest tests.test_vietnamese_number_normalizer

Tập trung các ca KHÓ của tiếng Việt: lăm/mốt/tư, lẻ, mười, 'không trăm' ở nhóm giữa,
số triệu/tỉ, thập phân 'phẩy', phần trăm, và giữ nguyên dấu tiếng Việt trong phần chữ.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vietnamese_number_normalizer import normalize, read_integer  # noqa: E402


class TestReadInteger(unittest.TestCase):
    def test_don_vi(self):
        cases = {0: "không", 1: "một", 4: "bốn", 5: "năm", 9: "chín"}
        for n, expected in cases.items():
            self.assertEqual(read_integer(n), expected, n)

    def test_hang_chuc_ca_kho(self):
        cases = {
            10: "mười", 11: "mười một", 14: "mười bốn", 15: "mười lăm",
            20: "hai mươi", 21: "hai mươi mốt", 24: "hai mươi tư", 25: "hai mươi lăm",
            30: "ba mươi", 51: "năm mươi mốt",
        }
        for n, expected in cases.items():
            self.assertEqual(read_integer(n), expected, n)

    def test_hang_tram_le(self):
        cases = {
            100: "một trăm", 101: "một trăm lẻ một", 105: "một trăm lẻ năm",
            110: "một trăm mười", 115: "một trăm mười lăm", 120: "một trăm hai mươi",
            125: "một trăm hai mươi lăm", 999: "chín trăm chín mươi chín",
        }
        for n, expected in cases.items():
            self.assertEqual(read_integer(n), expected, n)

    def test_nghin_trieu_ti(self):
        cases = {
            1000: "một nghìn",
            1001: "một nghìn không trăm lẻ một",
            1250000: "một triệu hai trăm năm mươi nghìn",
            1000000: "một triệu",
            1000005: "một triệu không trăm lẻ năm",
            2026: "hai nghìn không trăm hai mươi sáu",
            1000000000: "một tỉ",
        }
        for n, expected in cases.items():
            self.assertEqual(read_integer(n), expected, n)

    def test_mien_nam_dung_ngan(self):
        self.assertEqual(read_integer(1000, dialect="nam"), "một ngàn")
        self.assertEqual(read_integer(2000, dialect="nam"), "hai ngàn")


class TestNormalize(unittest.TestCase):
    def test_thap_phan_va_phan_tram(self):
        self.assertEqual(normalize("3,5"), "ba phẩy năm")
        self.assertEqual(normalize("tăng 3,5%"), "tăng ba phẩy năm phần trăm")
        self.assertEqual(normalize("0,05"), "không phẩy không năm")

    def test_tien_nghin_giu_dong(self):
        self.assertEqual(
            normalize("doanh thu 1.250.000 đồng"),
            "doanh thu một triệu hai trăm năm mươi nghìn đồng",
        )

    def test_cau_ngay_thang_nam(self):
        self.assertEqual(
            normalize("Ngày 15 tháng 8 năm 2026"),
            "Ngày mười lăm tháng tám năm hai nghìn không trăm hai mươi sáu",
        )

    def test_giu_nguyen_dau_tieng_viet_phan_chu(self):
        # Phần chữ (có dấu) phải nguyên vẹn; chỉ số bị đổi.
        out = normalize("Có 2 học viên đạt điểm cao.")
        self.assertEqual(out, "Có hai học viên đạt điểm cao.")

    def test_khong_co_so_thi_giu_nguyen(self):
        s = "Xin chào các bạn, hôm nay trời đẹp."
        self.assertEqual(normalize(s), s)

    def test_giu_xuong_dong(self):
        self.assertEqual(normalize("Dòng 1.\nDòng 2."),
                         "Dòng một.\nDòng hai.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
