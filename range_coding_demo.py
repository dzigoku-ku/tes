#!/usr/bin/env python3
"""
Демонстрация интервального кодирования (range coding).

Программа показывает метод с двух сторон:

1. «Идеальное» интервальное кодирование на точных дробях (fractions.Fraction):
   шаг за шагом видно, как интервал [low, high) сужается пропорционально
   вероятности каждого символа, и как по одному числу из итогового интервала
   однозначно восстанавливается всё сообщение.

2. Практический целочисленный интервальный кодер (32-битный, в стиле
   кодера Субботина / LZMA) с побайтовой нормализацией и обработкой переноса.
   Он кодирует сообщение в последовательность байтов, декодирует обратно
   и сравнивает размер результата с энтропийной границей Шеннона.

Запуск:
    python3 range_coding_demo.py                     # пример по умолчанию
    python3 range_coding_demo.py "КОЛОКОЛ"           # своё сообщение
    python3 range_coding_demo.py -f file.txt         # сообщение из файла
    python3 range_coding_demo.py "abracadabra" --no-steps
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from fractions import Fraction


# ---------------------------------------------------------------------------
# Модель: таблица частот и кумулятивных частот
# ---------------------------------------------------------------------------

class FrequencyModel:
    """Статическая модель источника: частоты символов и их накопленные суммы.

    Символу s отводится полуинтервал [cum[s], cum[s] + freq[s]) на шкале
    [0, total). Ширина подынтервала пропорциональна вероятности символа.
    """

    def __init__(self, freqs: dict[str, int]):
        if not freqs:
            raise ValueError("Пустая модель: нет ни одного символа")
        # Фиксированный порядок символов нужен, чтобы кодер и декодер
        # строили одинаковые подынтервалы.
        self.symbols = sorted(freqs)
        self.freq = {s: freqs[s] for s in self.symbols}
        self.cum: dict[str, int] = {}
        acc = 0
        for s in self.symbols:
            self.cum[s] = acc
            acc += self.freq[s]
        self.total = acc

    @classmethod
    def from_message(cls, message: str) -> "FrequencyModel":
        return cls(dict(Counter(message)))

    def find(self, value: int) -> str:
        """Найти символ, в подынтервал которого попадает value из [0, total)."""
        for s in self.symbols:
            if self.cum[s] <= value < self.cum[s] + self.freq[s]:
                return s
        raise ValueError(f"Значение {value} вне диапазона модели")

    def entropy(self) -> float:
        """Энтропия источника в битах на символ."""
        return -sum(
            (f / self.total) * math.log2(f / self.total) for f in self.freq.values()
        )


# ---------------------------------------------------------------------------
# Часть 1. Наглядное кодирование на точных дробях
# ---------------------------------------------------------------------------

def show(x: Fraction, digits: int = 12) -> str:
    """Десятичная запись дроби с заданным числом знаков после запятой (с отсечением)."""
    scaled = x.numerator * 10 ** digits // x.denominator
    s = str(scaled).rjust(digits + 1, "0")
    return f"{s[:-digits]}.{s[-digits:]}"


def digits_for(width: Fraction) -> int:
    """Сколько десятичных знаков нужно, чтобы различить границы интервала."""
    return max(6, math.ceil(-math.log10(width)) + 2)


def common_prefix(a: str, b: str) -> str:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a[:n]


def print_interval(low: Fraction, high: Fraction, indent: str = "     "):
    """Напечатать границы интервала; общий префикс — уже «определившиеся» цифры."""
    d = digits_for(high - low)
    lo, hi = show(low, d), show(high, d)
    fixed = common_prefix(lo, hi)
    print(f"{indent}low  = {lo}")
    print(f"{indent}high = {hi}")
    if len(fixed) > 2:
        print(f"{indent}определились цифры: {fixed}")


def exact_encode(message: str, model: FrequencyModel, verbose: bool = True):
    """Сужать интервал [low, high) символ за символом. Возвращает (low, high)."""
    low, high = Fraction(0), Fraction(1)
    for i, s in enumerate(message, 1):
        width = high - low
        sym_low = Fraction(model.cum[s], model.total)
        sym_high = Fraction(model.cum[s] + model.freq[s], model.total)
        low, high = low + width * sym_low, low + width * sym_high
        if verbose:
            p = Fraction(model.freq[s], model.total)
            print(f"{i:>3}. {s!r}  P = {p}  ширина = {float(high - low):.3e}  "
                  f"(накоплено {-math.log2(high - low):.1f} бит)")
            print_interval(low, high)
    return low, high


def shortest_binary_in(low: Fraction, high: Fraction) -> tuple[Fraction, str]:
    """Найти двоичную дробь 0.b1b2...bk с минимальным k, лежащую в [low, high)."""
    k = 1
    while True:
        scale = 1 << k
        # Наименьшее m, для которого m / 2^k >= low
        m = -((-low.numerator * scale) // low.denominator)
        if Fraction(m, scale) < high:
            bits = format(m, f"0{k}b") if m else "0" * k
            return Fraction(m, scale), bits
        k += 1


def exact_decode(code: Fraction, length: int, model: FrequencyModel,
                 verbose: bool = True) -> str:
    """Восстановить сообщение по числу code и известной длине."""
    low, high = Fraction(0), Fraction(1)
    out = []
    for i in range(length):
        width = high - low
        # Где code находится внутри текущего интервала, в долях от total
        value = int((code - low) / width * model.total)
        s = model.find(value)
        out.append(s)
        low, high = (low + width * Fraction(model.cum[s], model.total),
                     low + width * Fraction(model.cum[s] + model.freq[s], model.total))
        if verbose:
            print(f"{i + 1:>3}. число лежит в подынтервале {s!r} "
                  f"-> [{show(low, 8)}..., {show(high, 8)}...)")
    return "".join(out)


# ---------------------------------------------------------------------------
# Часть 2. Практический целочисленный интервальный кодер (32 бита)
# ---------------------------------------------------------------------------

TOP = 1 << 24          # если range опустился ниже, выдвигаем старший байт
MASK32 = (1 << 32) - 1
MAX_TOTAL = 1 << 16    # total должен быть заметно меньше TOP, иначе range // total = 0


class RangeEncoder:
    """Кодер с переносом (carry), как в LZMA.

    low  — нижняя граница интервала (33 бита: 32 + бит переноса),
    range — ширина интервала (32 бита).
    Байты, которые ещё могут измениться из-за переноса (0xFF...),
    откладываются в cache / cache_size.
    """

    def __init__(self):
        self.low = 0
        self.range = MASK32
        self.cache = 0
        self.cache_size = 1
        self.out = bytearray()
        self.log: list[str] = []
        # Промежуточные значения каждого шага — для пошагового отчёта
        self.trace: list[dict] = []

    def _shift_low(self):
        if self.low < 0xFF000000 or self.low > MASK32:
            carry = self.low >> 32
            temp = self.cache
            while True:
                self.out.append((temp + carry) & 0xFF)
                temp = 0xFF
                self.cache_size -= 1
                if self.cache_size == 0:
                    break
            self.cache = (self.low >> 24) & 0xFF
        self.cache_size += 1
        self.low = (self.low << 8) & MASK32

    def encode(self, cum: int, freq: int, total: int):
        step = {"cum": cum, "freq": freq, "total": total,
                "low_in": self.low, "range_in": self.range}
        r = self.range // total
        self.low += r * cum
        self.range = r * freq
        step.update(r=r, low_mid=self.low, range_mid=self.range)
        shifts = 0
        while self.range < TOP:
            self.range <<= 8
            self._shift_low()
            shifts += 1
        step.update(shifts=shifts, low_out=self.low, range_out=self.range)
        self.trace.append(step)
        self.log.append(
            f"low=0x{self.low & MASK32:08X} range=0x{self.range:08X}"
            + (f"  (нормализация: {shifts} байт)" if shifts else "")
        )

    def finish(self) -> bytes:
        # Выбираем в [low, low + range) число с максимальным количеством
        # нулевых младших битов: хвостовые нулевые байты можно не хранить,
        # декодер подставит их сам.
        for k in range(32, -1, -1):
            v = -(-self.low >> k) << k          # округление low вверх до кратного 2^k
            if v < self.low + self.range:
                self.low = v
                break
        for _ in range(5):
            self._shift_low()
        # Первый выданный байт всегда 0 (начальный cache) — его тоже не храним.
        return bytes(self.out[1:]).rstrip(b"\x00")


class RangeDecoder:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.range = MASK32
        self.code = 0
        for _ in range(4):
            self.code = ((self.code << 8) | self._next_byte()) & MASK32

    def _next_byte(self) -> int:
        b = self.data[self.pos] if self.pos < len(self.data) else 0
        self.pos += 1
        return b

    def decode(self, model: FrequencyModel) -> str:
        r = self.range // model.total
        value = min(self.code // r, model.total - 1)
        s = model.find(value)
        self.code -= r * model.cum[s]
        self.range = r * model.freq[s]
        while self.range < TOP:
            self.range <<= 8
            self.code = ((self.code << 8) | self._next_byte()) & MASK32
        return s


def scale_model(model: FrequencyModel) -> FrequencyModel:
    """Уменьшить частоты так, чтобы total < MAX_TOTAL (каждая частота >= 1)."""
    if model.total < MAX_TOTAL:
        return model
    k = model.total / (MAX_TOTAL - len(model.symbols))
    return FrequencyModel({s: max(1, int(f / k)) for s, f in model.freq.items()})


def int_encode(message: str, model: FrequencyModel) -> tuple[bytes, list[str]]:
    data, enc = int_encode_traced(message, model)
    return data, enc.log


def int_encode_traced(message: str, model: FrequencyModel) -> tuple[bytes, "RangeEncoder"]:
    enc = RangeEncoder()
    for s in message:
        enc.encode(model.cum[s], model.freq[s], model.total)
    return enc.finish(), enc


def int_decode(data: bytes, length: int, model: FrequencyModel) -> str:
    dec = RangeDecoder(data)
    return "".join(dec.decode(model) for _ in range(length))


# ---------------------------------------------------------------------------
# Вывод демонстрации
# ---------------------------------------------------------------------------

def header(title: str):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def print_model(model: FrequencyModel):
    print(f"{'символ':^8} {'частота':>8} {'P':>10} {'подынтервал на [0, 1)':>30}")
    for s in model.symbols:
        lo = Fraction(model.cum[s], model.total)
        hi = Fraction(model.cum[s] + model.freq[s], model.total)
        print(f"{repr(s):^8} {model.freq[s]:>8} {model.freq[s] / model.total:>10.4f} "
              f"{'[' + f'{float(lo):.4f}, {float(hi):.4f}' + ')':>30}")
    print(f"Всего символов: {model.total}, энтропия H = {model.entropy():.4f} бит/символ")


def demo(message: str, steps: bool, exact_limit: int = 200):
    model = FrequencyModel.from_message(message)
    n = len(message)

    header("Сообщение и модель источника")
    preview = message if len(message) <= 120 else message[:117] + "..."
    print(f"Сообщение ({n} симв.): {preview!r}")
    print()
    print_model(model)

    # --- Часть 1: точные дроби ---
    if n <= exact_limit:
        header("Часть 1. Сужение интервала (точная арифметика)")
        print("Каждый символ сужает текущий интервал до своего подынтервала:\n"
              "  low'  = low + (high - low) * cum(s) / total\n"
              "  high' = low + (high - low) * (cum(s) + freq(s)) / total\n")
        low, high = exact_encode(message, model, verbose=steps)
        width = high - low
        code, bits = shortest_binary_in(low, high)
        print()
        print("Итоговый интервал:")
        print_interval(low, high, indent="  ")
        print(f"Ширина интервала = произведение вероятностей = {float(width):.6e}")
        print(f"-log2(ширина) = {-math.log2(width):.2f} бит — столько информации "
              f"в сообщении")
        print(f"Кратчайшая двоичная дробь внутри интервала: 0.{bits}")
        print(f"  = {show(code, digits_for(width))}...  ({len(bits)} бит)")

        print("\nДекодирование: по числу определяем, в чей подынтервал оно попало.")
        decoded = exact_decode(code, n, model, verbose=steps)
        status = "СОВПАДАЕТ" if decoded == message else "ОШИБКА"
        print(f"Декодировано: {decoded!r} — {status}")
    else:
        header("Часть 1. Пропущена")
        print(f"Сообщение длиннее {exact_limit} символов — точные дроби становятся "
              f"слишком громоздкими.\nЭто и есть причина, по которой на практике "
              f"используют целочисленный кодер (часть 2).")

    # --- Часть 2: целочисленный кодер ---
    header("Часть 2. Целочисленный интервальный кодер (32 бита, байтовый вывод)")
    imodel = scale_model(model)
    if imodel is not model:
        print(f"Частоты отмасштабированы до total = {imodel.total} (< {MAX_TOTAL}).")
    print("Интервал хранится как (low, range). Когда range < 2^24, старший байт\n"
          "low уже определён (с точностью до переноса) — он выдвигается в выход,\n"
          "а low и range сдвигаются на 8 бит влево.\n")

    data, log = int_encode(message, imodel)
    if steps:
        show_n = 40
        for i, (s, line) in enumerate(zip(message, log), 1):
            if i > show_n:
                print(f"... ещё {len(log) - show_n} шагов")
                break
            print(f"{i:>4} {repr(s):^6} {line}")
        print()

    hex_preview = data[:48].hex(" ").upper() + (" ..." if len(data) > 48 else "")
    print(f"Закодировано в {len(data)} байт: {hex_preview}")

    decoded = int_decode(data, n, imodel)
    status = "СОВПАДАЕТ" if decoded == message else "ОШИБКА"
    print(f"Декодировано: {status}")

    header("Итог")
    original_bits = len(message.encode("utf-8")) * 8
    fixed_bits = n * max(1, math.ceil(math.log2(len(model.symbols)))) \
        if len(model.symbols) > 1 else n
    shannon_bits = n * model.entropy()
    coded_bits = len(data) * 8
    print(f"Исходный текст в UTF-8:              {original_bits:>10} бит")
    print(f"{'Равномерный код (алфавит ' + str(len(model.symbols)) + '):':<37}"
          f"{fixed_bits:>10} бит")
    print(f"Граница Шеннона n*H:                 {shannon_bits:>10.1f} бит")
    print(f"Интервальный кодер:                  {coded_bits:>10} бит "
          f"({coded_bits / n:.3f} бит/символ)")
    print("Разница с границей Шеннона — округление до целого байта и конечная\n"
          "точность 32-битной арифметики; на длинных сообщениях она пренебрежимо мала.\n"
          "(Таблицу частот декодер тоже должен знать — здесь она не учтена.)")

    return decoded == message


def main(argv=None):
    parser = argparse.ArgumentParser(description="Демонстрация интервального кодирования")
    parser.add_argument("message", nargs="?", default="ИНТЕРВАЛЬНОЕ КОДИРОВАНИЕ",
                        help="сообщение для кодирования")
    parser.add_argument("-f", "--file", help="взять сообщение из файла (UTF-8)")
    parser.add_argument("--no-steps", action="store_true",
                        help="не печатать пошаговые таблицы")
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            message = fh.read()
    else:
        message = args.message
    if not message:
        parser.error("сообщение пустое")

    ok = demo(message, steps=not args.no_steps)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
