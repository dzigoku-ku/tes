"""
Экспорт пошагового отчёта в документ Word (.docx).

Оформление по ГОСТ 7.32-2017:
  * поля: левое 30 мм, правое 15 мм, верхнее и нижнее 20 мм;
  * шрифт Times New Roman 14 пт, межстрочный интервал 1,5,
    абзацный отступ 1,25 см, выравнивание по ширине;
  * заголовки разделов — с абзацного отступа, полужирные, без точки;
  * формулы — редактируемые формулы Word (OMML) по центру,
    номер в круглых скобках у правого края;
  * «Таблица N — Название» — над таблицей, без отступа;
  * номера страниц — внизу по центру.
"""

from __future__ import annotations

import os
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt

from gui_omml import tex_to_omml

FONT = "Times New Roman"
TEXT_WIDTH = Mm(210 - 30 - 15)
ALIGN = {"l": WD_ALIGN_PARAGRAPH.LEFT, "c": WD_ALIGN_PARAGRAPH.CENTER,
         "r": WD_ALIGN_PARAGRAPH.RIGHT}


def _set_font(style_or_run, size: float | None = None):
    font = style_or_run.font
    font.name = FONT
    if size:
        font.size = Pt(size)
    element = style_or_run.element
    rpr = element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), FONT)


def _math(paragraph, tex: str):
    """Формула Word (OMML); если формулу не удалось разобрать — обычный текст."""
    try:
        paragraph._p.append(parse_xml(tex_to_omml(tex)))
    except ValueError:
        paragraph.add_run(tex)


def _page_number(section):
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.paragraph_format.first_line_indent = Cm(0)
    run = footer.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), kind)
            run._r.append(fld)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = text
            run._r.append(instr)


def _no_indent(paragraph, align=WD_ALIGN_PARAGRAPH.LEFT):
    pf = paragraph.paragraph_format
    pf.first_line_indent = Cm(0)
    paragraph.alignment = align
    return pf


def _fix_frozen_templates():
    """В собранной программе (PyInstaller) python-docx ищет шаблоны по пути
    docx/parts/../templates/…; папки docx/parts на диске нет (модули лежат в
    архиве), и в Linux такой путь не открывается. Создаём пустую папку."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        os.makedirs(os.path.join(base, "docx", "parts"), exist_ok=True)


def write_docx(items: list[tuple], path: str):
    _fix_frozen_templates()
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.left_margin, section.right_margin = Mm(30), Mm(15)
    section.top_margin, section.bottom_margin = Mm(20), Mm(20)
    _page_number(section)

    normal = doc.styles["Normal"]
    _set_font(normal, 14)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.first_line_indent = Cm(1.25)
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for item in items:
        kind = item[0]
        if kind == "title":
            par = doc.add_paragraph()
            pfx = _no_indent(par, WD_ALIGN_PARAGRAPH.CENTER)
            pfx.space_after = Pt(12)
            run = par.add_run(item[1])
            run.bold = True

        elif kind in ("h1", "h2"):
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pfx = par.paragraph_format
            pfx.space_before = Pt(12 if kind == "h1" else 6)
            pfx.space_after = Pt(6)
            pfx.keep_with_next = True
            run = par.add_run(item[1])
            run.bold = True

        elif kind == "p":
            _, tag, runs = item
            par = doc.add_paragraph()
            if tag == "step":
                par.paragraph_format.space_before = Pt(6)
                par.paragraph_format.keep_with_next = True
            for r in runs:
                if r[0] == "text":
                    run = par.add_run(r[1])
                else:
                    _math(par, r[1])
                    continue
                if tag in ("step", "note"):
                    run.italic = True
                if tag == "note":
                    run.font.size = Pt(12)

        elif kind == "formula":
            _, tex, number = item
            par = doc.add_paragraph()
            pfx = _no_indent(par)
            pfx.space_before = Pt(6)
            pfx.space_after = Pt(6)
            pfx.tab_stops.add_tab_stop(int(TEXT_WIDTH / 2), WD_TAB_ALIGNMENT.CENTER)
            pfx.tab_stops.add_tab_stop(int(TEXT_WIDTH), WD_TAB_ALIGNMENT.RIGHT)
            par.add_run("\t")
            _math(par, tex)
            if number:
                par.add_run(f"\t({number})")

        elif kind == "where":
            for k, (tex, desc) in enumerate(item[1]):
                par = doc.add_paragraph()
                pfx = _no_indent(par)
                pfx.tab_stops.add_tab_stop(Cm(1.25), WD_TAB_ALIGNMENT.LEFT)
                pfx.left_indent = Cm(1.25)
                pfx.first_line_indent = Cm(-1.25)
                par.add_run("где\t" if k == 0 else "\t")
                _math(par, tex)
                par.add_run(desc)

        elif kind == "table":
            _, caption, headers, rows, align = item
            cap = doc.add_paragraph()
            pfx = _no_indent(cap)
            pfx.space_before = Pt(12)
            pfx.keep_with_next = True
            cap.add_run(caption)

            table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.LEFT
            for j, head in enumerate(headers):
                cell = table.rows[0].cells[j]
                par = cell.paragraphs[0]
                pfx = _no_indent(par, WD_ALIGN_PARAGRAPH.CENTER)
                pfx.line_spacing = 1.0
                run = par.add_run(head.replace("\n", " "))
                run.bold = True
                run.font.size = Pt(12)
            # повторять заголовок таблицы на каждой странице
            tr_pr = table.rows[0]._tr.get_or_add_trPr()
            header = OxmlElement("w:tblHeader")
            header.set(qn("w:val"), "true")
            tr_pr.append(header)
            for i, row in enumerate(rows, 1):
                cells = table.rows[i].cells
                for j, value in enumerate(row):
                    par = cells[j].paragraphs[0]
                    pfx = _no_indent(par, ALIGN[align[j]])
                    pfx.line_spacing = 1.0
                    run = par.add_run(value)
                    run.font.size = Pt(12)
            spacer = doc.add_paragraph()
            spacer.paragraph_format.line_spacing = 1.0

    doc.save(path)
