"""
Отрисовка формул отчёта средствами tkinter (без внешних библиотек).

Формула (подмножество TeX, см. gui_omml.parse_tex) раскладывается на
«коробки» — как в TeX и в редакторе формул Word: у каждой есть ширина,
высота над базовой линией и глубина под ней. Готовая формула рисуется на
отдельном tk.Canvas, который вставляется в текст отчёта.

Оформление как в Word: латинские буквы — курсивом, цифры и русские слова —
прямым шрифтом, дроби с горизонтальной чертой, индексы уменьшенным кеглем,
пробелы вокруг знаков «=», «+», «−» и т. п.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from gui_omml import parse_tex

INK = "#000000"
RELATIONS = set("=≈≤≥<>⇒←→∈")
BINARY = set("+−·×")
SPACES = {" ": 0.17, " ": 0.33, " ": 1.0, "  ": 2.0}

_fonts: dict[tuple, tkfont.Font] = {}


def _font(root, family: str, size: float, italic: bool) -> tkfont.Font:
    key = (family, round(size), italic)
    if key not in _fonts:
        _fonts[key] = tkfont.Font(root=root, family=family, size=max(7, round(size)),
                                  slant="italic" if italic else "roman")
    return _fonts[key]


# ---------------------------------------------------------------- коробки
class Box:
    w = 0.0     # ширина
    a = 0.0     # высота над базовой линией
    d = 0.0     # глубина под базовой линией

    def draw(self, c: tk.Canvas, x: float, y: float):  # y — базовая линия
        pass


class Space(Box):
    def __init__(self, w: float):
        self.w = w


class Text(Box):
    def __init__(self, text: str, font: tkfont.Font):
        self.text, self.font = text, font
        self.w = font.measure(text)
        self.a = font.metrics("ascent")
        self.d = font.metrics("descent")

    def draw(self, c, x, y):
        c.create_text(x, y - self.a, anchor="nw", text=self.text, font=self.font,
                      fill=INK)


class Row(Box):
    def __init__(self, items: list[Box]):
        self.items = items
        self.w = sum(b.w for b in items)
        self.a = max([b.a for b in items] + [0])
        self.d = max([b.d for b in items] + [0])

    def draw(self, c, x, y):
        for b in self.items:
            b.draw(c, x, y)
            x += b.w


class Fraction(Box):
    def __init__(self, num: Box, den: Box, em: float):
        self.num, self.den = num, den
        self.axis = em * 0.27            # высота математической оси
        self.gap = max(2.0, em * 0.12)
        self.pad = em * 0.12
        self.w = max(num.w, den.w) + 2 * self.pad
        self.a = self.axis + self.gap + num.a + num.d
        self.d = den.a + den.d + self.gap - self.axis

    def draw(self, c, x, y):
        bar = y - self.axis
        c.create_line(x + 1, bar, x + self.w - 1, bar, fill=INK, width=1)
        self.num.draw(c, x + (self.w - self.num.w) / 2, bar - self.gap - self.num.d)
        self.den.draw(c, x + (self.w - self.den.w) / 2, bar + self.gap + self.den.a)


class Scripts(Box):
    def __init__(self, base: Box, sub: Box | None, sup: Box | None, em: float):
        self.base, self.sub, self.sup = base, sub, sup
        self.sub_shift = em * 0.2
        self.sup_shift = em * 0.4
        self.w = base.w + max(sub.w if sub else 0, sup.w if sup else 0) + 1
        self.a = max(base.a, (self.sup_shift + sup.a) if sup else 0)
        self.d = max(base.d, (self.sub_shift + sub.d) if sub else 0)

    def draw(self, c, x, y):
        self.base.draw(c, x, y)
        xs = x + self.base.w + 1
        if self.sup:
            self.sup.draw(c, xs, y - self.sup_shift)
        if self.sub:
            self.sub.draw(c, xs, y + self.sub_shift)


class Limits(Box):
    """Сумма/произведение с пределами снизу и сверху."""

    def __init__(self, op: Box, sub: Box | None, sup: Box | None, gap: float):
        self.op, self.sub, self.sup, self.gap = op, sub, sup, gap
        self.w = max(op.w, sub.w if sub else 0, sup.w if sup else 0)
        self.a = op.a + ((sup.a + sup.d + gap) if sup else 0)
        self.d = op.d + ((sub.a + sub.d + gap) if sub else 0)

    def draw(self, c, x, y):
        self.op.draw(c, x + (self.w - self.op.w) / 2, y)
        if self.sup:
            self.sup.draw(c, x + (self.w - self.sup.w) / 2,
                          y - self.op.a - self.gap - self.sup.d)
        if self.sub:
            self.sub.draw(c, x + (self.w - self.sub.w) / 2,
                          y + self.op.d + self.gap + self.sub.a)


class Delimited(Box):
    """Содержимое в скобках, высота которых подстраивается под содержимое."""

    def __init__(self, inner: Box, beg: str, end: str, em: float):
        self.inner, self.beg, self.end = inner, beg, end
        self.a = max(inner.a, em * 0.75) + 1
        self.d = max(inner.d, em * 0.25) + 1
        self.dw = max(em * 0.32, (self.a + self.d) * 0.16)
        self.w = inner.w + (self.dw + 2 if beg else 0) + (self.dw + 2 if end else 0)

    def _glyph(self, c, ch: str, x: float, y: float, left: bool):
        top, bottom = y - self.a, y + self.d
        w = self.dw
        if ch in "()":
            # круглая скобка: дуга эллипса высотой с содержимое
            r = w * 1.6
            if ch == "(":
                box = (x + w * 0.25, top, x + w * 0.25 + 2 * r, bottom)
                c.create_arc(*box, start=125, extent=110, style="arc",
                             outline=INK, width=1.3)
            else:
                box = (x + w * 0.75 - 2 * r, top, x + w * 0.75, bottom)
                c.create_arc(*box, start=-55, extent=110, style="arc",
                             outline=INK, width=1.3)
        elif ch in "[]":
            xv = x + (w * 0.35 if ch == "[" else w * 0.65)
            xe = x + (w if ch == "[" else 0)
            c.create_line(xe, top, xv, top, xv, bottom, xe, bottom, fill=INK, width=1.2)
        elif ch in "⌊⌋":
            xv = x + (w * 0.35 if ch == "⌊" else w * 0.65)
            xe = x + (w if ch == "⌊" else 0)
            c.create_line(xv, top, xv, bottom, xe, bottom, fill=INK, width=1.2)
        elif ch == "|":
            c.create_line(x + w / 2, top, x + w / 2, bottom, fill=INK, width=1.2)

    def draw(self, c, x, y):
        if self.beg:
            self._glyph(c, self.beg, x, y, True)
            x += self.dw + 2
        self.inner.draw(c, x, y)
        x += self.inner.w
        if self.end:
            self._glyph(c, self.end, x + 2, y, False)


# ---------------------------------------------------------------- вёрстка
class Layout:
    def __init__(self, root: tk.Misc, family: str):
        self.root, self.family = root, family

    def em(self, size: float) -> float:
        return _font(self.root, self.family, size, False).metrics("linespace") / 1.15

    def text(self, text: str, size: float, italic: bool) -> Box:
        if text in SPACES:
            return Space(SPACES[text] * self.em(size))
        return Text(text, _font(self.root, self.family, size, italic))

    def row(self, nodes: list, size: float, script: bool = False) -> Box:
        """Строка формулы; script=True — индекс (без пробелов вокруг знаков)."""
        items: list[Box] = []
        prev = None
        k = 0
        while k < len(nodes):
            node = nodes[k]
            kind = node[0]
            em = self.em(size)
            if kind == "run":
                text, italic = node[1], node[2]
                if text in RELATIONS:
                    gap = em * (0.08 if script else 0.28)
                    items += [Space(gap), self.text(text, size, False), Space(gap)]
                elif text in BINARY:
                    unary = prev is None or (prev[0] == "run" and
                                             prev[1] in RELATIONS | BINARY | set("([,;"))
                    gap = 0 if unary or script else em * 0.22
                    items += [Space(gap), self.text(text, size, False), Space(gap)]
                elif text in ",;" and not script:
                    items += [self.text(text, size, False), Space(em * 0.17)]
                else:
                    items.append(self.text(text, size, italic))
            elif kind == "num":
                items.append(self.text(node[1], size, False))
            elif kind == "group":
                items.append(self.row(node[1], size, script))
            elif kind == "frac":
                inner = size if (len(node) > 3 and node[3]) else size * 0.8
                items.append(Fraction(self.row(node[1], inner), self.row(node[2], inner),
                                      self.em(size)))
            elif kind == "delim":
                _, beg, end, content = node
                items.append(Delimited(self.row(content, size), beg, end, em))
            elif kind == "script":
                _, base, sub, sup = node
                small = size * 0.72
                sub_box = self.row(sub, small, True) if sub is not None else None
                sup_box = self.row(sup, small, True) if sup is not None else None
                if base[0] == "nary":
                    op = self.text(base[1], size * 1.45, False)
                    items += [Limits(op, sub_box, sup_box, em * 0.08), Space(em * 0.17)]
                else:
                    items.append(Scripts(self.row([base], size, script), sub_box,
                                         sup_box, em))
                    if base[0] == "run" and base[1] == "log":
                        items.append(Space(em * 0.17))      # log₂ p — как оператор
            elif kind == "nary":
                items.append(self.text(node[1], size * 1.45, False))
            prev = node
            k += 1
        return Row(items)


def render_formula(parent: tk.Misc, tex: str, size: float, family: str,
                   bg: str = "#ffffff") -> tk.Canvas:
    """Нарисовать формулу на новом Canvas (ValueError — если TeX не разобран)."""
    box = Layout(parent, family).row(parse_tex(tex), size)
    pad = 3
    width = int(box.w + 2 * pad) + 1
    height = int(box.a + box.d + 2 * pad) + 1
    canvas = tk.Canvas(parent, width=width, height=height, bg=bg,
                       highlightthickness=0, borderwidth=0)
    box.draw(canvas, pad, pad + box.a)
    return canvas
