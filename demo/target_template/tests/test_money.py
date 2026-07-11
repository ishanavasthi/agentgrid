import unittest

from splitsathi.money import from_paise, rupees_str, to_paise


class TestMoney(unittest.TestCase):
    def test_to_paise_round_amounts(self):
        self.assertEqual(to_paise(200), 20000)
        self.assertEqual(to_paise(10.50), 1050)
        self.assertEqual(to_paise(0.25), 25)

    def test_from_paise(self):
        self.assertEqual(from_paise(1050), 10.5)

    def test_rupees_str(self):
        self.assertEqual(rupees_str(1050), "Rs 10.50")


if __name__ == "__main__":
    unittest.main()
