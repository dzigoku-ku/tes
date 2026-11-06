"""
Вкладки «Кодирование» и «Декодирование»: пошаговые таблицы без графиков.

Каждый символ сообщения окрашен своим цветом (во всех строках, в легенде
и в итоговом сообщении), чтобы было видно, какой символ обрабатывается
на каждом шаге. Таблицы можно просматривать по одному шагу: текущая строка
выделяется, над таблицей выводится пояснение с вычислениями.
"""

from __future__ import annotations

import tkinter as tk
from fractions import Fraction
from tkinter import font as tkfont
from tkinter import ttk

from gui_analysis import Analysis
from gui_formula import dec, digits_for, short_sym

MAX_STEPS = 300            # столько же, сколько считается точно (EXACT_LIMIT)

INK = "#000000"
MUTED = "#505050"
CURRENT_ROW = "#fff3bf"
HEADER_BG = "#ececec"
# Тёмные насыщенные цвета: хорошо читаются на белом фоне
SYMBOL_COLORS = ["#1c56b8", "#d9480f", "#2b8a3e", "#c2255c", "#6741d9", "#0b7285",
                 "#b35c00", "#5c940d", "#a61e4d", "#364fc7", "#087f5b", "#862e9c",
                 "#e8590c", "#1098ad", "#9c36b5", "#2f9e44", "#c92a2a", "#495057"]


def pick_family(root: tk.Misc, candidates: list[str]) -> str:
    available = {f.lower(): f for f in tkfont.families(root)}
    for name in candidates:
        if name.lower() in available:
            return available[name.lower()]
    return candidates[-1]


def serif_family(root: tk.Misc) -> str:
    return pick_family(root, ["Times New Roman", "Liberation Serif",
                              "Tinos", "DejaVu Serif", "Times"])


def frac_text(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def sub(n: int) -> str:
    """Нижний индекс юникодом: 12 → ₁₂."""
    return str(n).translate(str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉"))


class StepTable(ttk.Frame):
    """Общая часть: панель шагов, пояснение, цветная легенда и таблица шагов."""

    columns: list[tuple[str, int]] = []      # (заголовок, ширина колонки в px)

    def __init__(self, master, status_callback=None):
        super().__init__(master)
        self.status = status_callback or (lambda text: None)
        self.serif = serif_family(self)
        self.analysis: Analysis | None = None
        self.current = 0
        self.total_steps = 0

        self.extra = ttk.Frame(self)           # место для полей ввода (декодер)
        self.extra.pack(fill="x", padx=8, pady=(8, 0))

        nav = ttk.Frame(self)
        nav.pack(fill="x", padx=8, pady=4)
        self.btn_first = ttk.Button(nav, text="⏮ В начало", command=self.go_first)
        self.btn_prev = ttk.Button(nav, text="◀ Назад", command=self.go_prev)
        self.btn_next = ttk.Button(nav, text="Вперёд ▶", command=self.go_next)
        self.btn_all = ttk.Button(nav, text="Все шаги ⏭", command=self.go_all)
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_all):
            b.pack(side="left", padx=(0, 4))
        self.step_label = ttk.Label(nav, text="", font=(self.serif, 12, "bold"))
        self.step_label.pack(side="left", padx=12)

        self.explain = tk.Label(self, justify="left", anchor="nw", padx=10, pady=5,
                                bg="#f4f4f4", fg=INK, relief="groove",
                                font=(self.serif, 12))
        self.explain.pack(fill="x", padx=8)
        self.explain.bind("<Configure>",
                          lambda e: self.explain.configure(wraplength=e.width - 24))

        # Неподвижная панель: сообщение цветными буквами и интервалы символов
        self.info = tk.Text(self, height=2, wrap="word", bg="#ffffff", fg=INK,
                            padx=14, pady=6, font=(self.serif, 13), cursor="arrow",
                            relief="flat", highlightthickness=1,
                            highlightbackground="#a0a0a0")
        self.info.pack(fill="x", padx=8, pady=(8, 0))
        self.info.bind("<Configure>", self._fit_info)

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text = tk.Text(holder, wrap="none", bg="#ffffff", fg=INK, padx=14, pady=10,
                            font=(self.serif, 13), cursor="arrow", relief="flat",
                            highlightthickness=1, highlightbackground="#a0a0a0")
        vbar = ttk.Scrollbar(holder, orient="vertical", command=self.text.yview)
        hbar = ttk.Scrollbar(holder, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        vbar.pack(side="right", fill="y")
        hbar.pack(side="bottom", fill="x")
        self.text.pack(side="left", fill="both", expand=True)

        f = self.serif
        for widget in (self.text, self.info):
            widget.tag_configure("title", font=(f, 13, "bold"))
            widget.tag_configure("muted", foreground=MUTED, font=(f, 12))
            widget.tag_configure("current", background=CURRENT_ROW)
            widget.tag_configure("big", font=(f, 18, "bold"))
        self.info.configure(state="disabled")
        stops, x = [], 0
        for _title, width in self.columns:
            x += width
            stops.append(x)
        t = self.text
        t.configure(tabs=tuple(stops))
        t.tag_configure("title", font=(f, 13, "bold"), spacing1=4, spacing3=4)
        t.tag_configure("muted", foreground=MUTED, font=(f, 12))
        t.tag_configure("header", font=(f, 12, "bold"), background=HEADER_BG,
                        spacing1=4, spacing3=4)
        t.tag_configure("row", spacing1=3, spacing3=3)
        t.tag_configure("current", background=CURRENT_ROW)
        t.tag_configure("big", font=(f, 18, "bold"))
        t.tag_configure("gap", font=(f, 6))
        t.configure(state="disabled")
        self.set_explanation("Введите сообщение и нажмите «Закодировать».")
        self._update_nav()

    # ------------------------------------------------------------ цвета
    def color_tag(self, widget: tk.Text, symbol: str, big: bool = False) -> str:
        """Тег текста с цветом символа (создаётся при первом обращении)."""
        idx = self.analysis.model.symbols.index(symbol)
        name = f"sym{idx}{'_big' if big else ''}"
        if name not in widget.tag_names():
            size = 18 if big else 13
            widget.tag_configure(name, font=(self.serif, size, "bold"),
                                 foreground=SYMBOL_COLORS[idx % len(SYMBOL_COLORS)])
        return name

    def put(self, text: str, *tags: str, widget: tk.Text | None = None):
        (widget or self.text).insert("end", text, tags)

    def put_symbol(self, symbol: str, *tags: str, big: bool = False,
                   widget: tk.Text | None = None):
        w = widget or self.text
        w.insert("end", short_sym(symbol), (self.color_tag(w, symbol, big),) + tags)

    def header(self):
        self.put("\t".join(title for title, _ in self.columns) + "\n", "header")

    def legend(self):
        """Строка «Символы:» — каждый символ своим цветом, с вероятностью."""
        a = self.analysis
        w = self.info
        self.put("\nСимволы и их интервалы:  ", "muted", widget=w)
        for s in a.model.symbols:
            self.put_symbol(s, widget=w)
            p, q = a.p(s), a.q(s)
            self.put(f" p = {frac_text(p)}, [{frac_text(q)}; {frac_text(q + p)})     ",
                     "muted", widget=w)

    # -------------------------------------------------------------- шаги
    def go_first(self):
        self.current = 0
        self._changed()

    def go_prev(self):
        self.current = max(0, self.current - 1)
        self._changed()

    def go_next(self):
        self.current = min(self.total_steps, self.current + 1)
        self._changed()

    def go_all(self):
        self.current = self.total_steps
        self._changed()

    def _changed(self):
        self._update_nav()
        self.redraw()
        self.describe()
        # показываем начало таблицы; прокручиваем, только если строка не видна
        self.text.yview_moveto(0)
        if 0 < self.current < self.total_steps:
            self.text.see("current.last")

    def _update_nav(self):
        has = self.total_steps > 0
        back = "normal" if has and self.current > 0 else "disabled"
        fwd = "normal" if has and self.current < self.total_steps else "disabled"
        self.btn_first.configure(state=back)
        self.btn_prev.configure(state=back)
        self.btn_next.configure(state=fwd)
        self.btn_all.configure(state=fwd)
        self.step_label.configure(
            text=f"Шаг {self.current} из {self.total_steps}" if has else "")

    def set_explanation(self, text: str):
        self.explain.configure(text=text)

    def begin(self):
        for w in (self.text, self.info):
            w.configure(state="normal")
            w.delete("1.0", "end")

    def end(self):
        for w in (self.text, self.info):
            w.configure(state="disabled")
        self._fit_info()

    def _fit_info(self, _event=None):
        """Высота панели — по числу строк на экране (легенда может переноситься)."""
        if self.info.winfo_width() <= 1:          # вкладка ещё не показана
            return
        lines = self.info.count("1.0", "end", "displaylines")
        lines = lines[0] if isinstance(lines, tuple) else (lines or 1)
        height = max(1, min(lines, 5)) + 1        # +1: крупная строка выше обычной
        if int(self.info.cget("height")) != height:
            self.info.configure(height=height)

    def redraw(self):
        raise NotImplementedError

    def describe(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Кодирование
# ---------------------------------------------------------------------------

class EncodeDiagram(StepTable):
    columns = [("Шаг", 70), ("Символ", 90), ("p(sᵢ)", 90), ("Q(sᵢ)", 90),
               ("lᵢ — нижняя граница", 230), ("hᵢ — верхняя граница", 230),
               ("hᵢ − lᵢ (ширина)", 200)]

    def set_analysis(self, analysis: Analysis):
        self.analysis = analysis
        self.total_steps = min(len(analysis.steps), MAX_STEPS) if analysis.exact else 0
        self.current = self.total_steps
        self._update_nav()
        self.redraw()
        self.describe()
        self.text.yview_moveto(0)

    def redraw(self):
        self.begin()
        a = self.analysis
        if a is None:
            self.end()
            return
        if not a.exact:
            self.put("Пошаговая таблица строится для сообщений длиной до 300 символов. "
                     "Результаты 32-битного кодера — во вкладке «Пошаговый отчёт».",
                     "muted")
            self.end()
            return

        # Сообщение: все буквы цветные, уже закодированные — крупно
        self.put("Сообщение:  ", "title", widget=self.info)
        for k, s in enumerate(a.message[:MAX_STEPS], 1):
            tags = ("current",) if k == self.current < self.total_steps else ()
            self.put_symbol(s, *tags, big=True, widget=self.info)
        self.legend()

        self.header()
        self.put("0\t—\t—\t—\t0\t1\t1\n", "row")
        for st in a.steps[:self.current]:
            d = min(digits_for(st.width), 16)
            tags = ("row", "current") if (st.index == self.current
                                          and self.current < self.total_steps) else ("row",)
            self.put(f"{st.index}\t", *tags)
            self.put_symbol(st.symbol, *tags)
            self.put(f"\t{frac_text(st.p)}\t{frac_text(st.q)}\t{dec(st.low, d)}\t"
                     f"{dec(st.high, d)}\t{dec(st.width, d)}\n", *tags)
        if self.current == len(a.steps):
            last = a.steps[-1]
            d = min(digits_for(last.width), 24)
            self.put("\n", "gap")
            self.put("Итоговый интервал:  ", "title")
            self.put(f"[{dec(last.low, d)}; {dec(last.high, d)})\n")
            self.put("Код (кратчайшая двоичная дробь в интервале):  ", "title")
            self.put(f"x = 0,{a.code_bits}₂  ({len(a.code_bits)} бит)\n")
        self.end()

    def describe(self):
        a = self.analysis
        if a is None:
            return
        if not a.exact:
            self.set_explanation(f"Сообщение слишком длинное ({a.n} символов) для "
                                 "пошаговой таблицы.")
            return
        k = self.current
        if k == 0:
            self.set_explanation(
                "Начальное состояние: интервал [l₀; h₀) = [0; 1). Каждому символу "
                "отведён свой интервал длиной p (строка «Символы и их интервалы»). "
                "Нажмите «Вперёд ▶», чтобы закодировать первый символ.")
            return
        if k == len(a.steps):
            self.set_explanation(
                f"Закодированы все {a.n} символов. Ширина итогового интервала равна "
                f"произведению вероятностей всех символов. Код — кратчайшая двоичная "
                f"дробь из итогового интервала: x = 0,{a.code_bits}₂ "
                f"({len(a.code_bits)} бит). Кнопками «◀ Назад» / «Вперёд ▶» можно "
                "просмотреть шаги по одному.")
            return
        st = a.steps[k - 1]
        d = min(digits_for(st.width, minimum=6), 16)
        dp = min(digits_for(st.width_prev, minimum=6), 16)
        w = st.width_prev
        self.set_explanation(
            f"Шаг {k}. Кодируется символ «{short_sym(st.symbol)}»: p = {frac_text(st.p)}, "
            f"Q = {frac_text(st.q)}.\n"
            f"Ширина текущего интервала: h{sub(k - 1)} − l{sub(k - 1)} = "
            f"{dec(st.high_prev, dp)} − {dec(st.low_prev, dp)} = {dec(w, dp)}.\n"
            f"l{sub(k)} = {dec(st.low_prev, dp)} + {dec(w, dp)} · {frac_text(st.q)} = "
            f"{dec(st.low, d)};   "
            f"h{sub(k)} = {dec(st.low_prev, dp)} + {dec(w, dp)} · "
            f"{frac_text(st.q + st.p)} = {dec(st.high, d)}.")


# ---------------------------------------------------------------------------
# Декодирование
# ---------------------------------------------------------------------------

class DecodeDiagram(StepTable):
    columns = [("Шаг", 70), ("lᵢ₋₁", 200), ("hᵢ₋₁", 200),
               ("vᵢ = (x − l) / (h − l)", 230), ("Интервал символа", 170),
               ("Символ", 90)]

    def __init__(self, master, status_callback=None):
        super().__init__(master, status_callback)
        self.code = None
        self.steps = []
        self.reference = ""

        box = ttk.LabelFrame(self.extra, text="Исходные данные декодера", padding=(8, 4))
        box.pack(fill="x")
        ttk.Label(box, text="Код x:").grid(row=0, column=0, sticky="w")
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(box, textvariable=self.code_var, width=30,
                                    font=("TkFixedFont", 11))
        self.code_entry.grid(row=0, column=1, sticky="we", padx=6)
        self.code_entry.bind("<Return>", lambda e: self.on_decode())
        self.format_var = tk.StringVar(value="bin")
        ttk.Radiobutton(box, text="двоичная", value="bin",
                        variable=self.format_var).grid(row=0, column=2, padx=2)
        ttk.Radiobutton(box, text="десятичная", value="dec",
                        variable=self.format_var).grid(row=0, column=3, padx=(2, 12))
        ttk.Label(box, text="Число символов n:").grid(row=0, column=4, sticky="e")
        self.len_var = tk.StringVar()
        self.len_spin = ttk.Spinbox(box, from_=1, to=MAX_STEPS,
                                    textvariable=self.len_var, width=6)
        self.len_spin.grid(row=0, column=5, sticky="w", padx=(4, 12))
        ttk.Button(box, text="Взять код из кодирования",
                   command=self.reset_from_analysis).grid(row=0, column=6, padx=4)
        ttk.Button(box, text="Декодировать", command=self.on_decode).grid(row=0, column=7)
        box.columnconfigure(1, weight=1)

    # ---------------------------------------------------------- данные
    def set_analysis(self, analysis: Analysis):
        self.analysis = analysis
        self.reset_from_analysis()

    def reset_from_analysis(self):
        a = self.analysis
        if a is None:
            return
        self.len_var.set(str(a.n))
        if not a.exact:
            self.code = None
            self.steps = []
            self.total_steps = self.current = 0
            self.code_var.set("")
            self._update_nav()
            self.redraw()
            self.describe()
            return
        self.code_var.set("0." + a.code_bits)
        self.format_var.set("bin")
        self.on_decode()

    def on_decode(self):
        from gui_analysis import decode_steps, parse_code
        a = self.analysis
        if a is None:
            self.status("Сначала закодируйте сообщение: декодеру нужна таблица вероятностей.")
            return
        try:
            x = parse_code(self.code_var.get(), self.format_var.get() == "bin")
        except ValueError as exc:
            self.status(f"Ошибка в поле «Код x»: {exc}.")
            self.code_entry.focus_set()
            return
        try:
            n = int(self.len_var.get())
            if not 1 <= n <= MAX_STEPS:
                raise ValueError
        except ValueError:
            self.status(f"Число символов n должно быть целым от 1 до {MAX_STEPS}.")
            self.len_spin.focus_set()
            return
        self.code = x
        self.steps = decode_steps(x, n, a.model)
        self.reference = a.message
        self.total_steps = n
        self.current = n
        self._update_nav()
        self.redraw()
        self.describe()
        self.text.yview_moveto(0)
        decoded = "".join(st.symbol for st in self.steps)
        if decoded == a.message:
            self.status("Декодирование выполнено: результат совпадает с исходным сообщением.")
        else:
            self.status("Декодирование выполнено: результат НЕ совпадает с исходным "
                        "сообщением (код не лежит в итоговом интервале или n другое).")

    # ---------------------------------------------------------- таблица
    def redraw(self):
        self.begin()
        a = self.analysis
        if a is None:
            self.end()
            return
        if not self.steps:
            self.put("Нет данных для декодирования.", "muted")
            self.end()
            return
        dx = min(max(digits_for(self.steps[-1].high - self.steps[-1].low), 10), 20)
        self.put("Декодировано:  ", "title", widget=self.info)
        for st in self.steps[:self.current]:
            tags = ("current",) if st.index == self.current < self.total_steps else ()
            self.put_symbol(st.symbol, *tags, big=True, widget=self.info)
        self.put("·" * (len(self.steps) - self.current), "big", "muted", widget=self.info)
        self.put(f"      код x = {dec(self.code, dx)}", "muted", widget=self.info)
        self.legend()
        self.header()
        for st in self.steps[:self.current]:
            d = min(digits_for(st.high_prev - st.low_prev), 16)
            q, p = a.q(st.symbol), a.p(st.symbol)
            tags = ("row", "current") if (st.index == self.current
                                          and self.current < self.total_steps) else ("row",)
            self.put(f"{st.index}\t{dec(st.low_prev, d)}\t{dec(st.high_prev, d)}\t"
                     f"{dec(st.v, 6)}\t[{frac_text(q)}; {frac_text(q + p)})\t", *tags)
            self.put_symbol(st.symbol, *tags)
            self.put("\n", *tags)
        self.end()

    def describe(self):
        a = self.analysis
        if a is None:
            return
        if not self.steps:
            self.set_explanation("Для этого сообщения пошаговое декодирование не "
                                 "строится (слишком длинное).")
            return
        x = self.code
        k = self.current
        if k == 0:
            self.set_explanation(
                "Начальное состояние: интервал [0; 1). На каждом шаге находим "
                "положение кода в текущем интервале v = (x − l) / (h − l) и смотрим, "
                "в интервал какого символа попало v. Нажмите «Вперёд ▶».")
            return
        if k == len(self.steps):
            decoded = "".join(st.symbol for st in self.steps)
            verdict = ("совпадает с исходным сообщением" if decoded == self.reference
                       else "не совпадает с исходным сообщением")
            self.set_explanation(
                f"Декодированы все {len(self.steps)} символов: «{decoded}» — {verdict}. "
                "Кнопками «◀ Назад» / «Вперёд ▶» можно пройти шаги по одному.")
            return
        st = self.steps[k - 1]
        d = min(max(digits_for(st.high_prev - st.low_prev), 10), 18)
        q, p = a.q(st.symbol), a.p(st.symbol)
        self.set_explanation(
            f"Шаг {k}. Текущий интервал [{dec(st.low_prev, d)}; {dec(st.high_prev, d)}).\n"
            f"v = (x − l) / (h − l) = ({dec(x, d)} − {dec(st.low_prev, d)}) / "
            f"({dec(st.high_prev, d)} − {dec(st.low_prev, d)}) = {dec(st.v, 6)}.\n"
            f"{frac_text(q)} ≤ {dec(st.v, 6)} < {frac_text(q + p)}, то есть v попадает в "
            f"интервал символа «{short_sym(st.symbol)}» → декодирован символ "
            f"«{short_sym(st.symbol)}».")
