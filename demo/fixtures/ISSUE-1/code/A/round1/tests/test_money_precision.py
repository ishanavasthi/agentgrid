import unittest

from splitsathi.money import to_paise


class TestPaisePrecision(unittest.TestCase):
    def test_truncation_regression(self):
        self.assertEqual(to_paise(19.99), 1999)

    def test_awkward_floats(self):
        self.assertEqual(to_paise(4.35), 435)
        self.assertEqual(to_paise(0.07), 7)


if __name__ == "__main__":
    unittest.main()
