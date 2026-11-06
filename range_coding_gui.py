#!/usr/bin/env python3
"""
Графическое приложение «Интервальное кодирование» (учебная программа).

Вкладки:
  * «Кодирование»     — таблица сужения интервала, просмотр по шагам;
  * «Декодирование»   — таблица восстановления сообщения по коду, по шагам;
  * «Пошаговый отчёт» — формулы и вычисления, оформленные по ГОСТ 7.32;
  * «Справка»         — как пользоваться программой.

Интерфейс построен по принципам ГОСТ Р ИСО 9241-110 (соответствие задаче,
информативность, соответствие ожиданиям пользователя, устойчивость к ошибкам):
у каждого действия есть понятная подпись и горячая клавиша, ошибки ввода
сообщаются в строке состояния с указанием, что исправить.

Запуск:  python3 range_coding_gui.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gui_analysis import analyse
from gui_diagrams import DecodeDiagram, EncodeDiagram, serif_family
from gui_formula import dec, plain_int
from gui_report import ReportView

APP_TITLE = "Интервальное кодирование — учебная программа"
DEFAULT_MESSAGE = "КОЛОКОЛ"
MAX_MESSAGE_LEN = 200_000
EXAMPLES = ["КОЛОКОЛ", "abracadabra", "РАДИОВИЗИР", "ИНТЕРВАЛЬНОЕ КОДИРОВАНИЕ",
            "AAAAAAAAAB", "мама мыла раму"]

HELP_TEXT = """\
Назначение программы

Программа показывает, как работает интервальное (арифметическое) кодирование: \
сообщение записывается одним числом из отрезка [0; 1). Каждый символ сужает \
текущий интервал пропорционально своей вероятности; чем вероятнее символ, тем \
меньше он сужает интервал и тем меньше бит требуется для его записи.

Порядок работы

1. Введите сообщение в поле «Исходное сообщение» (или выберите пример, или \
откройте текстовый файл: «Файл → Открыть…», Ctrl+O).
2. Нажмите «Закодировать» (Ctrl+Enter). В блоке «Результат» появятся основные \
величины: энтропия, длина кода, проверка декодирования.
3. Вкладка «Кодирование»: таблица шагов. В каждой строке — кодируемый символ \
(каждый символ сообщения окрашен своим цветом), его вероятность p и нижняя \
граница его интервала Q, новые границы интервала l и h и ширина интервала. \
Над таблицей — сообщение и интервалы всех символов.
4. Вкладка «Декодирование»: декодер получает код x и длину n. В каждой строке — \
текущий интервал, положение кода в нём v = (x − l) / (h − l) и символ, \
в интервал которого попало v. Можно ввести свой код и посмотреть, что получится. \
Вероятности символов декодер берёт из кодирования (он должен знать их заранее), \
а длина n нужна, чтобы знать, когда остановиться.
5. Кнопки «⏮ В начало», «◀ Назад», «Вперёд ▶», «Все шаги ⏭» позволяют пройти \
кодирование и декодирование по одному шагу; текущая строка выделяется, \
над таблицей выводится пояснение с вычислениями.
6. Вкладка «Пошаговый отчёт» содержит формулы, таблицы и итоговое сравнение. \
Флажок «Подробные шаги в отчёте» (рядом с кнопкой «Закодировать») добавляет \
вычисления с подставленными числами для каждого шага. Кнопка «Сохранить отчёт для Word…» (Ctrl+S) сохраняет отчёт \
в файл, который открывается в Microsoft Word и LibreOffice Writer.

Оформление

Отчёт оформлен по правилам ГОСТ 7.32-2017 и ГОСТ 2.105-2019: нумерация разделов, \
формулы в отдельной строке с номером в круглых скобках у правого края, пояснение \
символов со слова «где», заголовки таблиц «Таблица N — …», десятичный \
разделитель — запятая. Интерфейс выполнен с учётом \
ГОСТ Р ИСО 9241-110 (принципы организации диалога).

Клавиши

Ctrl+Enter — закодировать; Ctrl+O — открыть файл; Ctrl+S — сохранить отчёт; \
F1 — эта справка; Ctrl+1 … Ctrl+4 — переход между вкладками.
"""


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        # окно помещается на экран (с запасом на панель задач)
        width = min(1240, self.winfo_screenwidth() - 40)
        height = min(900, self.winfo_screenheight() - 80)
        self.geometry(f"{width}x{height}+10+10")
        self.minsize(900, 560)
        if self.winfo_screenheight() <= 820:          # ноутбуки 1366×768 и т. п.
            try:
                self.state("zoomed")                  # Windows
            except tk.TclError:
                try:
                    self.attributes("-zoomed", True)  # Linux (X11)
                except tk.TclError:
                    pass
        self.serif = serif_family(self)
        self.detailed = tk.BooleanVar(value=False)
        self.analysis = None
        self.report_dirty = False

        style = ttk.Style(self)
        style.configure("Big.TButton", font=("TkDefaultFont", 11, "bold"), padding=(12, 6))
        style.configure("Key.TLabel", foreground="#404040")
        style.configure("Value.TLabel", font=("TkDefaultFont", 10, "bold"))

        self._build_menu()
        self._build_status()      # первой: строка состояния всегда видна внизу
        self._build_input()
        self._build_summary()
        self._build_tabs()
        self._bind_keys()

        self.input.insert("1.0", DEFAULT_MESSAGE)
        self._update_counter()
        self.after(100, self.encode)

    # ================================================================== UI
    def _build_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Открыть сообщение из файла…", accelerator="Ctrl+O",
                              command=self.open_file)
        file_menu.add_command(label="Сохранить отчёт для Word…", accelerator="Ctrl+S",
                              command=self.save_report)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)
        menu.add_cascade(label="Файл", menu=file_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        for k, name in enumerate(["Кодирование", "Декодирование", "Пошаговый отчёт",
                                  "Справка"], 1):
            view_menu.add_command(label=name, accelerator=f"Ctrl+{k}",
                                  command=lambda i=k - 1: self.tabs.select(i))
        menu.add_cascade(label="Вид", menu=view_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Как пользоваться программой", accelerator="F1",
                              command=lambda: self.tabs.select(3))
        help_menu.add_command(label="О программе", command=self.about)
        menu.add_cascade(label="Справка", menu=help_menu)
        self.configure(menu=menu)

    def _build_input(self):
        box = ttk.LabelFrame(self, text="Исходное сообщение", padding=(10, 4))
        box.pack(fill="x", padx=10, pady=(6, 2))
        self.input_box = box

        self.input = tk.Text(box, height=1, wrap="word", font=(self.serif, 14),
                             undo=True, relief="solid", borderwidth=1)
        self.input.grid(row=0, column=0, columnspan=6, sticky="we")
        self.input.bind("<<Modified>>", self._on_modified)
        box.columnconfigure(5, weight=1)

        ttk.Button(box, text="Закодировать (Ctrl+Enter)", style="Big.TButton",
                   command=self.encode).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(box, text="Открыть файл…", command=self.open_file).grid(
            row=1, column=1, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Button(box, text="Очистить", command=self.clear_input).grid(
            row=1, column=2, sticky="w", padx=6, pady=(6, 0))

        ex = ttk.Frame(box)
        ex.grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(ex, text="Пример:").pack(side="left")
        self.example = ttk.Combobox(ex, values=EXAMPLES, state="readonly", width=24)
        self.example.set("— выберите —")
        self.example.pack(side="left", padx=4)
        self.example.bind("<<ComboboxSelected>>", self._on_example)

        ttk.Checkbutton(box, variable=self.detailed, command=self._on_detail_toggle,
                        text="Подробные шаги в отчёте").grid(
            row=1, column=4, sticky="w", padx=(12, 0), pady=(6, 0))

    def _build_summary(self):
        box = ttk.LabelFrame(self, text="Результат", padding=(10, 2))
        box.pack(fill="x", padx=10, pady=2)
        self.values = {}
        fields = [
            ("n", "Длина сообщения n:"), ("m", "Различных символов m:"),
            ("H", "Энтропия H:"), ("I", "Информация I:"),
            ("k", "Длина кода:"), ("int", "32-битный кодер:"),
            ("check", "Декодирование:"), ("ratio", "Сжатие к UTF-8:"),
        ]
        for col in range(8):
            box.columnconfigure(col, weight=1 if col % 2 else 0)
        for idx, (key, label) in enumerate(fields):
            r, col = divmod(idx, 4)
            ttk.Label(box, text=label, style="Key.TLabel").grid(
                row=r, column=col * 2, sticky="e", padx=(12 if col else 0, 4), pady=2)
            val = ttk.Label(box, text="—", style="Value.TLabel")
            val.grid(row=r, column=col * 2 + 1, sticky="w", pady=2)
            self.values[key] = val

    def _build_tabs(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=4)
        self.encode_view = EncodeDiagram(self.tabs, status_callback=self.set_status)
        self.decode_view = DecodeDiagram(self.tabs, status_callback=self.set_status)
        self.report = ReportView(self.tabs, status_callback=self.set_status)
        help_frame = ttk.Frame(self.tabs)
        self.tabs.add(self.encode_view, text="  Кодирование  ")
        self.tabs.add(self.decode_view, text="  Декодирование  ")
        self.tabs.add(self.report, text="  Пошаговый отчёт  ")
        self.tabs.add(help_frame, text="  Справка  ")
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab)

        text = tk.Text(help_frame, wrap="word", font=(self.serif, 13), padx=40, pady=20,
                       relief="flat", bg="#ffffff")
        sb = ttk.Scrollbar(help_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.tag_configure("h", font=(self.serif, 14, "bold"), spacing1=12, spacing3=6)
        text.tag_configure("p", spacing1=2, spacing3=4, lmargin1=36)
        for block in HELP_TEXT.split("\n\n"):
            if "\n" not in block and len(block) < 40:
                text.insert("end", block + "\n", "h")
            else:
                for line in block.split("\n"):
                    text.insert("end", line + "\n", "p")
        text.configure(state="disabled")

    def _build_status(self):
        self.status = ttk.Label(self, text="", relief="sunken", anchor="w",
                                padding=(8, 3))
        self.status.pack(fill="x", side="bottom")

    def _bind_keys(self):
        self.bind_all("<Control-Return>", lambda e: (self.encode(), "break")[1])
        self.bind_all("<Control-o>", lambda e: self.open_file())
        self.bind_all("<Control-s>", lambda e: self.save_report())
        self.bind_all("<F1>", lambda e: self.tabs.select(3))
        for k in range(1, 5):
            self.bind_all(f"<Control-Key-{k}>", lambda e, i=k - 1: self.tabs.select(i))

    # =============================================================== события
    def set_status(self, text: str):
        self.status.configure(text=text)

    def _on_modified(self, _event=None):
        if self.input.edit_modified():
            self._update_counter()
            self.input.edit_modified(False)

    def _update_counter(self):
        n = len(self.input.get("1.0", "end-1c"))
        self.input_box.configure(text=f"Исходное сообщение ({n} симв.)")

    def _on_example(self, _event=None):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", self.example.get())
        self.example.set("— выберите —")
        self.encode()

    def _on_tab(self, _event=None):
        if self.tabs.index("current") == 2 and self.report_dirty:
            self.build_report()

    def _on_detail_toggle(self):
        self.report_dirty = True
        if self.tabs.index("current") == 2:
            self.build_report()
        else:
            self.set_status("Отчёт будет перестроен при открытии вкладки "
                            "«Пошаговый отчёт».")

    def clear_input(self):
        self.input.delete("1.0", "end")
        self.input.focus_set()
        self.set_status("Поле очищено. Введите сообщение и нажмите «Закодировать».")

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Открыть сообщение",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            messagebox.showerror(APP_TITLE, "Файл не в кодировке UTF-8. Сохраните его "
                                            "в UTF-8 и повторите попытку.")
            return
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Не удалось прочитать файл:\n{exc}")
            return
        if len(text) > MAX_MESSAGE_LEN:
            messagebox.showwarning(APP_TITLE, f"Файл слишком большой; будут "
                                              f"использованы первые {MAX_MESSAGE_LEN} символов.")
            text = text[:MAX_MESSAGE_LEN]
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.encode()

    def about(self):
        messagebox.showinfo(
            "О программе",
            "Интервальное кодирование — учебная программа.\n\n"
            "Показывает кодирование и декодирование сообщения методом "
            "интервального (арифметического) кодирования: точный расчёт "
            "на дробях и практический 32-битный кодер.")

    # ============================================================= действия
    def encode(self):
        message = self.input.get("1.0", "end-1c")
        if message.endswith("\n"):
            message = message.rstrip("\n")
        if not message:
            self.bell()
            self.set_status("Ошибка: сообщение пустое. Введите хотя бы один символ "
                            "в поле «Исходное сообщение».")
            self.input.focus_set()
            return
        if len(message) > MAX_MESSAGE_LEN:
            message = message[:MAX_MESSAGE_LEN]
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            a = analyse(message)
        finally:
            self.configure(cursor="")
        self.analysis = a
        self._fill_summary(a)
        self.encode_view.set_analysis(a)
        self.decode_view.set_analysis(a)
        self.report_dirty = True
        if self.tabs.index("current") == 2:
            self.build_report()
        ok = a.int_ok and (not a.exact or a.decoded == message)
        self.set_status(f"Сообщение закодировано ({a.n} симв.). "
                        + ("Декодирование проверено: совпадает." if ok
                           else "Внимание: декодирование не совпало."))

    def _fill_summary(self, a):
        v = self.values
        v["n"].configure(text=f"{a.n} симв.")
        v["m"].configure(text=str(len(a.model.symbols)))
        v["H"].configure(text=f"{dec(a.entropy, 4)} бит/симв.")
        v["I"].configure(text=f"{dec(a.information, 2)} бит")
        v["k"].configure(text=f"{len(a.code_bits)} бит" if a.exact else "— (n > 300)")
        bits = len(a.int_data) * 8
        v["int"].configure(text=f"{len(a.int_data)} байт = {plain_int(bits)} бит")
        ok = a.int_ok and (not a.exact or a.decoded == a.message)
        v["check"].configure(text="совпадает ✓" if ok else "ОШИБКА ✗",
                             foreground="#000000" if ok else "#b00000")
        utf8 = len(a.message.encode("utf-8")) * 8
        v["ratio"].configure(text=f"в {dec(utf8 / max(bits, 1), 2)} раза"
                             if bits else "—")

    def save_report(self):
        if self.analysis is None:
            self.set_status("Сначала закодируйте сообщение.")
            return
        if self.report_dirty:
            self.build_report()
        self.report.save_docx()

    def build_report(self):
        if self.analysis is None:
            return
        self.configure(cursor="watch")
        self.set_status("Формирование отчёта…")
        self.update_idletasks()
        try:
            self.report.build(self.analysis, self.detailed.get())
        finally:
            self.configure(cursor="")
        self.report_dirty = False
        self.set_status("Отчёт сформирован." + (
            " Подробные шаги включены." if self.detailed.get() else
            " Для арифметики каждого шага включите «Подробные шаги в отчёте»."))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
