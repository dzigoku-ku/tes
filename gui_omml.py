"""
Преобразование формул отчёта (подмножество TeX) в формулы Word (OMML).

В документе .docx формулы получаются «родными» — такими же, как созданные
через «Вставка → Уравнение» в Word: их можно редактировать.

Поддерживается ровно то, что использует отчёт: индексы и степени, дроби
\\frac/\\dfrac, суммы и произведения с пределами, \\mathrm{…}, \\left…\\right,
\\log, отношения и стрелки, пробелы.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

SYMBOLS = {
    "cdot": "·", "leq": "≤", "geq": "≥", "approx": "≈", "in": "∈",
    "leftarrow": "←", "rightarrow": "→", "Rightarrow": "⇒", "lfloor": "⌊",
    "rfloor": "⌋", "times": "×", "ldots": "…", ",": " ", " ": " ",
    "quad": " ", "qquad": "  ", "{": "{", "}": "}",
}
UPRIGHT_WORDS = {"log": "log", "bmod": " mod ", "ln": "ln"}
NARY = {"sum": "∑", "prod": "∏"}


class _Parser:
    def __init__(self, tex: str):
        self.t = tex
        self.i = 0

    # ------------------------------------------------------------ лексика
    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def command(self) -> str:
        """Прочитать имя команды после «\\»."""
        self.i += 1
        start = self.i
        if self.i < len(self.t) and self.t[self.i].isalpha():
            while self.i < len(self.t) and self.t[self.i].isalpha():
                self.i += 1
        else:
            self.i += 1
        return self.t[start:self.i]

    def skip_spaces(self):
        while self.peek() == " ":
            self.i += 1

    # ------------------------------------------------------------ синтаксис
    def sequence(self, stop: str | None = None, stop_right: bool = False) -> list:
        nodes: list = []
        while self.i < len(self.t):
            ch = self.peek()
            if stop and ch == stop:
                self.i += 1
                return nodes
            if stop_right and self.t.startswith("\\right", self.i):
                return nodes
            if ch in "_^":
                self.i += 1
                arg = self.argument()
                base = nodes.pop() if nodes else ("run", "", False)
                if base[0] == "script":
                    _, b, sub, sup = base
                else:
                    b, sub, sup = base, None, None
                if ch == "_":
                    sub = arg
                else:
                    sup = arg
                nodes.append(("script", b, sub, sup))
                continue
            node = self.atom()
            if node is not None:
                nodes.append(node)
        return nodes

    def argument(self) -> list:
        self.skip_spaces()
        ch = self.peek()
        if ch == "{":
            self.i += 1
            return self.sequence(stop="}")
        if ch == "\\":
            node = self.atom()
            return [node] if node else []
        self.i += 1
        return [("run", ch, ch.isalpha())]

    def atom(self):
        ch = self.peek()
        if ch == "{":
            self.i += 1
            return ("group", self.sequence(stop="}"))
        if ch == " ":
            self.i += 1
            return None
        if ch != "\\":
            self.i += 1
            text = {"-": "−", "*": "∗"}.get(ch, ch)
            return ("run", text, ch.isalpha())
        name = self.command()
        if name in ("frac", "dfrac", "tfrac"):
            # четвёртый элемент: крупная («выключная») дробь \dfrac
            return ("frac", self.argument(), self.argument(), name == "dfrac")
        if name == "mathrm" or name == "text":
            return ("run", self.raw_group(), False)
        if name == "numtext":
            return ("num", self.raw_group())
        if name in NARY:
            return ("nary", NARY[name])
        if name == "left":
            beg = self.delimiter()
            content = self.sequence(stop_right=True)
            if self.t.startswith("\\right", self.i):
                self.i += len("\\right")
                end = self.delimiter()
            else:
                end = ""
            return ("delim", beg, end, content)
        if name in UPRIGHT_WORDS:
            return ("run", UPRIGHT_WORDS[name], False)
        if name in SYMBOLS:
            return ("run", SYMBOLS[name], False)
        raise ValueError(f"неподдерживаемая команда \\{name}")

    def delimiter(self) -> str:
        ch = self.peek()
        if ch == "\\":
            name = self.command()
            return SYMBOLS.get(name, "")
        self.i += 1
        return "" if ch == "." else ch

    def raw_group(self) -> str:
        self.skip_spaces()
        if self.peek() != "{":
            ch = self.peek()
            self.i += 1
            return ch
        self.i += 1
        depth, start = 1, self.i
        while self.i < len(self.t):
            if self.t[self.i] == "{":
                depth += 1
            elif self.t[self.i] == "}":
                depth -= 1
                if depth == 0:
                    text = self.t[start:self.i]
                    self.i += 1
                    return text.replace("\\ ", " ").replace("\\,", " ")
            self.i += 1
        raise ValueError("незакрытая скобка")


# ------------------------------------------------------------------ вывод
def _run(text: str, italic: bool, normal_text: bool = False) -> str:
    if not text:
        return ""
    if normal_text:
        # «обычный текст» внутри формулы: без математических пробелов у запятой
        sty = '<m:rPr><m:nor/></m:rPr>'
    else:
        sty = "" if italic else '<m:rPr><m:sty m:val="p"/></m:rPr>'
    return (f'<m:r>{sty}<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/>'
            f'</w:rPr><m:t xml:space="preserve">{escape(text)}</m:t></m:r>')


def _render(nodes: list) -> str:
    out = []
    k = 0
    while k < len(nodes):
        node = nodes[k]
        kind = node[0]
        if kind == "run":
            # склеиваем подряд идущие символы одного начертания
            text, italic = node[1], node[2]
            while (k + 1 < len(nodes) and nodes[k + 1][0] == "run"
                   and nodes[k + 1][2] == italic and not italic):
                k += 1
                text += nodes[k][1]
            out.append(_run(text, italic))
        elif kind == "num":
            out.append(_run(node[1], False, normal_text=True))
        elif kind == "group":
            out.append(_render(node[1]))
        elif kind == "frac":
            out.append(f"<m:f><m:num>{_render(node[1])}</m:num>"
                       f"<m:den>{_render(node[2])}</m:den></m:f>")
        elif kind == "delim":
            _, beg, end, content = node
            out.append(f'<m:d><m:dPr><m:begChr m:val="{escape(beg)}"/>'
                       f'<m:endChr m:val="{escape(end)}"/></m:dPr>'
                       f"<m:e>{_render(content)}</m:e></m:d>")
        elif kind == "script":
            _, base, sub, sup = node
            if base[0] == "nary":
                # сумма/произведение: операнд — всё до «,», «.», «=» верхнего уровня
                operand = []
                while k + 1 < len(nodes):
                    nxt = nodes[k + 1]
                    if nxt[0] == "run" and nxt[1] in (",", ".", "="):
                        break
                    operand.append(nxt)
                    k += 1
                out.append(
                    f'<m:nary><m:naryPr><m:chr m:val="{base[1]}"/>'
                    f'<m:limLoc m:val="undOvr"/>'
                    + ('' if sub else '<m:subHide m:val="1"/>')
                    + ('' if sup else '<m:supHide m:val="1"/>')
                    + f'</m:naryPr><m:sub>{_render(sub or [])}</m:sub>'
                    f'<m:sup>{_render(sup or [])}</m:sup>'
                    f'<m:e>{_render(operand)}</m:e></m:nary>')
            else:
                b = _render([base])
                if sub is not None and sup is not None:
                    out.append(f"<m:sSubSup><m:e>{b}</m:e><m:sub>{_render(sub)}</m:sub>"
                               f"<m:sup>{_render(sup)}</m:sup></m:sSubSup>")
                elif sub is not None:
                    out.append(f"<m:sSub><m:e>{b}</m:e><m:sub>{_render(sub)}</m:sub></m:sSub>")
                else:
                    out.append(f"<m:sSup><m:e>{b}</m:e><m:sup>{_render(sup)}</m:sup></m:sSup>")
        elif kind == "nary":
            out.append(_run(node[1], False))
        k += 1
    return "".join(out)


def parse_tex(tex: str) -> list:
    """TeX → дерево узлов (используется и для Word, и для отрисовки в окне)."""
    # десятичные числа «0{,}285» → одно число с запятой без пробела
    tex = re.sub(r"(\d*)\{,\}(\d+)", lambda m: rf"\numtext{{{m[1]},{m[2]}}}", tex)
    return _Parser(tex).sequence()


def tex_to_omml(tex: str) -> str:
    """TeX → XML элемента <m:oMath> (с объявлениями пространств имён)."""
    nodes = parse_tex(tex)
    return (f'<m:oMath xmlns:m="{M_NS}" xmlns:w="{W_NS}">{_render(nodes)}</m:oMath>')
