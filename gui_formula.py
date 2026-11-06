"""
Числа и символы для формул графического интерфейса.

Формулы рисуются модулем gui_mathdraw (средствами tkinter).

Числа оформляются по правилам ГОСТ: десятичный разделитель — запятая.
"""

from __future__ import annotations

import math
from fractions import Fraction

# ---------------------------------------------------------------------------
# Числа
# ---------------------------------------------------------------------------

def round_fraction(x: Fraction, digits: int) -> str:
    """Округлить точную дробь до digits знаков, записать через запятую."""
    scaled = round(x * 10 ** digits)
    sign = "-" if scaled < 0 else ""
    s = str(abs(scaled)).rjust(digits + 1, "0")
    if digits == 0:
        return sign + s
    return f"{sign}{s[:-digits]},{s[-digits:]}"


def dec(x, digits: int = 6) -> str:
    """Десятичная запись числа (Fraction, float или int) с запятой."""
    if isinstance(x, Fraction):
        return round_fraction(x, digits)
    if isinstance(x, int):
        return str(x)
    return f"{x:.{digits}f}".replace(".", ",")


def tex_num(x, digits: int = 6) -> str:
    """Число для формулы: запятая в фигурных скобках, чтобы не было пробела."""
    return dec(x, digits).replace(",", "{,}")


def tex_frac(x: Fraction) -> str:
    if x.denominator == 1:
        return str(x.numerator)
    return rf"\frac{{{x.numerator}}}{{{x.denominator}}}"


def tex_int(n: int) -> str:
    """Целое с разбиением на группы по три цифры тонким пробелом (ГОСТ 8.417)."""
    s = str(n)
    groups = []
    while len(s) > 3:
        groups.insert(0, s[-3:])
        s = s[:-3]
    groups.insert(0, s)
    return r"\,".join(groups) if len(str(n)) > 4 else str(n)


def plain_int(n: int) -> str:
    s = str(n)
    if len(s) <= 4:
        return s
    groups = []
    while len(s) > 3:
        groups.insert(0, s[-3:])
        s = s[:-3]
    groups.insert(0, s)
    return " ".join(groups)


def tex_sym(symbol: str) -> str:
    """Символ сообщения внутри формулы: «А», пробел показываем как ␣."""
    if symbol == " ":
        return r"\mathrm{␣}"
    if symbol in "\\{}$^_%#&~":
        return r"\mathrm{?}"
    return rf"\mathrm{{{symbol}}}"


def show_sym(symbol: str) -> str:
    """Символ сообщения в тексте интерфейса."""
    names = {" ": "␣ (пробел)", "\n": "↵ (перевод строки)", "\t": "→ (табуляция)"}
    return names.get(symbol, symbol)


def short_sym(symbol: str) -> str:
    return {" ": "␣", "\n": "↵", "\t": "→"}.get(symbol, symbol)


def digits_for(width: Fraction, extra: int = 2, minimum: int = 4,
               maximum: int = 30) -> int:
    """Сколько знаков после запятой нужно, чтобы различать границы интервала."""
    if width <= 0:
        return maximum
    return max(minimum, min(maximum, math.ceil(-math.log10(width)) + extra))
