"""
Полный расчёт интервального кодирования сообщения для графического интерфейса.

Все величины точные (fractions.Fraction); графический интерфейс
и отчёт только отображают то, что посчитано здесь.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction

import range_coding_demo as rc

EXACT_LIMIT = 300   # дальше точные дроби становятся слишком громоздкими


@dataclass
class EncodeStep:
    index: int          # номер шага i (с 1)
    symbol: str         # s_i
    low_prev: Fraction  # l_{i-1}
    high_prev: Fraction  # h_{i-1}
    q: Fraction         # Q(s_i) — нижняя граница интервала символа
    p: Fraction         # p(s_i)
    low: Fraction       # l_i
    high: Fraction      # h_i

    @property
    def width_prev(self) -> Fraction:
        return self.high_prev - self.low_prev

    @property
    def width(self) -> Fraction:
        return self.high - self.low


@dataclass
class DecodeStep:
    index: int
    low_prev: Fraction
    high_prev: Fraction
    v: Fraction         # относительное положение кода в текущем интервале
    symbol: str
    low: Fraction
    high: Fraction


@dataclass
class Analysis:
    message: str
    model: rc.FrequencyModel
    exact: bool                         # выполнен ли расчёт на точных дробях
    steps: list[EncodeStep] = field(default_factory=list)
    code: Fraction | None = None        # кратчайшая двоичная дробь в [l_n, h_n)
    code_bits: str = ""
    decode_steps: list[DecodeStep] = field(default_factory=list)
    int_model: rc.FrequencyModel | None = None
    int_data: bytes = b""
    int_trace: list[dict] = field(default_factory=list)
    int_ok: bool = False

    # --- производные величины ---
    @property
    def n(self) -> int:
        return len(self.message)

    def p(self, s: str) -> Fraction:
        return Fraction(self.model.freq[s], self.model.total)

    def q(self, s: str) -> Fraction:
        return Fraction(self.model.cum[s], self.model.total)

    @property
    def final_low(self) -> Fraction:
        return self.steps[-1].low

    @property
    def final_high(self) -> Fraction:
        return self.steps[-1].high

    @property
    def information(self) -> float:
        """Количество информации в сообщении, бит: −log2(h_n − l_n)."""
        return sum(-math.log2(self.model.freq[s] / self.model.total)
                   for s in self.message)

    @property
    def entropy(self) -> float:
        return self.model.entropy()

    @property
    def decoded(self) -> str:
        return "".join(st.symbol for st in self.decode_steps)


def interval_steps(message: str, model: rc.FrequencyModel) -> list[EncodeStep]:
    steps = []
    low, high = Fraction(0), Fraction(1)
    for i, s in enumerate(message, 1):
        q = Fraction(model.cum[s], model.total)
        p = Fraction(model.freq[s], model.total)
        width = high - low
        new_low, new_high = low + width * q, low + width * (q + p)
        steps.append(EncodeStep(i, s, low, high, q, p, new_low, new_high))
        low, high = new_low, new_high
    return steps


def decode_steps(code: Fraction, length: int,
                 model: rc.FrequencyModel) -> list[DecodeStep]:
    """Декодирование числа code: на каждом шаге ищем, в чей интервал оно попало."""
    steps = []
    low, high = Fraction(0), Fraction(1)
    for i in range(1, length + 1):
        width = high - low
        v = (code - low) / width
        value = math.floor(v * model.total)
        if not 0 <= value < model.total:
            raise ValueError("число вышло за пределы интервала [0; 1)")
        s = model.find(value)
        q = Fraction(model.cum[s], model.total)
        p = Fraction(model.freq[s], model.total)
        new_low, new_high = low + width * q, low + width * (q + p)
        steps.append(DecodeStep(i, low, high, v, s, new_low, new_high))
        low, high = new_low, new_high
    return steps


def analyse(message: str) -> Analysis:
    model = rc.FrequencyModel.from_message(message)
    exact = len(message) <= EXACT_LIMIT
    a = Analysis(message=message, model=model, exact=exact)
    if exact:
        a.steps = interval_steps(message, model)
        a.code, a.code_bits = rc.shortest_binary_in(a.final_low, a.final_high)
        a.decode_steps = decode_steps(a.code, len(message), model)

    a.int_model = rc.scale_model(model)
    a.int_data, enc = rc.int_encode_traced(message, a.int_model)
    a.int_trace = enc.trace
    a.int_ok = rc.int_decode(a.int_data, len(message), a.int_model) == message
    return a


def parse_code(text: str, binary: bool) -> Fraction:
    """Разобрать введённое пользователем число из [0; 1).

    binary=True:  «0.0011100011», «0,0011100011» или просто «0011100011».
    binary=False: десятичная дробь «0,2216796875» или «0.2216796875».
    """
    t = text.strip().replace(" ", "").replace(",", ".")
    if not t:
        raise ValueError("введите число")
    if binary:
        if t.startswith("0."):
            t = t[2:]
        elif t.startswith("."):
            t = t[1:]
        if not t or any(c not in "01" for c in t):
            raise ValueError("двоичная дробь может содержать только цифры 0 и 1")
        return Fraction(int(t, 2), 1 << len(t))
    try:
        x = Fraction(t)
    except ValueError:
        raise ValueError("не удалось распознать десятичное число") from None
    if not 0 <= x < 1:
        raise ValueError("число должно лежать в интервале [0; 1)")
    return x
