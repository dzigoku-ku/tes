"""Тесты расчётной части графического интерфейса (без окон)."""

import unittest
from fractions import Fraction

from gui_analysis import analyse, decode_steps, parse_code

try:
    from lxml import etree
    from gui_omml import tex_to_omml
except ImportError:  # lxml ставится вместе с python-docx
    etree = None


class AnalysisTest(unittest.TestCase):
    def test_kolokol(self):
        a = analyse("КОЛОКОЛ")
        self.assertTrue(a.exact)
        self.assertEqual(a.decoded, "КОЛОКОЛ")
        self.assertTrue(a.int_ok)
        self.assertEqual(a.code_bits, "0011100011")
        self.assertTrue(a.final_low <= a.code < a.final_high)
        # ширина итогового интервала = произведение вероятностей
        prod = Fraction(1)
        for s in a.message:
            prod *= a.p(s)
        self.assertEqual(a.final_high - a.final_low, prod)

    def test_steps_chain(self):
        a = analyse("abracadabra")
        for prev, cur in zip(a.steps, a.steps[1:]):
            self.assertEqual(prev.low, cur.low_prev)
            self.assertEqual(prev.high, cur.high_prev)
        self.assertEqual(len(a.int_trace), a.n)

    def test_long_message_not_exact(self):
        a = analyse("ab" * 400)
        self.assertFalse(a.exact)
        self.assertTrue(a.int_ok)

    def test_parse_code(self):
        self.assertEqual(parse_code("0.0011100011", True), Fraction(227, 1024))
        self.assertEqual(parse_code("0,0011100011", True), Fraction(227, 1024))
        self.assertEqual(parse_code("0011100011", True), Fraction(227, 1024))
        self.assertEqual(parse_code("0,25", False), Fraction(1, 4))
        for bad, binary in [("0.12", True), ("", True), ("1,5", False), ("abc", False)]:
            with self.assertRaises(ValueError):
                parse_code(bad, binary)

    def test_decode_foreign_code(self):
        a = analyse("КОЛОКОЛ")
        steps = decode_steps(Fraction(9, 10), 5, a.model)
        self.assertEqual(len(steps), 5)
        for st in steps:
            self.assertTrue(0 <= st.v < 1)


@unittest.skipIf(etree is None, "нужен lxml (pip install python-docx)")
class OmmlTest(unittest.TestCase):
    FORMULAS = [
        r"p(a) = \dfrac{n(a)}{n},",
        r"Q(a) = \sum_{b\,<\,a} p(b),",
        r"H = -\sum_{a\,\in\,A} p(a)\,\log_2 p(a).",
        r"l_i = l_{i-1} + (h_{i-1} - l_{i-1})\cdot Q(s_i),",
        r"r = \left\lfloor \dfrac{R}{T} \right\rfloor,",
        r"R \leftarrow 2^{8} R,\qquad L \leftarrow 2^{8} L \bmod 2^{32}.",
        r"\left[Q(a);\ Q(a) + p(a)\right)",
        r"H \approx 1{,}5567\ \mathrm{бит/символ}",
        r"\frac{4}{7} \leq 0{,}775879 < 1\quad\Rightarrow\quad s_{2} = \mathrm{О}",
    ]

    def test_well_formed(self):
        for tex in self.FORMULAS:
            etree.fromstring(tex_to_omml(tex))

    def test_decimal_comma_is_one_run(self):
        xml = tex_to_omml(r"x = 0{,}2216")
        self.assertIn(">0,2216<", xml)
        self.assertIn("<m:nor/>", xml)


if __name__ == "__main__":
    unittest.main()
