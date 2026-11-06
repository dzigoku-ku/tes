"""
Вкладка «Пошаговый отчёт».

Отчёт оформлен по правилам ГОСТ 7.32-2017 / ГОСТ 2.105-2019:
  * разделы нумеруются арабскими цифрами («1 Исходные данные»);
  * формулы выносятся в отдельную строку, по центру, номер — в круглых
    скобках у правого края; пояснение символов начинается со слова «где»;
  * таблицы имеют заголовок «Таблица N — Название» над таблицей;
  * десятичный разделитель — запятая.

Формулы рисуются как в редакторе формул Word (см. gui_mathdraw.py).
При включённом флажке «Подробные шаги» для каждого шага приводятся
конкретные арифметические действия с подставленными числами.
"""

from __future__ import annotations

import math
import tkinter as tk
from fractions import Fraction
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import range_coding_demo as rc
from gui_analysis import Analysis
from gui_diagrams import serif_family
from gui_mathdraw import render_formula
from gui_formula import (dec, digits_for, plain_int,
                         short_sym, tex_frac, tex_int, tex_num, tex_sym)

DETAIL_STEPS = 25        # подробная арифметика: шагов точного кодирования
DETAIL_INT_STEPS = 12    # подробная арифметика: шагов 32-битного кодера
TABLE_DIGITS = 16        # максимум знаков после запятой в таблицах
FORMULA_SIZE = 16
STEP_FORMULA_SIZE = 14


def frac_str(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def sci(x: float) -> str:
    """5.246e-04 → «5,246·10⁻⁴»."""
    if x == 0:
        return "0"
    exp = math.floor(math.log10(abs(x)))
    if -3 <= exp <= 3:
        return dec(x, 6)
    mant = x / 10 ** exp
    sup = str(exp).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"{dec(mant, 3)}·10{sup}"


def tex_sci(x: Fraction | float, sig: int = 4) -> str:
    x = float(x)
    if x == 0:
        return "0"
    exp = math.floor(math.log10(abs(x)))
    if -3 <= exp <= 3:
        return tex_num(x, 6)
    mant = x / 10 ** exp
    return rf"{tex_num(mant, sig - 1)}\cdot 10^{{{exp}}}"


class ReportView(ttk.Frame):
    def __init__(self, master, status_callback=None):
        super().__init__(master)
        self.status = status_callback or (lambda text: None)
        self.serif = serif_family(self)
        self.analysis: Analysis | None = None
        self.detailed = False

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Button(bar, text="Сохранить отчёт в Word (.docx)…",
                   command=self.save_docx).pack(side="left")
        ttk.Label(bar, foreground="#505050", text=(
            "  Документ оформлен по ГОСТ 7.32: поля, шрифт Times New Roman 14, "
            "нумерация формул и таблиц.")).pack(side="left")

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.text = tk.Text(holder, wrap="word", bg="#ffffff", fg="#000000",
                            padx=40, pady=24, font=(self.serif, 13),
                            relief="flat", highlightthickness=1,
                            highlightbackground="#a0a0a0", cursor="arrow")
        vbar = ttk.Scrollbar(holder, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Configure>", self._on_resize)

        f = self.serif
        t = self.text
        t.tag_configure("title", font=(f, 16, "bold"), justify="center",
                        spacing1=4, spacing3=14)
        t.tag_configure("h1", font=(f, 15, "bold"), spacing1=18, spacing3=8,
                        lmargin1=36)
        t.tag_configure("h2", font=(f, 13, "bold"), spacing1=12, spacing3=6,
                        lmargin1=36)
        t.tag_configure("p", font=(f, 13), spacing1=3, spacing3=3, lmargin1=36,
                        lmargin2=0, spacing2=4)
        t.tag_configure("step", font=(f, 13, "italic"), spacing1=10, spacing3=2,
                        lmargin1=36)
        t.tag_configure("where", font=(f, 13), lmargin1=0, lmargin2=48,
                        tabs=(48,), spacing1=1, spacing3=1)
        t.tag_configure("formula", font=(f, 13), spacing1=6, spacing3=6)
        t.tag_configure("caption", font=(f, 13), spacing1=12, spacing3=4)
        t.tag_configure("note", font=(f, 12, "italic"), foreground="#404040",
                        lmargin1=36, spacing1=4, spacing3=4)
        t.tag_configure("table", spacing1=2, spacing3=10)
        self.text.configure(state="disabled")
        self._tables: list[tk.Canvas] = []
        self.formula_no = 0
        self.table_no = 0
        self.items: list[tuple] = []   # структура документа для экспорта в .docx
        self.placeholder()

    # ------------------------------------------------------------ служебное
    def _on_resize(self, event):
        width = event.width - 96
        self.text.tag_configure("formula", tabs=(width // 2, "center", width, "right"))

    def placeholder(self):
        self._begin()
        self.p("Отчёт появится после кодирования сообщения.")
        self._end()

    def _begin(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for canvas in self._tables:
            canvas.destroy()
        self._tables.clear()
        self.formula_no = 0
        self.table_no = 0
        self.items = []

    def _end(self):
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def _insert(self, text: str, tag: str):
        self.text.insert("end", text, tag)

    def _image(self, tex: str, size: float, tag: str) -> None:
        """Вставить формулу (рисуется на Canvas внутри текста)."""
        try:
            canvas = render_formula(self.text, tex, size - 1, self.serif)
        except ValueError:  # неподдерживаемая конструкция — выводим как текст
            self._insert(tex, tag)
            return
        self.text.window_create("end", window=canvas, align="center")
        self.text.tag_add(tag, "end-2c", "end-1c")
        self._tables.append(canvas)

    # ------------------------------------------------------------ элементы
    def title(self, text: str):
        self._insert(text + "\n", "title")
        self.items.append(("title", text))

    def h1(self, text: str):
        self._insert(text + "\n", "h1")
        self.items.append(("h1", text))

    def h2(self, text: str):
        self._insert(text + "\n", "h2")
        self.items.append(("h2", text))

    def p(self, *parts, tag: str = "p"):
        """Абзац. parts: строки (текст) или ('$', tex) — формула в строке."""
        runs = []
        for part in parts:
            if isinstance(part, tuple):
                self._image(part[1], 14, tag)
                runs.append(("math", part[1]))
            else:
                self._insert(part, tag)
                runs.append(("text", part))
        self.items.append(("p", tag, runs))
        self._insert("\n", tag)

    def formula(self, tex: str, numbered: bool = True, size: float = FORMULA_SIZE) -> int:
        """Формула в отдельной строке; номер (N) у правого края."""
        self._insert("\t", "formula")
        self._image(tex, size, "formula")
        number = 0
        if numbered:
            self.formula_no += 1
            number = self.formula_no
            self._insert(f"\t({number})", "formula")
        self._insert("\n", "formula")
        self.items.append(("formula", tex, number))
        return number

    def where(self, items: list[tuple[str, str]]):
        """Пояснение символов: «где l_i — …;» (ГОСТ 7.32, 6.10.4)."""
        entries = []
        for k, (tex, desc) in enumerate(items):
            end = ";" if k < len(items) - 1 else "."
            self._insert("где\t" if k == 0 else "\t", "where")
            self._image(tex, 14, "where")
            self._insert(f" — {desc}{end}\n", "where")
            entries.append((tex, f" — {desc}{end}"))
        self.items.append(("where", entries))

    def table(self, title: str, headers: list[str], rows: list[list[str]],
              align: list[str] | None = None, max_rows: int = 400):
        """Таблица: заголовок «Таблица N — …» над ней, сетка как в Word."""
        self.table_no += 1
        caption = f"Таблица {self.table_no} — {title}"
        self._insert(caption + "\n", "caption")
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]
        align = align or ["c"] * len(headers)

        font = tkfont.Font(family=self.serif, size=12)
        bold = tkfont.Font(family=self.serif, size=12, weight="bold")
        pad = 10
        widths = []
        for j, head in enumerate(headers):
            w = max([bold.measure(line) for line in head.split("\n")] +
                    [font.measure(r[j]) for r in rows] + [30])
            widths.append(w + 2 * pad)
        line_h = font.metrics("linespace") + 8
        head_lines = max(h.count("\n") + 1 for h in headers)
        head_h = head_lines * (bold.metrics("linespace")) + 10
        total_w = sum(widths) + 2
        total_h = head_h + line_h * len(rows) + 2

        canvas = tk.Canvas(self.text, width=total_w, height=total_h, bg="#ffffff",
                           highlightthickness=0)
        x = 1
        for j, head in enumerate(headers):
            canvas.create_rectangle(x, 1, x + widths[j], head_h, outline="#000000")
            canvas.create_text(x + widths[j] / 2, head_h / 2, text=head, font=bold,
                               justify="center")
            y = head_h
            for row in rows:
                canvas.create_rectangle(x, y, x + widths[j], y + line_h, outline="#000000")
                anchor, tx = {"l": ("w", x + pad), "r": ("e", x + widths[j] - pad),
                              "c": ("center", x + widths[j] / 2)}[align[j]]
                canvas.create_text(tx, y + line_h / 2, text=row[j], font=font,
                                   anchor=anchor)
                y += line_h
            x += widths[j]
        self.text.window_create("end", window=canvas)
        self.text.tag_add("table", "end-2c", "end-1c")
        self._insert("\n", "table")
        self._tables.append(canvas)
        self.items.append(("table", caption, headers, rows, align))

        if truncated:
            self.p(f"Показаны первые {max_rows} строк.", tag="note")

    # ------------------------------------------------------------ сохранение
    def save_docx(self):
        """Сохранить отчёт в документ Word (.docx)."""
        if self.analysis is None:
            self.status("Сначала закодируйте сообщение.")
            return
        path = filedialog.asksaveasfilename(
            title="Сохранить отчёт", defaultextension=".docx",
            initialfile="Отчёт_интервальное_кодирование.docx",
            filetypes=[("Документ Word", "*.docx")])
        if not path:
            return
        try:
            from gui_export import write_docx
            write_docx(self.items, path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Сохранение отчёта", f"Не удалось сохранить файл:\n{exc}")
            return
        self.status(f"Отчёт сохранён: {path}")

    # ============================================================ содержание
    def build(self, a: Analysis, detailed: bool):
        self.analysis = a
        self.detailed = detailed
        self._begin()
        try:
            self._build(a, detailed)
        finally:
            self._end()

    def _build(self, a: Analysis, detailed: bool):
        model = a.model
        msg = a.message if len(a.message) <= 60 else a.message[:57] + "…"
        self.title("Интервальное (арифметическое) кодирование сообщения")
        if detailed:
            self.p("Режим: подробные шаги — для каждого шага приведены вычисления "
                   "с подставленными значениями.", tag="note")
        else:
            self.p("Включите флажок «Подробные шаги в отчёте», чтобы увидеть "
                   "арифметические действия для каждого шага.", tag="note")

        # ---------------------------------------------------------------- 1
        self.h1("1 Исходные данные")
        self.p(f"Исходное сообщение: «{msg}». Длина сообщения ",
               ("$", rf"n = {a.n}"), " символов; алфавит ", ("$", "A"),
               " сообщения содержит ", ("$", rf"m = {len(model.symbols)}"),
               " различных символов.")

        # ---------------------------------------------------------------- 2
        self.h1("2 Модель источника")
        self.p("Вероятность символа оценивается по частоте его появления в сообщении:")
        n_p = self.formula(r"p(a) = \dfrac{n(a)}{n},")
        self.where([("n(a)", "число появлений символа a в сообщении"),
                    ("n", "длина сообщения")])
        self.p("Символы упорядочиваются, и каждому символу сопоставляется "
               "полуинтервал отрезка [0; 1) длиной p(a). Нижняя граница интервала "
               "символа равна сумме вероятностей всех предшествующих символов:")
        n_q = self.formula(r"Q(a) = \sum_{b\,<\,a} p(b),")
        self.p("тогда интервал символа ", ("$", "a"), " есть ",
               ("$", r"\left[Q(a);\ Q(a) + p(a)\right)"), ".")

        syms = model.symbols
        if detailed and len(syms) <= 16:
            self.h2("2.1 Вычисление вероятностей и границ интервалов")
            acc_terms: list[str] = []
            for s in syms:
                p, q = a.p(s), a.q(s)
                self.p(f"Символ «{short_sym(s)}» встречается {model.freq[s]} раз(а):",
                       tag="step")
                self.formula(rf"p({tex_sym(s)}) = \dfrac{{{model.freq[s]}}}{{{a.n}}}"
                             rf" \approx {tex_num(p, 6)}", numbered=False,
                             size=STEP_FORMULA_SIZE)
                if acc_terms:
                    expr = " + ".join(acc_terms)
                    self.formula(rf"Q({tex_sym(s)}) = {expr} = {tex_frac(q)}"
                                 rf" \approx {tex_num(q, 6)}",
                                 numbered=False, size=STEP_FORMULA_SIZE)
                else:
                    self.formula(rf"Q({tex_sym(s)}) = 0 \quad"
                                 r"\mathrm{(первый\ символ)}",
                                 numbered=False, size=STEP_FORMULA_SIZE)
                acc_terms.append(tex_frac(p))

        rows = []
        for s in syms:
            p, q = a.p(s), a.q(s)
            rows.append([f"«{short_sym(s)}»", str(model.freq[s]),
                         f"{frac_str(p)} ≈ {dec(p, 4)}", f"{frac_str(q)} ≈ {dec(q, 4)}",
                         f"[{dec(q, 4)}; {dec(q + p, 4)})"])
        self.table("Вероятности и интервалы символов",
                   ["Символ a", "n(a)", "p(a)", "Q(a)", "Интервал символа"], rows,
                   ["c", "c", "c", "c", "c"], max_rows=200)

        self.p("Среднее количество информации на один символ (энтропия источника):")
        n_h = self.formula(r"H = -\sum_{a\,\in\,A} p(a)\,\log_2 p(a).")
        if detailed and len(syms) <= 6:
            terms = " + ".join(rf"{tex_frac(a.p(s))}\log_2{tex_frac(a.p(s))}" for s in syms)
            self.formula(rf"H = -\left({terms}\right) \approx {tex_num(a.entropy, 4)}"
                         r"\ \mathrm{бит/символ}", numbered=False, size=STEP_FORMULA_SIZE)
        else:
            self.formula(rf"H \approx {tex_num(a.entropy, 4)}\ \mathrm{{бит/символ}}",
                         numbered=False, size=STEP_FORMULA_SIZE)

        if not a.exact:
            self.h1("3 Кодирование")
            self.p(f"Сообщение содержит {a.n} символов. Расчёт на точных дробях "
                   f"(разделы кодирования и декодирования) выполняется для сообщений "
                   f"длиной до 300 символов; ниже приведена целочисленная реализация.")
            self._int_section(a, detailed, section=4, refs=None)
            self._comparison(a, section=5)
            return

        # ---------------------------------------------------------------- 3
        self.h1("3 Кодирование")
        self.p("Кодирование начинается с интервала ",
               ("$", r"\left[l_0;\ h_0\right) = \left[0;\ 1\right)"),
               ". Для очередного символа ", ("$", "s_i"),
               " текущий интервал заменяется той его частью, которая соответствует "
               "интервалу символа:")
        n_l = self.formula(r"l_i = l_{i-1} + (h_{i-1} - l_{i-1})\cdot Q(s_i),")
        n_hh = self.formula(r"h_i = l_{i-1} + (h_{i-1} - l_{i-1})\cdot"
                            r"\left(Q(s_i) + p(s_i)\right),")
        self.where([(r"l_i,\ h_i", "нижняя и верхняя границы интервала после "
                                  "кодирования i-го символа"),
                    ("s_i", "i-й символ сообщения"),
                    (r"Q(s_i),\ p(s_i)", f"величины по формулам ({n_q}) и ({n_p})")])
        self.p("Ширина интервала на каждом шаге умножается на вероятность символа: ",
               ("$", r"h_i - l_i = (h_{i-1} - l_{i-1})\cdot p(s_i)"), ".")

        if detailed:
            self.h2("3.1 Вычисления по шагам")
            limit = min(len(a.steps), DETAIL_STEPS)
            for st in a.steps[:limit]:
                i = st.index
                d = min(digits_for(st.width, minimum=6), 20)
                dp = min(digits_for(st.width_prev, minimum=6), 20)
                self.p(f"Шаг {i}. ", ("$", rf"s_{{{i}}} = {tex_sym(st.symbol)}"),
                       ", ", ("$", rf"p(s_{{{i}}}) = {tex_frac(st.p)}"), ", ",
                       ("$", rf"Q(s_{{{i}}}) = {tex_frac(st.q)}"), ".", tag="step")
                w = st.width_prev
                self.formula(rf"h_{{{i-1}}} - l_{{{i-1}}} = {tex_num(st.high_prev, dp)}"
                             rf" - {tex_num(st.low_prev, dp)} = {tex_num(w, dp)}",
                             numbered=False, size=STEP_FORMULA_SIZE)
                self.formula(rf"l_{{{i}}} = {tex_num(st.low_prev, dp)} + "
                             rf"{tex_num(w, dp)}\cdot {tex_frac(st.q)} = "
                             rf"{tex_num(st.low, d)}",
                             numbered=False, size=STEP_FORMULA_SIZE)
                self.formula(rf"h_{{{i}}} = {tex_num(st.low_prev, dp)} + "
                             rf"{tex_num(w, dp)}\cdot {tex_frac(st.q + st.p)} = "
                             rf"{tex_num(st.high, d)}",
                             numbered=False, size=STEP_FORMULA_SIZE)
            if len(a.steps) > limit:
                self.p(f"Подробные вычисления показаны для первых {limit} шагов; "
                       "остальные шаги — в таблице.", tag="note")
            self.p("Значения округлены; вычисления выполнены точно, в рациональных "
                   "дробях.", tag="note")

        rows = []
        for st in a.steps:
            d = min(digits_for(st.width), TABLE_DIGITS)
            rows.append([str(st.index), f"«{short_sym(st.symbol)}»", frac_str(st.p),
                         dec(st.low, d), dec(st.high, d), sci(float(st.width))])
        self.table(f"Границы интервала по шагам кодирования (формулы ({n_l}), ({n_hh}))",
                   ["i", "sᵢ", "p(sᵢ)", "lᵢ", "hᵢ", "hᵢ − lᵢ"], rows,
                   ["c", "c", "c", "l", "l", "c"])

        # ---------------------------------------------------------------- 4
        self.h1("4 Формирование кода")
        self.p("Ширина итогового интервала равна произведению вероятностей всех "
               "символов сообщения:")
        n_w = self.formula(r"h_n - l_n = \prod_{i=1}^{n} p(s_i).")
        width = a.final_high - a.final_low
        if detailed and a.n <= 16:
            prod = r"\cdot ".join(tex_frac(st.p) for st in a.steps)
            self.formula(rf"h_{{{a.n}}} - l_{{{a.n}}} = {prod} \approx {tex_sci(width)}",
                         numbered=False, size=STEP_FORMULA_SIZE)
        else:
            self.formula(rf"h_{{{a.n}}} - l_{{{a.n}}} \approx {tex_sci(width)}",
                         numbered=False, size=STEP_FORMULA_SIZE)
        self.p("Количество информации в сообщении, бит:")
        n_i = self.formula(r"I = -\log_2(h_n - l_n) = \sum_{i=1}^{n} -\log_2 p(s_i).")
        self.formula(rf"I = -\log_2\left({tex_sci(width)}\right) \approx "
                     rf"{tex_num(a.information, 2)}\ \mathrm{{бит}}",
                     numbered=False, size=STEP_FORMULA_SIZE)
        bits = a.code_bits
        shown_bits = bits if len(bits) <= 64 else bits[:61] + "…"
        d = min(digits_for(width), 24)
        self.p("В качестве кода выбирается число ", ("$", "x"),
               " из итогового интервала, имеющее самую короткую двоичную запись:")
        self.formula(rf"x = 0{{,}}{shown_bits}_2", numbered=False, size=STEP_FORMULA_SIZE)
        ones = [k + 1 for k, b in enumerate(bits) if b == "1"]
        if detailed and 0 < len(ones) <= 14:
            terms = " + ".join(rf"2^{{-{k}}}" for k in ones)
            self.formula(rf"x = {terms} = {tex_num(a.code, len(bits))}",
                         numbered=False, size=STEP_FORMULA_SIZE)
        if detailed:
            self.p("Проверка: код лежит в итоговом интервале:", tag="step")
            self.formula(rf"l_{{{a.n}}} = {tex_num(a.final_low, d)} \leq x = "
                         rf"{tex_num(a.code, d)} < h_{{{a.n}}} = {tex_num(a.final_high, d)}",
                         numbered=False, size=STEP_FORMULA_SIZE)
        self.p(f"Длина кода k = {len(bits)} бит. Она всегда не больше ⌈I⌉ + 1 "
               f"(по формуле ({n_i}) I ≈ {dec(a.information, 2)} бит).")

        # ---------------------------------------------------------------- 5
        self.h1("5 Декодирование")
        self.p("Декодеру известны таблица 1 и длина сообщения n. Начиная с интервала "
               "[0; 1), на каждом шаге вычисляется относительное положение кода "
               "в текущем интервале:")
        n_v = self.formula(r"v_i = \dfrac{x - l_{i-1}}{h_{i-1} - l_{i-1}},")
        self.p("и находится символ, в интервал которого попало ", ("$", "v_i"), ":")
        n_s = self.formula(r"Q(s_i) \leq v_i < Q(s_i) + p(s_i).")
        self.p(f"Затем границы интервала пересчитываются по формулам ({n_l}) и ({n_hh}).")

        if detailed:
            self.h2("5.1 Вычисления по шагам")
            limit = min(len(a.decode_steps), DETAIL_STEPS)
            for st in a.decode_steps[:limit]:
                i = st.index
                dp = min(max(digits_for(st.high_prev - st.low_prev, minimum=6),
                             len(a.code_bits)), 20)
                q, p = a.q(st.symbol), a.p(st.symbol)
                self.p(f"Шаг {i}.", tag="step")
                self.formula(rf"v_{{{i}}} = \dfrac{{{tex_num(a.code, dp)} - "
                             rf"{tex_num(st.low_prev, dp)}}}{{{tex_num(st.high_prev, dp)} - "
                             rf"{tex_num(st.low_prev, dp)}}} \approx {tex_num(st.v, 6)}",
                             numbered=False, size=STEP_FORMULA_SIZE)
                self.formula(rf"{tex_frac(q)} \leq {tex_num(st.v, 6)} < {tex_frac(q + p)}"
                             rf"\quad\Rightarrow\quad s_{{{i}}} = {tex_sym(st.symbol)}",
                             numbered=False, size=STEP_FORMULA_SIZE)
            if len(a.decode_steps) > limit:
                self.p(f"Подробные вычисления показаны для первых {limit} шагов.",
                       tag="note")

        rows = []
        for st in a.decode_steps:
            d = min(digits_for(st.high - st.low), TABLE_DIGITS)
            rows.append([str(st.index), dec(st.v, 6), f"«{short_sym(st.symbol)}»",
                         dec(st.low, d), dec(st.high, d)])
        self.table(f"Декодирование (формулы ({n_v}), ({n_s}))",
                   ["i", "vᵢ", "sᵢ", "lᵢ", "hᵢ"], rows, ["c", "l", "c", "l", "l"])
        ok = a.decoded == a.message
        self.p("Результат декодирования: «"
               f"{a.decoded if len(a.decoded) <= 60 else a.decoded[:57] + '…'}» — "
               + ("совпадает с исходным сообщением." if ok else "ОШИБКА: не совпадает."))

        self._int_section(a, detailed, section=6, refs=(n_l, n_hh))
        self._comparison(a, section=7, n_h=n_h, n_w=n_w)

    # ------------------------------------------------------------------
    def _int_section(self, a: Analysis, detailed: bool, section: int, refs):
        m = a.int_model
        self.h1(f"{section} Целочисленная реализация (32-битный кодер)")
        ref = (f" — целочисленный аналог формул ({refs[0]}) и ({refs[1]})"
               if refs else "")
        self.p("В компьютере границы хранятся не дробями, а 32-битными целыми числами: "
               "нижняя граница L и ширина R. Вместо вероятностей используются частоты "
               f"f(a) и накопленные частоты C(a), их сумма T = {m.total}" + ref + ":")
        n_r = self.formula(r"r = \left\lfloor \dfrac{R}{T} \right\rfloor,")
        self.formula(r"L \leftarrow L + r\cdot C(s),")
        self.formula(r"R \leftarrow r\cdot f(s).")
        self.p("Когда ширина становится меньше ", ("$", "2^{24}"),
               ", старший байт L уже не изменится (кроме возможного переноса): "
               "он выводится в результат, а L и R сдвигаются на 8 бит:")
        self.formula(r"R \leftarrow 2^{8} R,\qquad L \leftarrow 2^{8} L \bmod 2^{32}.")
        self.where([("L", "нижняя граница интервала (целое число)"),
                    ("R", "ширина интервала, в начале  R = 2³² − 1 = 4 294 967 295"),
                    ("C(s),\\ f(s)", "накопленная частота и частота символа s"),
                    ("T", "сумма частот всех символов")])
        if m is not a.model:
            self.p(f"Частоты уменьшены пропорционально, чтобы T < {rc.MAX_TOTAL}.",
                   tag="note")

        trace = a.int_trace
        if detailed:
            self.h2(f"{section}.1 Вычисления по шагам")
            limit = min(len(trace), DETAIL_INT_STEPS)
            for i, (s, t) in enumerate(zip(a.message, trace[:limit]), 1):
                self.p(f"Шаг {i}. ", ("$", rf"s = {tex_sym(s)}"), ", ",
                       ("$", rf"C(s) = {t['cum']}"), ", ", ("$", rf"f(s) = {t['freq']}"),
                       ".", tag="step")
                self.formula(rf"r = \left\lfloor \dfrac{{{tex_int(t['range_in'])}}}"
                             rf"{{{t['total']}}} \right\rfloor = {tex_int(t['r'])}",
                             numbered=False, size=STEP_FORMULA_SIZE)
                self.formula(rf"L = {tex_int(t['low_in'])} + {tex_int(t['r'])}\cdot "
                             rf"{t['cum']} = {tex_int(t['low_mid'])}",
                             numbered=False, size=STEP_FORMULA_SIZE)
                self.formula(rf"R = {tex_int(t['r'])}\cdot {t['freq']} = "
                             rf"{tex_int(t['range_mid'])}",
                             numbered=False, size=STEP_FORMULA_SIZE)
                if t["shifts"]:
                    self.p(f"R < 2²⁴ — выполняется нормализация ({t['shifts']} байт):",
                           tag="note")
                    k8 = 8 * t["shifts"]
                    self.formula(rf"R = {tex_int(t['range_mid'])}\cdot 2^{{{k8}}}"
                                 rf" = {tex_int(t['range_out'])}",
                                 numbered=False, size=STEP_FORMULA_SIZE)
                    self.formula(rf"L = \left({tex_int(t['low_mid'])}\cdot 2^{{{k8}}}\right)"
                                 rf"\bmod 2^{{32}} = {tex_int(t['low_out'])}",
                                 numbered=False, size=STEP_FORMULA_SIZE)
            if len(trace) > limit:
                self.p(f"Подробные вычисления показаны для первых {limit} шагов.",
                       tag="note")

        rows = []
        for i, (s, t) in enumerate(zip(a.message, trace), 1):
            rows.append([str(i), f"«{short_sym(s)}»", plain_int(t["r"]),
                         f"{t['low_out'] & rc.MASK32:08X}", f"{t['range_out']:08X}",
                         str(t["shifts"]) if t["shifts"] else "—"])
        self.table(f"Состояние 32-битного кодера после каждого шага (r — по формуле ({n_r}))",
                   ["i", "s", "r", "L (16-ричн.)", "R (16-ричн.)", "Выведено\nбайт"],
                   rows, ["c", "c", "r", "c", "c", "c"])
        data = a.int_data
        hex_bytes = " ".join(f"{b:02X}" for b in data[:40]) + (" …" if len(data) > 40 else "")
        self.p(f"Результат: {len(data)} байт ({len(data) * 8} бит): {hex_bytes or '—'}. "
               "Декодирование 32-битного кода: "
               + ("результат совпадает с исходным сообщением." if a.int_ok
                  else "ОШИБКА."))

    def _comparison(self, a: Analysis, section: int, n_h=None, n_w=None):
        self.h1(f"{section} Сравнение результатов")
        m = len(a.model.symbols)
        fixed = a.n * max(1, math.ceil(math.log2(m))) if m > 1 else a.n
        utf8 = len(a.message.encode("utf-8")) * 8
        rows = [["Исходный текст в кодировке UTF-8", plain_int(utf8), dec(utf8 / a.n, 3)],
                [f"Равномерный код (⌈log₂ {m}⌉ бит на символ)", plain_int(fixed),
                 dec(fixed / a.n, 3)],
                ["Граница Шеннона n·H", dec(a.n * a.entropy, 1), dec(a.entropy, 3)]]
        if a.exact:
            rows.append(["Арифметический код (точные дроби)", str(len(a.code_bits)),
                         dec(len(a.code_bits) / a.n, 3)])
        bits = len(a.int_data) * 8
        rows.append(["32-битный интервальный кодер", plain_int(bits), dec(bits / a.n, 3)])
        self.table("Объём закодированного сообщения",
                   ["Способ кодирования", "Объём, бит", "Бит на символ"], rows,
                   ["l", "r", "r"])
        self.p("Таблица вероятностей (таблица 1) тоже должна быть известна декодеру; "
               "её объём в сравнении не учтён.", tag="note")
