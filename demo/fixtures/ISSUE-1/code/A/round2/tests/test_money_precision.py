import unittest

from splitsathi.money import to_paise


class TestPaisePrecision(unittest.TestCase):
    def test_truncation_regression(self):
        self.assertEqual(to_paise(19.99), 1999)

    def test_awkward_floats(self):
        self.assertEqual(to_paise(4.35), 435)
        self.assertEqual(to_paise(0.07), 7)

    def test_string_amounts_from_upi_exports(self):
        self.assertEqual(to_paise("19.99"), 1999)
        self.assertEqual(to_paise("0.50"), 50)

    def test_large_amounts_stay_exact(self):
        self.assertEqual(to_paise("99999999999.99"), 9999999999999)

    def test_sub_paisa_rejected(self):
        with self.assertRaises(ValueError):
            to_paise("1.005")

    def test_garbage_rejected(self):
        with self.assertRaises(ValueError):
            to_paise("abc")


if __name__ == "__main__":
    unittest.main()
