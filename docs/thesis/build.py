"""Build the thesis (ALT_STORES_VKR.docx) from the Markdown sources in this folder.

Run: build.bat (or .venv\\Scripts\\python.exe build.py). Markup is described in README.md.
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # repository root: image paths are relative to it
OUT = HERE / "ALT_STORES_VKR.docx"
PARTS = ["00_title.md", "00_annotation.md", "01_intro.md", "10_ch1.md", "20_ch2.md",
         "30_ch3.md", "40_ch4.md", "90_conclusion.md", "95_sources_head.md", "99_appendix.md"]
FONT = "Times New Roman"
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}

errors: list[str] = []
STATE = {"fresh": True}  # True right after a page/section break: a chapter heading needs no extra break


# ---------------------------------------------------------------- sources
def load_sources():
    """95_sources.md: '## group' lines and '- [key] text :: check-url' entries."""
    groups, order, data = [], [], {}
    text = re.sub(r"<!--.*?-->", "", (HERE / "95_sources.md").read_text(encoding="utf-8"), flags=re.S)
    for line in text.splitlines():
        if line.startswith("## "):
            groups.append((line[3:].strip(), []))
        m = re.match(r"- \[([\w-]+)\]\s+(.+?)(?:\s+::\s+(\S+))?\s*$", line)
        if m:
            key, text, url = m.groups()
            if key in data:
                errors.append(f"duplicate source key {key}")
            order.append(key)
            data[key] = {"text": text, "url": url or "", "n": len(order), "where": []}
            groups[-1][1].append(key)
    return groups, order, data


# ---------------------------------------------------------------- numbering pass
def scan_labels(texts):
    """First pass: number figures, tables and equations by chapter."""
    labels, prefix, counters = {}, "", {}
    for name, text in texts:
        for line in text.splitlines():
            h = re.match(r"#\s+(?:ГЛАВА\s+([IVX]+)|ПРИЛОЖЕНИЕ\s+([А-ЯA-Z]))", line)
            if h:
                prefix = str(ROMAN[h.group(1)]) if h.group(1) else h.group(2)
                counters = {}
            for kind, key in re.findall(r"\{#(fig|tab|eq):([\w-]+)", line):
                counters[kind] = counters.get(kind, 0) + 1
                if f"{kind}:{key}" in labels:
                    errors.append(f"duplicate label {kind}:{key}")
                labels[f"{kind}:{key}"] = f"{prefix}.{counters[kind]}" if prefix else str(counters[kind])
    return labels


# ---------------------------------------------------------------- low-level docx helpers
def set_run_font(run, size=14, bold=None, italic=None, name=FONT):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def fmt(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=1.25, spacing=1.5, before=0, after=0, keep=False):
    pf = p.paragraph_format
    pf.alignment = align
    pf.first_line_indent = Cm(indent) if indent else Cm(0)
    pf.line_spacing = spacing
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if keep:
        pf.keep_with_next = True
    return p


def add_field(paragraph, instr, size=14):
    run = paragraph.add_run()
    set_run_font(run, size)
    for tag, text in (("begin", None), ("instr", instr), ("separate", None), ("text", "1"), ("end", None)):
        if tag == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        elif tag == "text":
            el = OxmlElement("w:t")
            el.text = text
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        run._element.append(el)


def page_break(doc):
    p = doc.add_paragraph()
    fmt(p, indent=0, spacing=1)
    p.add_run().add_break(WD_BREAK.PAGE)
    STATE["fresh"] = True


def cell_borders(table):
    tbl = table._tbl
    tblpr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblpr.append(borders)


# ---------------------------------------------------------------- inline text
class Ctx:
    def __init__(self, labels, sources, part):
        self.labels, self.sources, self.part = labels, sources, part
        self.section = ""


def resolve(text, ctx: Ctx):
    def cite(m):
        out = []
        for item in m.group(1).split(";"):
            item = item.strip()
            mm = re.match(r"@([\w-]+)(.*)", item)
            if not mm or mm.group(1) not in ctx.sources:
                errors.append(f"{ctx.part}: unknown source {item}")
                out.append("??")
                continue
            src = ctx.sources[mm.group(1)]
            where = f"{ctx.part}: {ctx.section}".strip()
            if where not in src["where"]:
                src["where"].append(where)
            out.append(f"{src['n']}{mm.group(2)}")
        return "[" + ", ".join(out) + "]"

    text = re.sub(r"\[(@[^\]]+)\]", cite, text)

    def ref(m):
        key = f"{m.group(1)}:{m.group(2)}"
        if key not in ctx.labels:
            errors.append(f"{ctx.part}: unknown label {key}")
            return "??"
        return f"({ctx.labels[key]})" if m.group(1) == "eq" else ctx.labels[key]

    text = re.sub(r"@(fig|tab|eq):([\w-]+)", ref, text)
    # typography: ' - ' -> en dash surrounded by nbsp-like spaces
    text = text.replace(" -- ", " – ").replace(" — ", " — ")
    return text


def add_inline(p, text, ctx, size=14, bold=False, italic=False):
    text = resolve(text, ctx)
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)", text):
        if not tok:
            continue
        b, i, mono = bold, italic, False
        if tok.startswith("**") and tok.endswith("**"):
            tok, b = tok[2:-2], True
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 1:
            tok, i = tok[1:-1], True
        elif tok.startswith("`") and tok.endswith("`"):
            tok, mono = tok[1:-1], True
        r = p.add_run(tok)
        set_run_font(r, size - (1 if mono else 0), b, i, "Courier New" if mono else FONT)


# ---------------------------------------------------------------- document setup
def setup(doc):
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin, sec.right_margin = Cm(3), Cm(1.5)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    sec.footer_distance = Cm(1)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(14)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), "ru-RU")
    lang.set(qn("w:eastAsia"), "ru-RU")
    st.element.rPr.append(lang)
    for name, size in (("Heading 1", 14), ("Heading 2", 14), ("Heading 3", 14)):
        hs = doc.styles[name]
        hs.font.name, hs.font.size, hs.font.bold = FONT, Pt(size), True
        hs.font.italic = False
        hs.font.color.rgb = None
        rpr = hs.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.insert(0, rf)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(a), FONT)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            if rf.get(qn(a)) is not None:
                del rf.attrib[qn(a)]
        color = rpr.find(qn("w:color"))
        if color is not None:
            rpr.remove(color)
        hs.paragraph_format.line_spacing = 1.5
    for name in ("TOC 1", "TOC 2"):
        try:
            ts = doc.styles[name]
        except KeyError:
            ts = doc.styles.add_style(name, 1)
        ts.font.name, ts.font.size = FONT, Pt(14)
        ts.paragraph_format.line_spacing = 1.5
        ts.paragraph_format.space_after = Pt(0)
        ts.paragraph_format.left_indent = Cm(0 if name == "TOC 1" else 0.75)
    settings = doc.settings.element
    hyph = OxmlElement("w:autoHyphenation")
    hyph.set(qn("w:val"), "true")
    settings.append(hyph)


def numbered_section(doc):
    """New section whose footer shows the page number centered."""
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.footer.is_linked_to_previous = False
    p = sec.footer.paragraphs[0]
    fmt(p, WD_ALIGN_PARAGRAPH.CENTER, indent=0, spacing=1)
    add_field(p, "PAGE", 12)
    STATE["fresh"] = True
    return sec


# ---------------------------------------------------------------- block renderers
def heading(doc, text, level, ctx):
    toc = not text.startswith("*")
    text = text.lstrip("*").strip()
    if level == 1:
        if not STATE["fresh"]:
            page_break(doc)
        p = doc.add_paragraph(style="Heading 1" if toc else None)
        fmt(p, WD_ALIGN_PARAGRAPH.CENTER, indent=0, after=12, keep=True)
        add_inline(p, text.upper(), ctx, bold=True)
    else:
        p = doc.add_paragraph(style=f"Heading {level}" if toc else None)
        fmt(p, WD_ALIGN_PARAGRAPH.LEFT if level == 2 else WD_ALIGN_PARAGRAPH.JUSTIFY,
            indent=1.25, before=12, after=6, keep=True)
        add_inline(p, text, ctx, bold=True)
    ctx.section = re.sub(r"\s+", " ", text)[:60]


def figure(doc, line, ctx):
    m = re.match(r"!\[(.*?)\]\((.+?)\)\{#fig:([\w-]+)(?:\s+width=([\d.]+))?\}", line)
    if not m:
        errors.append(f"{ctx.part}: bad figure line {line[:60]}")
        return
    caption, paths, key, width = m.groups()
    width = float(width or 16)
    p = doc.add_paragraph()
    fmt(p, WD_ALIGN_PARAGRAPH.CENTER, indent=0, spacing=1, before=6, keep=True)
    for i, path in enumerate(paths.split("|")):
        f = ROOT / path.strip()
        if not f.exists():
            errors.append(f"{ctx.part}: missing image {path}")
            continue
        if i:
            p.add_run("  ")
        p.add_run().add_picture(str(f), width=Cm(width))
    c = doc.add_paragraph()
    fmt(c, WD_ALIGN_PARAGRAPH.CENTER, indent=0, spacing=1, before=6, after=12)
    add_inline(c, f"Рисунок {ctx.labels['fig:' + key]} — {caption}", ctx)


def table(doc, caption_line, rows, ctx):
    m = re.match(r"Таблица:\s*(.+?)\s*\{#tab:([\w-]+)((?:\s+\w+=[\d.,]+)*)\}", caption_line)
    if not m:
        errors.append(f"{ctx.part}: bad table caption {caption_line[:60]}")
        return
    caption, key, opts = m.groups()
    opt = dict(o.split("=") for o in opts.split())
    size = int(opt.get("font", 12))
    cap = doc.add_paragraph()
    fmt(cap, WD_ALIGN_PARAGRAPH.RIGHT, indent=0, spacing=1, before=6, after=6, keep=True)
    add_inline(cap, f"Таблица {ctx.labels['tab:' + key]} — {caption}", ctx)
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows
             if not re.match(r"^\|?\s*:?-{2,}", r.strip())]
    ncol = len(cells[0])
    t = doc.add_table(rows=len(cells), cols=ncol)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_borders(t)
    widths = [float(w) for w in opt["widths"].split(",")] if "widths" in opt else None
    if widths:
        total = sum(widths)
        widths = [16.5 * w / total for w in widths]
    for i, row in enumerate(cells):
        if len(row) != ncol:
            errors.append(f"{ctx.part}: table {key} row {i} has {len(row)} cells, need {ncol}")
            row = (row + [""] * ncol)[:ncol]
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            if widths:
                cell.width = Cm(widths[j])
            p = cell.paragraphs[0]
            fmt(p, WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT,
                indent=0, spacing=1)
            add_inline(p, val.replace("<br>", "\n"), ctx, size=size, bold=(i == 0))
    if len(cells) > 1:  # repeat header row on each page
        trpr = t.rows[0]._tr.get_or_add_trPr()
        el = OxmlElement("w:tblHeader")
        el.set(qn("w:val"), "true")
        trpr.append(el)
    after = doc.add_paragraph()
    fmt(after, indent=0, spacing=1)


def code_block(doc, lines):
    for i, line in enumerate(lines):
        p = doc.add_paragraph()
        fmt(p, WD_ALIGN_PARAGRAPH.LEFT, indent=0, spacing=1, after=0,
            keep=i < len(lines) - 1 and len(lines) < 25)
        r = p.add_run(line.replace("\t", "    ") or " ")
        set_run_font(r, 10, name="Courier New")
    p = doc.add_paragraph()
    fmt(p, indent=0, spacing=1)


def equation(doc, line, ctx):
    m = re.match(r"\$\$\s*(.+?)\s*\$\$\s*\{#eq:([\w-]+)\}", line)
    if not m:
        errors.append(f"{ctx.part}: bad equation {line[:60]}")
        return
    p = doc.add_paragraph()
    fmt(p, WD_ALIGN_PARAGRAPH.CENTER, indent=0, before=6, after=6)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Cm(8.25), 1)   # center
    tabs.add_tab_stop(Cm(16.5), 2)   # right
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("\t")
    set_run_font(r)
    add_inline(p, m.group(1), ctx, italic=False)
    r = p.add_run(f"\t({ctx.labels['eq:' + m.group(2)]})")
    set_run_font(r)


def title_line(doc, line, ctx):
    """00_title.md markup: '::c', '::cb', '::r', '::rb', '::l', '::gap N'."""
    m = re.match(r"::(\w+)\s*(.*)", line)
    kind, text = m.groups()
    if kind == "gap":
        for _ in range(int(text or 1)):
            fmt(doc.add_paragraph(), indent=0)
        return
    align = {"c": WD_ALIGN_PARAGRAPH.CENTER, "r": WD_ALIGN_PARAGRAPH.LEFT,
             "l": WD_ALIGN_PARAGRAPH.LEFT}[kind[0]]
    p = doc.add_paragraph()
    fmt(p, align, indent=0, spacing=1.15)
    if kind[0] == "r":
        p.paragraph_format.left_indent = Cm(9)
    add_inline(p, text, ctx, bold=kind.endswith("b"))


def sources_list(doc, groups, data, ctx):
    for title, keys in groups:
        p = doc.add_paragraph()
        fmt(p, WD_ALIGN_PARAGRAPH.CENTER, indent=0, before=12, after=6, keep=True)
        add_inline(p, title, ctx, bold=True)
        for key in keys:
            p = doc.add_paragraph()
            fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, indent=1.25)
            r = p.add_run(f"{data[key]['n']}. ")
            set_run_font(r)
            for tok in re.split(r"(\*[^*]+\*)", data[key]["text"]):
                if tok:
                    it = tok.startswith("*") and tok.endswith("*")
                    r = p.add_run(tok[1:-1] if it else tok)
                    set_run_font(r, italic=it)


def toc(doc):
    p = doc.add_paragraph()
    fmt(p, indent=0)
    add_field(p, 'TOC \\o "1-2" \\h \\z \\u')


# ---------------------------------------------------------------- main loop
def render_part(doc, name, text, ctx, groups, data):
    lines = text.splitlines()
    i, para = 0, []

    def flush():
        nonlocal para
        if para:
            p = doc.add_paragraph()
            fmt(p)
            add_inline(p, " ".join(s.strip() for s in para), ctx)
            para = []

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("<!--"):
            while "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        if not s:
            flush()
        elif s.startswith("::"):
            flush()
            title_line(doc, s, ctx)
        elif s == "[[TOC]]":
            flush()
            toc(doc)
        elif s == "[[PAGEBREAK]]":
            flush()
            page_break(doc)
        elif s == "[[SOURCES]]":
            flush()
            sources_list(doc, groups, data, ctx)
        elif s == "[[NUMBERED]]":
            flush()
            numbered_section(doc)
            i += 1
            continue
        elif re.match(r"#{1,3}\s", s):
            flush()
            level = len(s.split()[0])
            heading(doc, s[level:].strip(), level, ctx)
        elif s.startswith("!["):
            flush()
            figure(doc, s, ctx)
        elif s.startswith("$$"):
            flush()
            equation(doc, s, ctx)
        elif s.startswith("Таблица:"):
            flush()
            rows = []
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            table(doc, s, rows, ctx)
            continue
        elif s.startswith("```"):
            flush()
            code, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i].rstrip())
                i += 1
            code_block(doc, code)
        elif re.match(r"[-–]\s", s):
            flush()
            p = doc.add_paragraph()
            fmt(p)
            add_inline(p, "– " + s[2:].strip(), ctx)
            # continuation lines of the same item
            while i + 1 < len(lines) and lines[i + 1].startswith("  ") and lines[i + 1].strip():
                i += 1
                add_inline(p, " " + lines[i].strip(), ctx)
        else:
            para.append(s)
        if s and s not in ("[[PAGEBREAK]]", "[[NUMBERED]]"):
            STATE["fresh"] = False
        i += 1
    flush()


def main():
    groups, order, data = load_sources()
    texts = [(n, (HERE / n).read_text(encoding="utf-8")) for n in PARTS if (HERE / n).exists()]
    labels = scan_labels(texts)
    doc = Document()
    setup(doc)
    for n, text in texts:
        ctx = Ctx(labels, data, n)
        render_part(doc, n, text, ctx, groups, data)
    doc.save(OUT)
    uncited = [k for k in order if not data[k]["where"]]
    write_check(order, data)
    for e in errors:
        print("ERROR:", e)
    print(f"sources: {len(order)}, uncited: {len(uncited)} {uncited[:10]}")
    print(f"figures: {sum(1 for k in labels if k.startswith('fig:'))}, "
          f"tables: {sum(1 for k in labels if k.startswith('tab:'))}")
    print("saved", OUT)
    return 1 if errors else 0


def write_check(order, data):
    out = ["# Проверка источников", "",
           "Файл создаёт `build.py` при каждой сборке: номер в списке → источник → где проверен → где цитируется.", "",
           "| № | Источник | Проверка | Где цитируется |", "|---|---|---|---|"]
    for k in order:
        d = data[k]
        where = "; ".join(d["where"]) or "**не цитируется**"
        out.append(f"| {d['n']} | {d['text'].replace('|', '/')} | {d['url']} | {where} |")
    (HERE / "sources_check.md").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
