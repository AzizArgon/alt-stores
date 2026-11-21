"""Build the ALT STORES defense deck: docs/presentation/ALT_STORES_defense.pptx.

Texts and speaker notes live in slides.yaml (edit them there); this file only places them.
Run from the repository root:  py -3.12 docs/presentation/build_pptx.py
Needs: pip install python-pptx pyyaml qrcode pillow. Fonts: docs/presentation/fonts (Inter).
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import qrcode
import yaml
from lxml import etree
from PIL import Image, ImageFont
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SHOTS = ROOT / "docs" / "screenshots" / "final"
DIAGRAMS = ROOT / "docs" / "diagrams"
OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "ALT_STORES_defense.pptx"
CACHE = Path(tempfile.mkdtemp(prefix="alt_deck_"))

# Brand tokens: frontend/src/index.css (@theme) and components/Logo.jsx
FONT = "Inter"
PRIMARY = "2546E8"
PRIMARY_DARK = "1B36BD"
PRIMARY_SOFT = "EAEEFE"
ACCENT = "FF8A1F"
ACCENT_SOFT = "FFF1E3"
INK = "14171F"
MUTED = "5B6472"
FAINT = "8A93A3"
BG = "F5F6F8"
SURFACE2 = "F0F2F5"
LINE = "E3E6EB"
LINE_STRONG = "C9CED7"
SUCCESS = "0F7A55"
SUCCESS_SOFT = "E5F6EF"
WARNING = "8F5400"
WARNING_SOFT = "FFF5E0"
DANGER = "C02B2B"
DANGER_SOFT = "FDECEC"
INFO = "0B6A94"
INFO_SOFT = "E6F4FA"
WHITE = "FFFFFF"

W, H = 13.333, 7.5
MX = 0.6                 # side margin
CW = W - 2 * MX          # content width
TOP = 1.75               # content top
BOTTOM = 6.72            # content bottom (footer below)


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ------------------------------------------------------------------ primitives
def _no_style(shape):
    st = shape._element.find(qn("p:style"))
    if st is not None:
        shape._element.remove(st)


def box(slide, x, y, w, h, fill=SURFACE2, line=None, radius=0.14, lw=1.0, name=None):
    """Rounded card (radius in inches; 0 = plain rectangle)."""
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    _no_style(s)
    if radius:
        s.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
    else:
        s.line.fill.background()
    if name:
        s.name = name
    return s


def circle(slide, x, y, d, fill, text=None, color=WHITE, size=18):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    _no_style(s)
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.fill.background()
    if text is not None:
        tf = s.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = text
        _font(r, size, color, True)
    return s


def _font(run, size, color, bold=False, italic=False):
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = rgb(color)


def text(slide, x, y, w, h, paras, size=16, color=INK, bold=False, align="l",
         anchor="t", spacing=1.12, after=0, margin=0.0, name=None):
    """Text box. paras: str | list of (str | dict(t=..., size, color, bold, after, runs=[...]))."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    m = Inches(margin)
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = m
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    fill_text(tf, paras, size, color, bold, align, spacing, after)
    return tb


def fit_size(t: str, w: float, size: float, low: float = 16, bold=True) -> float:
    """Largest font size (down to low) at which one line of t fits into w inches."""
    while size > low and est_width(t, size, bold) > w:
        size -= 1
    return size


def nbsp(t: str) -> str:
    """Keep '94 %', '2 359', '15 с', '1 спорный' on one line."""
    t = re.sub(r"(\d) (?=\d{3}\b)", "\\1\u00a0", t)
    t = re.sub(r"(\d) (?=(%|с\b|мин\b|ТБ|ГБ|МГц|px|сум|из\b|спорный))", "\\1\u00a0", t)
    return t


def fill_text(tf, paras, size=16, color=INK, bold=False, align="l", spacing=1.12, after=0):
    if isinstance(paras, (str, dict)):
        paras = [paras]
    al = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}
    for i, item in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        d = item if isinstance(item, dict) else {"t": item}
        p.alignment = al[d.get("align", align)]
        p.line_spacing = d.get("spacing", spacing)
        p.space_after = Pt(d.get("after", after))
        runs = d.get("runs") or [{"t": d["t"]}]
        for rd in runs:
            r = p.add_run()
            r.text = nbsp(rd["t"])
            _font(r, rd.get("size", d.get("size", size)), rd.get("color", d.get("color", color)),
                  rd.get("bold", d.get("bold", bold)), rd.get("italic", False))


def shape_text(shape, paras, size=16, color=INK, bold=False, align="l", anchor="m", pad=0.12):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(pad)
    tf.margin_top = tf.margin_bottom = Inches(0.05)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    fill_text(tf, paras, size, color, bold, align)


def arrow(slide, x1, y1, x2, y2, color=LINE_STRONG, width=2.0, head=True):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    _no_style(c)
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    if head:
        ln = c.line._get_or_add_ln()
        tail = etree.SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
    return c


def chip(slide, x, y, label, fill=PRIMARY_SOFT, color=PRIMARY, size=16, h=0.46, pad=0.2, bold=True):
    w = est_width(label, size, bold) + 2 * pad
    s = box(slide, x, y, w, h, fill=fill, radius=h / 2)
    shape_text(s, {"t": label}, size=size, color=color, bold=bold, align="c", pad=0.05)
    return w


_FONTS = {}


def est_width(s: str, size: float, bold=False) -> float:
    """Width of Inter text in inches, measured with the font file (for chips)."""
    key = (bold, size)
    if key not in _FONTS:
        name = "Inter-Bold.ttf" if bold else "Inter-Regular.ttf"
        _FONTS[key] = ImageFont.truetype(str(HERE / "fonts" / name), size * 10)
    return _FONTS[key].getlength(s) / 10 / 72 * 1.04


def picture(slide, src: Path, x, y, w=None, h=None, crop=None, radius=0.12, border=LINE, descr="",
            px_per_in=200):
    """Crop with Pillow, cache as JPEG/PNG, insert with rounded corners and a thin border."""
    im = Image.open(src)
    if crop:
        im = im.crop(crop)
    ratio = im.width / im.height
    if w is None:
        w = h * ratio
    if h is None:
        h = w / ratio
    target = int(w * px_per_in)
    if im.width > target:
        im = im.resize((target, int(target / ratio)), Image.LANCZOS)
    key = f"{src.stem}_{abs(hash((crop, target)))}"
    if src.suffix.lower() == ".png":
        path = CACHE / f"{key}.png"
        im.save(path, optimize=True)
    else:
        path = CACHE / f"{key}.jpg"
        im.convert("RGB").save(path, quality=90)
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        geom = pic._element.spPr.find(qn("a:prstGeom"))
        geom.set("prst", "roundRect")
        av = geom.find(qn("a:avLst"))
        if av is None:
            av = etree.SubElement(geom, qn("a:avLst"))
        gd = etree.SubElement(av, qn("a:gd"))
        gd.set("name", "adj")
        gd.set("fmla", f"val {int(min(50000, radius / min(w, h) * 100000))}")
    if border:
        pic.line.color.rgb = rgb(border)
        pic.line.width = Pt(1)
    if descr:
        pic._element.nvPicPr.cNvPr.set("descr", descr)
    return pic, w, h


def logo(slide, x, y, size, on_dark=False):
    """The 'A' mark from components/Logo.jsx (viewBox 32), as native shapes."""
    k = size / 32
    sq = box(slide, x, y, size, size, fill=WHITE if on_dark else PRIMARY, radius=8 * k)
    sq.name = "Logo"
    fg = PRIMARY if on_dark else WHITE
    bgc = WHITE if on_dark else PRIMARY
    outer = [(9, 22.75), (14.7, 9.25), (17.3, 9.25), (23, 22.75), (20, 22.75), (19, 20.15), (13, 20.15), (12, 22.75)]
    hole = [(14, 17.75), (18, 17.75), (16, 12.55)]
    for pts, col in ((outer, fg), (hole, bgc)):
        scale = Inches(k) / 1.0
        fb = slide.shapes.build_freeform(pts[0][0], pts[0][1], scale=scale)
        fb.add_line_segments(pts[1:], close=True)
        s = fb.convert_to_shape(Inches(x), Inches(y))
        _no_style(s)
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(col)
        s.line.fill.background()
    d = 5 * k
    circle(slide, x + 23 * k, y + 4 * k, d, ACCENT)


# ------------------------------------------------------------------ slide frame
class Deck:
    def __init__(self, data):
        self.d = data
        self.prs = Presentation()
        self.prs.slide_width = Inches(W)
        self.prs.slide_height = Inches(H)
        self._theme_fonts()
        self.blank = self.prs.slide_layouts[6]
        self.n = 0
        self.elapsed = 0

    def _theme_fonts(self):
        """Set theme fonts and colours to the brand so any default text is Inter."""
        master = self.prs.slide_master
        for rel in master.part.rels.values():
            if rel.reltype.endswith("/theme"):
                part = rel.target_part
                root = etree.fromstring(part.blob)
                ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                for tag in ("a:majorFont", "a:minorFont"):
                    for el in root.iterfind(f".//{tag}/a:latin", ns):
                        el.set("typeface", FONT)
                cs = root.find(".//a:clrScheme", ns)
                cs.set("name", "ALT STORES")
                colors = {"dk1": INK, "lt1": WHITE, "dk2": MUTED, "lt2": BG, "accent1": PRIMARY,
                          "accent2": ACCENT, "accent3": SUCCESS, "accent4": INFO, "accent5": WARNING,
                          "accent6": DANGER, "hlink": PRIMARY, "folHlink": PRIMARY_DARK}
                for key, val in colors.items():
                    el = cs.find(f"a:{key}", ns)
                    for ch in list(el):
                        el.remove(ch)
                    srgb = etree.SubElement(el, "{%s}srgbClr" % ns["a"])
                    srgb.set("val", val)
                part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    def new(self, sd, dark=False):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(PRIMARY if dark else WHITE)
        if not dark:
            self.footer(s)
        if sd.get("kicker"):
            num = "" if sd.get("backup") else f"{self.n:02d} · "
            text(s, MX, 0.42, CW, 0.36, {"t": f"{num}{sd['kicker']}".upper()}, size=16, color=PRIMARY, bold=True)
        if sd.get("title") and not dark:
            text(s, MX, 0.78, CW, 0.7, sd["title"], size=30, color=INK, bold=True, name="Title")
        self.notes(s, sd)
        return s

    def footer(self, s):
        logo(s, MX, 7.0, 0.26)
        text(s, MX + 0.38, 6.98, 5, 0.3, self.d["footer"], size=14, color=MUTED, anchor="m")
        text(s, W - MX - 1.0, 6.98, 1.0, 0.3, str(self.n), size=14, color=MUTED, align="r", anchor="m")

    def notes(self, s, sd):
        body = sd.get("notes", "").strip()
        if "time" in sd:
            self.elapsed += sd["time"]
            t, e = sd["time"], self.elapsed
            body = f"[{t // 60}:{t % 60:02d} · с начала {e // 60}:{e % 60:02d}]\n{body}"
        elif sd.get("backup"):
            body = f"[Запасной слайд {sd['backup']} — только если спросят]\n{body}"
        s.notes_slide.notes_text_frame.text = body


# ------------------------------------------------------------------ charts
def style_chart(chart, size=16, legend=True):
    chart.font.name = FONT
    chart.font.size = Pt(size)
    chart.font.color.rgb = rgb(MUTED)
    chart.has_title = False
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
        chart.legend.font.name = FONT
        chart.legend.font.color.rgb = rgb(INK)


def bar_chart(slide, x, y, w, h, cats, series, colors, horizontal=False, maxv=None, fmt='0.0',
              legend=True, size=16, label_size=16, gap=55):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    style_chart(ch, size, legend)
    plot = ch.plots[0]
    plot.gap_width = gap
    plot.overlap = -8 if len(series) > 1 else 0
    for s, col in zip(plot.series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(col)
        s.invert_if_negative = False
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = fmt
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(label_size)
    dl.font.name = FONT
    dl.font.bold = True
    dl.font.color.rgb = rgb(INK)
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb(LINE)
    va.major_gridlines.format.line.width = Pt(0.75)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(label_size)
    va.tick_labels.font.color.rgb = rgb(FAINT)
    if maxv is not None:
        va.maximum_scale = maxv
        va.minimum_scale = 0
    va.visible = not horizontal
    ca = ch.category_axis
    ca.format.line.color.rgb = rgb(LINE_STRONG)
    ca.tick_labels.font.size = Pt(size)
    ca.tick_labels.font.color.rgb = rgb(INK)
    ca.has_major_gridlines = False
    if horizontal:
        ca.reverse_order = True
        va.has_major_gridlines = False
    return ch


def donut(slide, x, y, w, h, cats, vals, colors, hole=62, size=16):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("s", vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    style_chart(ch, size, legend=False)
    plot = ch.plots[0]
    for i, col in enumerate(colors):
        pt = plot.series[0].points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(col)
        pt.format.line.color.rgb = rgb(WHITE)
        pt.format.line.width = Pt(2)
    hs = ch._chartSpace.find(".//" + qn("c:holeSize"))
    if hs is not None:
        hs.set("val", str(hole))
    return ch


# ------------------------------------------------------------------ table
def table(slide, x, y, w, rows, col_w, row_h=0.5, size=16, head_fill=SURFACE2, first_bold=True,
          aligns=None, mark=None):
    nr, nc = len(rows), len(rows[0])
    gf = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr))
    tbl = gf.table
    tblPr = tbl._tbl.tblPr
    tblPr.set("firstRow", "0")
    tblPr.set("bandRow", "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is None:
        sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # No Style, No Grid
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(cw)
    for r in range(nr):
        tbl.rows[r].height = Inches(row_h)
        for c in range(nc):
            cell = tbl.cell(r, c)
            val = rows[r][c]
            cell.margin_left = cell.margin_right = Inches(0.12)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            fill = head_fill if r == 0 else (mark(r, c) if mark else None)
            if fill:
                cell.fill.solid()
                cell.fill.fore_color.rgb = rgb(fill)
            else:
                cell.fill.background()
            tf = cell.text_frame
            tf.word_wrap = True
            al = (aligns or ["l"] * nc)[c]
            p = tf.paragraphs[0]
            p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[al]
            color, bold, t = INK, (r == 0 or (c == 0 and first_bold)), str(val)
            if val == "yes":
                t, color, bold = "✓", SUCCESS, True
            elif val == "no":
                t, color, bold = "✗", FAINT, False
            elif r == 0:
                color = MUTED
            run = p.add_run()
            run.text = t
            _font(run, size + (4 if val in ("yes", "no") else 0), color, bold)
            # bottom border
            tcPr = cell._tc.get_or_add_tcPr()
            lnB = etree.SubElement(tcPr, qn("a:lnB"))
            lnB.set("w", str(Emu(Pt(1))))
            sf = etree.SubElement(lnB, qn("a:solidFill"))
            clr = etree.SubElement(sf, qn("a:srgbClr"))
            clr.set("val", LINE)
    return tbl


# ------------------------------------------------------------------ slides
def s_title(deck, sd):
    d = deck.d
    s = deck.new(sd, dark=True)
    logo(s, MX + 0.1, 0.6, 0.7, on_dark=True)
    text(s, MX + 1.0, 0.6, 5, 0.7, {"runs": [{"t": "ALT "}, {"t": "STORES", "color": "C9D3FF"}]},
         size=30, color=WHITE, bold=True, anchor="m")
    text(s, MX + 0.1, 1.75, 6.9, 0.4, sd["label"].upper(), size=16, color="C9D3FF", bold=True)
    text(s, MX + 0.1, 2.15, 7.1, 1.9, d["topic"], size=30, color=WHITE, bold=True, spacing=1.02)
    text(s, MX + 0.1, 4.3, 7.1, 0.8, sd["tagline"], size=18, color="DCE3FF")
    a = d["author"]
    rows = [("Автор", a["name"]), ("Научный руководитель", a["supervisor"]),
            ("Вуз, кафедра", f"{a['university']}, {a['department']}")]
    yy = 5.35
    for k, v in rows:
        text(s, MX + 0.1, yy, 2.7, 0.36, k, size=16, color="C9D3FF")
        text(s, MX + 2.85, yy, 4.4, 0.36, v, size=16, color=WHITE, bold=True)
        yy += 0.42
    text(s, MX + 0.1, 6.65, 4, 0.4, a["year"], size=16, color="C9D3FF")
    # screenshot of the storefront in a white frame
    box(s, 7.95, 1.05, 4.85, 4.0, fill=WHITE, radius=0.2)
    picture(s, SHOTS / "01_home.jpg", 8.1, 1.2, w=4.55, crop=(300, 0, 1620, 1080),
            radius=0.12, border=None, descr="Главная страница ALT STORES")
    text(s, 7.95, 6.2, 4.85, 0.4, d["site"], size=18, color=WHITE, bold=True, align="c")


def s_problem(deck, sd):
    s = deck.new(sd)
    lw = 6.9
    box(s, MX, TOP, lw, 4.97, fill=BG)
    text(s, MX + 0.3, TOP + 0.18, lw - 0.6, 0.4, sd["rows_title"], size=18, bold=True)
    y = TOP + 0.66
    for src, line in sd["rows"]:
        text(s, MX + 0.3, y, lw - 0.6, 0.3, src, size=16, color=MUTED)
        card = box(s, MX + 0.3, y + 0.3, lw - 0.6, 0.42, fill=WHITE, line=LINE, radius=0.1)
        shape_text(card, {"t": line}, size=16, color=INK, bold=True, pad=0.15)
        y += 0.77
    text(s, MX + 0.3, TOP + 4.5, lw - 0.6, 0.35, sd["rows_note"], size=16, color=FAINT)
    x = MX + lw + 0.4
    w = W - MX - x
    y = TOP
    for i, (head, desc) in enumerate(sd["pains"]):
        hot = i == 3
        circle(s, x, y + 0.08, 0.56, DANGER_SOFT if hot else PRIMARY_SOFT, str(i + 1),
               color=DANGER if hot else PRIMARY, size=20)
        text(s, x + 0.75, y, w - 0.75, 0.38, head, size=fit_size(head, w - 0.8, 20), bold=True)
        text(s, x + 0.75, y + 0.42, w - 0.75, 0.7, desc, size=16, color=MUTED)
        y += 1.26


def s_relevance(deck, sd):
    s = deck.new(sd)
    n = len(sd["cards"])
    gap = 0.35
    cw = (CW - gap * (n - 1)) / n
    for i, c in enumerate(sd["cards"]):
        x = MX + i * (cw + gap)
        first = i == 0
        box(s, x, TOP, cw, 4.85, fill=PRIMARY if first else BG)
        col = WHITE if first else INK
        text(s, x + 0.35, TOP + 0.35, cw - 0.7, 1.2, c["big"], size=54, bold=True,
             color=WHITE if first else (ACCENT if i == 2 else PRIMARY))
        text(s, x + 0.35, TOP + 1.85, cw - 0.7, 0.9, c["head"], size=22, bold=True, color=col)
        text(s, x + 0.35, TOP + 2.75, cw - 0.7, 1.9, c["text"], size=17,
             color="DCE3FF" if first else MUTED, spacing=1.18)


def s_goal(deck, sd):
    s = deck.new(sd)
    lw = 6.1
    box(s, MX, TOP, lw, 2.25, fill=PRIMARY)
    text(s, MX + 0.3, TOP + 0.18, lw - 0.6, 0.35, "ЦЕЛЬ", size=16, color="C9D3FF", bold=True)
    text(s, MX + 0.3, TOP + 0.52, lw - 0.6, 1.7, sd["goal"], size=17, color=WHITE, bold=True, spacing=1.08)
    yy = TOP + 2.45
    for head, key, hh in (("ОБЪЕКТ", "object", 1.05), ("ПРЕДМЕТ", "subject", 1.27)):
        box(s, MX, yy, lw, hh, fill=BG)
        text(s, MX + 0.3, yy + 0.14, 1.4, 0.35, head, size=16, color=PRIMARY, bold=True)
        text(s, MX + 1.6, yy + 0.12, lw - 1.85, hh - 0.2, sd[key], size=16, color=INK, spacing=1.05)
        yy += hh + 0.2
    x = MX + lw + 0.45
    w = W - MX - x
    text(s, x, TOP - 0.05, w, 0.4, "ЗАДАЧИ", size=16, color=PRIMARY, bold=True)
    y = TOP + 0.45
    for i, t in enumerate(sd["tasks"]):
        circle(s, x, y + 0.02, 0.44, PRIMARY_SOFT, str(i + 1), color=PRIMARY, size=16)
        text(s, x + 0.62, y, w - 0.62, 0.5, t, size=17, anchor="m")
        y += 0.635


def s_solution(deck, sd):
    s = deck.new(sd)
    _, pw, ph = picture(s, SHOTS / "03_product_offers.jpg", MX, TOP, w=7.3, crop=(320, 128, 1590, 960),
                        descr=sd["caption"])
    x = MX + 7.3 + 0.4
    w = W - MX - x
    y = TOP
    colors = [(PRIMARY_SOFT, PRIMARY), (ACCENT_SOFT, "B85A00"), (SUCCESS_SOFT, SUCCESS)]
    hh = (ph - 0.4) / 3
    for (letter, head, desc), (bgc, fg) in zip(sd["roles"], colors):
        box(s, x, y, w, hh, fill=BG)
        circle(s, x + 0.22, y + 0.22, 0.56, bgc, letter, color=fg, size=20)
        text(s, x + 0.95, y + 0.22, w - 1.1, 0.56, head, size=20, bold=True, anchor="m")
        text(s, x + 0.95, y + 0.82, w - 1.1, hh - 0.9, desc, size=16, color=MUTED, spacing=1.05)
        y += hh + 0.2


def node(s, x, y, w, h, head, sub=None, fill=WHITE, line=LINE_STRONG, hc=INK, sc=MUTED, hs=18, ss=16):
    b = box(s, x, y, w, h, fill=fill, line=line, radius=0.12)
    paras = [{"t": head, "size": hs, "bold": True, "color": hc, "align": "c", "after": 2}]
    if sub:
        paras.append({"t": sub, "size": ss, "color": sc, "align": "c"})
    shape_text(b, paras, pad=0.1)
    return b


def s_architecture(deck, sd):
    s = deck.new(sd)
    # left: user and network
    node(s, MX, 3.25, 1.85, 1.5, "Браузер", "ПК и телефон\nRU · UZ · EN")
    node(s, 2.8, 3.25, 1.95, 1.5, "Cloudflare + nginx", "HTTPS")
    arrow(s, MX + 1.85, 4.0, 2.8, 4.0)
    # VPS group
    gx, gy, gw, gh = 5.2, TOP, 4.35, 4.95
    box(s, gx, gy, gw, gh, fill=PRIMARY_SOFT, radius=0.18)
    text(s, gx + 0.25, gy + 0.12, gw - 0.5, 0.35, "VPS · Docker Compose", size=16, color=PRIMARY, bold=True)
    node(s, gx + 0.25, gy + 0.6, gw - 0.5, 0.95, "web", "React + Vite, статика", line=None)
    node(s, gx + 0.25, gy + 1.8, gw - 0.5, 1.45, "backend: FastAPI",
         "разбор прайсов, Anti-Fraud, мониторинг, учёт, чат, брони", fill=PRIMARY, line=None, hc=WHITE, sc="DCE3FF")
    node(s, gx + 0.25, gy + 3.55, 1.95, 1.1, "SQLite", "35 таблиц", line=None)
    node(s, gx + 2.35, gy + 3.55, 1.95, 1.1, "Фото", "data/media", line=None)
    arrow(s, 4.75, 3.75, gx + 0.25, gy + 1.08)
    arrow(s, 4.75, 4.25, gx + 0.25, gy + 2.52)
    arrow(s, gx + 1.22, gy + 3.25, gx + 1.22, gy + 3.55)
    arrow(s, gx + 3.32, gy + 3.25, gx + 3.32, gy + 3.55)
    # external services
    ex = 9.95
    ew = W - MX - ex
    ext = [("ИИ: Gemini, Groq", "только непонятные строки", ACCENT_SOFT),
           ("Курс ЦБ", "cbu.uz, раз в день", BG), ("Telegram-каналы", "новые посты магазинов", BG)]
    for i, (hd, sb, f) in enumerate(ext):
        yy = TOP + i * 1.72
        node(s, ex, yy, ew, 1.5, hd, sb, fill=f, line=None)
        arrow(s, gx + gw - 0.25, gy + 2.52, ex, yy + 0.75)


def s_pipeline(deck, sd):
    s = deck.new(sd)
    st = sd["stages"]
    gap = 0.45
    cw = (CW - 3 * gap) / 4
    ch = 1.62
    rows_y = [TOP - 0.05, TOP + 1.92]
    pos = []
    for i in range(8):
        r = i // 4
        c = i % 4 if r == 0 else 3 - (i % 4)
        pos.append((MX + c * (cw + gap), rows_y[r]))
    for i, ((head, desc), (x, y)) in enumerate(zip(st, pos)):
        if head == "Код":
            f, hc, dc, line = PRIMARY, WHITE, "DCE3FF", None
        elif head == "ИИ":
            f, hc, dc, line = ACCENT_SOFT, INK, MUTED, None
        else:
            f, hc, dc, line = BG, INK, MUTED, None
        box(s, x, y, cw, ch, fill=f, line=line)
        circle(s, x + 0.2, y + 0.2, 0.4, WHITE if f != BG else PRIMARY_SOFT, str(i + 1),
               color=PRIMARY, size=16)
        text(s, x + 0.7, y + 0.17, cw - 0.8, 0.46, head, size=fit_size(head, cw - 0.85, 20), bold=True,
             color=hc, anchor="m")
        text(s, x + 0.2, y + 0.72, cw - 0.4, ch - 0.78, desc, size=16, color=dc, spacing=1.02)
    for i in range(7):
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if y1 == y2:
            if x2 > x1:
                arrow(s, x1 + cw + 0.05, y1 + ch / 2, x2 - 0.05, y2 + ch / 2)
            else:
                arrow(s, x1 - 0.05, y1 + ch / 2, x2 + cw + 0.05, y2 + ch / 2)
        else:
            arrow(s, x1 + cw / 2, y1 + ch + 0.05, x2 + cw / 2, y2 - 0.05)
    # measurement band
    my = TOP + 3.78
    box(s, MX, my, CW, 1.2, fill=WHITE, line=LINE)
    text(s, MX + 0.3, my + 0.1, 2.5, 1.0, sd["measure_title"], size=16, color=MUTED, anchor="m")
    n = len(sd["measure"])
    tw = (CW - 3.0) / n
    for i, (num, lab) in enumerate(sd["measure"]):
        x = MX + 2.95 + i * tw
        last = i == n - 1
        text(s, x, my + 0.1, tw - 0.1, 0.6, num, size=30, bold=True, color=SUCCESS if last else PRIMARY)
        text(s, x, my + 0.7, tw - 0.05, 0.45, lab, size=16, color=MUTED)


def s_standard(deck, sd):
    s = deck.new(sd)
    lw = 4.75
    y = TOP + 0.1
    for line in sd["raw"]:
        b = box(s, MX, y, lw, 0.62, fill=BG, radius=0.1)
        shape_text(b, {"t": line}, size=17, color=INK, bold=True, pad=0.2)
        y += 0.8
    arrow(s, MX + lw + 0.15, TOP + 1.6, MX + lw + 0.95, TOP + 1.6, color=PRIMARY, width=3.5)
    cx = MX + lw + 1.15
    cw = W - MX - cx
    box(s, cx, TOP, cw, 3.45, fill=WHITE, line=LINE_STRONG, radius=0.18)
    c = sd["card"]
    text(s, cx + 0.35, TOP + 0.25, cw - 0.7, 0.35, c["cat"], size=16, color=MUTED)
    text(s, cx + 0.35, TOP + 0.6, cw - 0.7, 0.55, c["name"], size=28, bold=True)
    yy = TOP + 1.3
    for k, v in c["specs"]:
        text(s, cx + 0.35, yy, 2.6, 0.36, k, size=16, color=MUTED)
        text(s, cx + 3.0, yy, cw - 3.3, 0.36, v, size=16, bold=True)
        yy += 0.4
    chip(s, cx + 0.35, TOP + 2.92, c["foot"], fill=SUCCESS_SOFT, color=SUCCESS, size=16, h=0.4)
    # principles
    ry = TOP + 3.7
    n = len(sd["rules"])
    gap = 0.3
    rw = (CW - gap * (n - 1)) / n
    for i, (head, desc) in enumerate(sd["rules"]):
        x = MX + i * (rw + gap)
        box(s, x, ry, rw, 1.27, fill=PRIMARY_SOFT)
        text(s, x + 0.25, ry + 0.13, rw - 0.5, 0.4, head, size=18, bold=True, color=PRIMARY)
        text(s, x + 0.25, ry + 0.52, rw - 0.5, 0.72, desc, size=16, color=INK, spacing=1.02)


def bullets(s, x, y, w, items, size=16, color=INK, dot=PRIMARY, h=3.0, after=10):
    """Bulleted list in one text box: the renderer wraps lines, nothing overlaps."""
    tb = text(s, x, y, w, h, [{"t": it, "after": after} for it in items], size=size, color=color, spacing=1.05)
    for p in tb.text_frame.paragraphs:
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(Inches(0.3)))
        pPr.set("indent", str(-Inches(0.3)))
        bc = etree.SubElement(pPr, qn("a:buClr"))
        etree.SubElement(bc, qn("a:srgbClr")).set("val", dot)
        etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
        etree.SubElement(pPr, qn("a:buChar")).set("char", "\u25cf")
        # schema order inside a:pPr: lnSpc, spcBef, spcAft, then bullets
        for tag in ("a:spcAft", "a:spcBef", "a:lnSpc"):
            el = pPr.find(qn(tag))
            if el is not None:
                pPr.remove(el)
                pPr.insert(0, el)
    return tb


def s_ai(deck, sd):
    s = deck.new(sd)
    cw = 3.7
    for i, (hk, ik, f, dot) in enumerate((("code_head", "code", PRIMARY_SOFT, PRIMARY),
                                           ("ai_head", "ai", ACCENT_SOFT, ACCENT))):
        x = MX + i * (cw + 0.3)
        box(s, x, TOP, cw, 2.85, fill=f)
        text(s, x + 0.3, TOP + 0.2, cw - 0.6, 0.4, sd[hk], size=20, bold=True,
             color=PRIMARY if i == 0 else "B85A00")
        bullets(s, x + 0.3, TOP + 0.78, cw - 0.55, sd[ik], size=16, dot=dot, h=2.0, after=8)
    # donut: 794 rules / 384 AI
    dx = MX + 2 * cw + 0.6
    dw = W - MX - dx
    text(s, dx, TOP, dw, 0.4, sd["donut_title"], size=16, color=MUTED, bold=True)
    donut(s, dx - 0.1, TOP + 0.4, 2.4, 2.4, ["Правила", "ИИ"], [794, 384], [PRIMARY, ACCENT])
    text(s, dx + 0.6, TOP + 1.3, 1.1, 0.6, "1 178", size=20, bold=True, align="c", anchor="m")
    lx = dx + 2.45
    for j, (num, lab, col) in enumerate((("67 %", "правилами\nбез ИИ", PRIMARY), ("33 %", "ушло к ИИ", ACCENT))):
        yy = TOP + 0.55 + j * 1.15
        text(s, lx, yy, dw - 2.45, 0.5, num, size=28, bold=True, color=col if j == 0 else "B85A00")
        text(s, lx, yy + 0.5, dw - 2.45, 0.6, lab, size=16, color=MUTED, spacing=1.0)
    # learning band
    by = TOP + 3.15
    box(s, MX, by, CW, 1.8, fill=BG)
    text(s, MX + 0.35, by + 0.2, 4.0, 1.4, sd["learn_head"], size=20, bold=True, anchor="m")
    x0 = MX + 4.6
    text(s, x0, by + 0.25, 2.3, 0.7, sd["learn_from"], size=36, bold=True, color=MUTED)
    text(s, x0, by + 0.95, 3.0, 0.8, sd["learn_from_text"], size=16, color=MUTED, spacing=1.0)
    arrow(s, x0 + 2.75, by + 0.6, x0 + 3.45, by + 0.6, color=SUCCESS, width=3.5)
    x1 = x0 + 3.65
    text(s, x1, by + 0.25, 2.0, 0.7, sd["learn_to"], size=36, bold=True, color=SUCCESS)
    text(s, x1, by + 0.95, W - MX - x1 - 0.3, 0.8, sd["learn_to_text"], size=16, color=INK, spacing=1.0)


def s_fraud(deck, sd):
    s = deck.new(sd)
    _, pw, ph = picture(s, SHOTS / "07_import_preview.jpg", MX, TOP, w=7.4, crop=(240, 1150, 1480, 1652),
                        descr=sd["caption"])
    y = TOP + ph + 0.3
    lx = MX
    for i, (lab, f, c) in enumerate((("info", INFO_SOFT, INFO), ("warning", WARNING_SOFT, WARNING),
                                      ("danger", DANGER_SOFT, DANGER))):
        lx += chip(s, lx, y, lab, fill=f, color=c, size=16, h=0.42) + 0.15
    text(s, lx + 0.1, y, 7.4 - (lx - MX) - 0.1, 0.42, "три уровня флага", size=16, color=MUTED, anchor="m")
    y += 0.62
    for p in sd["principles"]:
        circle(s, MX, y + 0.1, 0.12, PRIMARY)
        text(s, MX + 0.28, y, 7.1, 0.35, p, size=16)
        y += 0.42
    x = MX + 7.4 + 0.4
    w = W - MX - x
    box(s, x, TOP, w, 1.85, fill=SUCCESS_SOFT)
    text(s, x + 0.3, TOP + 0.15, w - 0.6, 0.75, sd["big"], size=40, bold=True, color=SUCCESS)
    text(s, x + 0.3, TOP + 0.92, w - 0.6, 0.85, sd["big_text"], size=16, color=INK, spacing=1.05)
    box(s, x, TOP + 2.05, w, 2.9, fill=BG)
    text(s, x + 0.3, TOP + 2.2, w - 0.6, 0.4, "Что проверяется", size=18, bold=True)
    bullets(s, x + 0.3, TOP + 2.7, w - 0.55, sd["checks"], size=16, dot=DANGER, h=2.2, after=8)


def s_monitoring(deck, sd):
    s = deck.new(sd)
    _, pw, ph = picture(s, SHOTS / "14_market.jpg", MX, TOP, h=4.65, crop=(290, 250, 1790, 1400),
                        descr=sd["caption"])
    x = MX + pw + 0.4
    w = W - MX - x
    n = len(sd["facts"])
    gap = 0.18
    fh = (4.95 - gap * (n - 1)) / n
    for i, (head, desc) in enumerate(sd["facts"]):
        yy = TOP + i * (fh + gap)
        box(s, x, yy, w, fh, fill=PRIMARY_SOFT if i == 0 else BG)
        text(s, x + 0.3, yy + 0.13, w - 0.6, 0.38, head, size=18, bold=True, color=PRIMARY if i == 0 else INK)
        text(s, x + 0.3, yy + 0.5, w - 0.6, fh - 0.55, desc, size=16, color=MUTED, spacing=1.02)


def s_seller(deck, sd):
    s = deck.new(sd)
    cap = sd["captions"]
    _, w1, h1 = picture(s, SHOTS / "06_seller_goods.jpg", MX, TOP, w=6.3, crop=(0, 0, 1920, 1080), descr=cap[0])
    x2 = MX + 6.3 + 0.3
    _, w2, h2 = picture(s, SHOTS / "08_stock.jpg", x2, TOP, w=3.85, crop=(240, 30, 1880, 690), descr=cap[1])
    px = x2 + 3.85 + 0.3
    pw = W - MX - px
    picture(s, SHOTS / "phone_seller_stock.jpg", px, TOP, w=pw, crop=(0, 0, 750, 1624), radius=0.14, descr=cap[2])
    fy = TOP + h2 + 0.25
    box(s, x2, fy, 3.85, h1 - h2 - 0.25, fill=PRIMARY)
    text(s, x2 + 0.3, fy, 3.25, h1 - h2 - 0.25, sd["formula"], size=22, bold=True, color=WHITE, anchor="m")
    # chips
    y = TOP + h1 + 0.3
    x = MX
    for c in sd["chips"]:
        cw = est_width(c, 16, True) + 0.4
        if x + cw > W - MX:
            x = MX
            y += 0.6
        chip(s, x, y, c, size=16, h=0.46)
        x += cw + 0.15


def s_storefront(deck, sd):
    s = deck.new(sd)
    cap = sd["captions"]
    _, w1, h1 = picture(s, SHOTS / "01_home.jpg", MX, TOP, h=3.85, crop=(300, 0, 1620, 1080), descr=cap[0])
    x = MX + w1 + 0.3
    _, w2, h2 = picture(s, SHOTS / "phone_product.jpg", x, TOP, h=3.85, crop=(0, 0, 750, 1624), radius=0.14,
                        descr=cap[1])
    x3 = x + w2 + 0.3
    w3 = W - MX - x3
    _, _, h3 = picture(s, SHOTS / "04_used.jpg", x3, TOP, w=w3, crop=(330, 40, 1600, 680), descr=cap[2])
    picture(s, SHOTS / "05_build.jpg", x3, TOP + h3 + 0.25, w=w3, h=3.85 - h3 - 0.25,
            crop=(320, 60, 1600, 60 + int(1280 / (w3 / (3.85 - h3 - 0.25)))), descr=cap[3])
    y = TOP + 3.85 + 0.35
    xx = MX
    for c in sd["chips"]:
        cw = est_width(c, 16, True) + 0.4
        if xx + cw > W - MX:
            xx = MX
            y += 0.6
        chip(s, xx, y, c, size=16, h=0.46)
        xx += cw + 0.15


def s_database(deck, sd):
    s = deck.new(sd)
    bw, bh = 2.15, 1.2
    xs = [MX + i * 2.5 for i in range(5)]
    ys = [TOP, TOP + 1.7, TOP + 3.4]
    ent = {
        "cat": (0, 0, "Категория", "код МХИК"),
        "prod": (1, 0, "Товар (эталон)", "бренд, модель, ключ"),
        "offer": (2, 0, "Предложение", "цена, валюта, наличие"),
        "store": (3, 0, "Магазин", "режим учёта"),
        "user": (4, 0, "Пользователь", "роль, хэш пароля"),
        "cache": (0, 1, "Кэш разбора", "строка → ответ"),
        "flag": (1, 1, "Флаг Anti-Fraud", "тип, уровень"),
        "hist": (2, 1, "История цен", "цена, дата"),
        "imp": (3, 1, "Загрузка", "предпросмотр, отмена"),
        "branch": (4, 1, "Филиал", "адрес, карта"),
        "resv": (2, 2, "Бронь", "срок, статус"),
        "stock": (3, 2, "Остаток", "по филиалам"),
        "move": (4, 2, "Движение", "журнал операций"),
    }
    core = {"prod", "offer"}
    centers = {}
    for k, (c, r, head, sub) in ent.items():
        x, y = xs[c], ys[r]
        centers[k] = (x, y)
    links = [("cat", "prod"), ("prod", "offer"), ("offer", "store"), ("store", "user"), ("offer", "flag"),
             ("offer", "hist"), ("store", "imp"), ("store", "branch"), ("branch", "stock"), ("resv", "stock"),
             ("stock", "move")]
    for a, b in links:
        (x1, y1), (x2, y2) = centers[a], centers[b]
        arrow(s, x1 + bw / 2, y1 + bh / 2, x2 + bw / 2, y2 + bh / 2, color=LINE_STRONG, width=1.75, head=False)
    for k, (c, r, head, sub) in ent.items():
        x, y = centers[k]
        f = PRIMARY if k in core else (BG if r == 0 else WHITE)
        b = box(s, x, y, bw, bh, fill=f, line=None if k in core or r == 0 else LINE_STRONG, radius=0.12)
        shape_text(b, [{"t": head, "bold": True, "size": 17, "color": WHITE if k in core else INK, "after": 2},
                       {"t": sub, "size": 16, "color": "DCE3FF" if k in core else MUTED}], align="c", pad=0.08)
    box(s, xs[0], ys[2], 4.65, bh, fill=PRIMARY_SOFT)
    text(s, xs[0] + 0.25, ys[2], 4.2, bh, sd["note"], size=16, color=INK, anchor="m", spacing=1.05)


def s_tech(deck, sd):
    s = deck.new(sd)
    n = len(sd["cols"])
    gap = 0.35
    cw = (CW - gap * (n - 1)) / n
    for i, col in enumerate(sd["cols"]):
        x = MX + i * (cw + gap)
        box(s, x, TOP, cw, 3.6, fill=BG)
        circle(s, x + 0.3, TOP + 0.3, 0.52, PRIMARY, str(i + 1), size=18)
        text(s, x + 1.0, TOP + 0.3, cw - 1.2, 0.52, col["head"], size=fit_size(col["head"], cw - 1.25, 22),
             bold=True, anchor="m")
        bullets(s, x + 0.35, TOP + 1.15, cw - 0.6, col["items"], size=18, h=2.6, after=14)
    box(s, MX, TOP + 3.85, CW, 1.12, fill=SUCCESS_SOFT)
    text(s, MX + 0.35, TOP + 3.85, CW - 0.7, 1.12, sd["bottom"], size=18, bold=True, color=SUCCESS, anchor="m")


def tiles(s, x, y, w, items, cols, th, gap=0.2, num_size=36, colors=None, fill=BG):
    tw = (w - gap * (cols - 1)) / cols
    for i, (num, lab) in enumerate(items):
        c, r = i % cols, i // cols
        tx, ty = x + c * (tw + gap), y + r * (th + gap)
        box(s, tx, ty, tw, th, fill=fill)
        col = (colors or [PRIMARY])[i % len(colors or [PRIMARY])]
        text(s, tx + 0.25, ty + 0.15, tw - 0.5, num_size / 72 * 1.25, num, size=num_size, bold=True, color=col)
        text(s, tx + 0.25, ty + 0.2 + num_size / 72 * 1.3, tw - 0.45, th - 0.3 - num_size / 72 * 1.3, lab,
             size=16, color=MUTED, spacing=1.02)


def s_testing(deck, sd):
    s = deck.new(sd)
    tiles(s, MX, TOP, CW, sd["tiles"], 4, 1.55)
    y = TOP + 1.8
    box(s, MX, y, CW, 2.55, fill=WHITE, line=LINE)
    text(s, MX + 0.35, y + 0.2, CW - 0.7, 0.4, sd["examples_head"], size=18, bold=True)
    yy = y + 0.75
    for i, ex in enumerate(sd["examples"]):
        circle(s, MX + 0.35, yy + 0.04, 0.4, SUCCESS_SOFT, "✓", color=SUCCESS, size=16)
        text(s, MX + 0.95, yy, CW - 1.3, 0.48, ex, size=17, anchor="m")
        yy += 0.56
    text(s, MX, y + 2.75, CW, 0.4, sd["extra"], size=16, color=MUTED)


def s_results(deck, sd):
    s = deck.new(sd)
    cw = 6.75
    text(s, MX, TOP - 0.05, cw, 0.4, sd["chart_title"], size=18, bold=True)
    bar_chart(s, MX - 0.1, TOP + 0.3, cw + 0.1, 4.15, sd["cats"],
              [(sd["series"][0], sd["rules"]), (sd["series"][1], sd["gemini"])],
              [LINE_STRONG, PRIMARY], maxv=112, fmt='[=100]0;0.0', size=16, label_size=16, gap=45, horizontal=True)
    text(s, MX, TOP + 4.55, cw, 0.4, sd["chart_note"], size=16, color=MUTED, spacing=1.0)
    x = MX + cw + 0.35
    tiles(s, x, TOP, W - MX - x, sd["tiles"], 2, 1.5, gap=0.18, num_size=30,
          colors=[PRIMARY, SUCCESS, SUCCESS, PRIMARY, PRIMARY, PRIMARY])




def s_future(deck, sd):
    s = deck.new(sd)
    n = len(sd["cols"])
    gap = 0.35
    cw = (CW - gap * (n - 1)) / n
    fills = [PRIMARY_SOFT, BG, BG]
    for i, col in enumerate(sd["cols"]):
        x = MX + i * (cw + gap)
        box(s, x, TOP, cw, 4.95, fill=fills[i])
        circle(s, x + 0.3, TOP + 0.3, 0.52, PRIMARY if i == 0 else LINE_STRONG, str(i + 1),
               color=WHITE if i == 0 else INK, size=18)
        text(s, x + 1.0, TOP + 0.3, cw - 1.2, 0.52, col["head"], size=22, bold=True, anchor="m")
        bullets(s, x + 0.35, TOP + 1.2, cw - 0.6, col["items"], size=17, h=3.6, after=14)


def s_thanks(deck, sd):
    d = deck.d
    s = deck.new(sd, dark=True)
    logo(s, MX + 0.1, 0.6, 0.7, on_dark=True)
    text(s, MX + 1.0, 0.6, 5, 0.7, {"runs": [{"t": "ALT "}, {"t": "STORES", "color": "C9D3FF"}]},
         size=30, color=WHITE, bold=True, anchor="m")
    text(s, MX + 0.1, 2.3, 7.9, 1.2, sd["title"], size=fit_size(sd["title"], 7.8, 48), bold=True, color=WHITE)
    text(s, MX + 0.1, 3.55, 7.4, 0.6, sd["sub"], size=22, color="DCE3FF")
    text(s, MX + 0.1, 4.6, 7.4, 0.5, d["site"], size=26, bold=True, color=WHITE)
    a = d["author"]
    text(s, MX + 0.1, 6.35, 7.4, 0.4, f"{a['name']} · {d['footer']}", size=16, color="C9D3FF")
    qr = qrcode.QRCode(border=1, box_size=20, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(d["site_url"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="#" + INK, back_color="white")
    p = CACHE / "qr.png"
    img.save(p)
    box(s, 8.85, 1.6, 3.6, 4.15, fill=WHITE, radius=0.22)
    s.shapes.add_picture(str(p), Inches(9.15), Inches(1.85), Inches(3.0), Inches(3.0))
    text(s, 8.85, 4.95, 3.6, 0.5, "Демо-версия", size=16, color=MUTED, align="c")


# ------------------------------------------------------------------ backup slides
def s_b_er(deck, sd):
    s = deck.new(sd)
    cap = sd["captions"]
    _, w1, h1 = picture(s, DIAGRAMS / "er_main.png", MX, TOP, h=4.55, radius=0.08, descr=cap[0])
    x = MX + w1 + 0.3
    _, w2, h2 = picture(s, DIAGRAMS / "er_stock.png", x, TOP, h=4.55, radius=0.08, descr=cap[1])
    text(s, MX, TOP + 4.62, w1, 0.35, cap[0], size=16, color=MUTED)
    text(s, x, TOP + 4.62, w2, 0.35, cap[1], size=16, color=MUTED)


def s_b_llm(deck, sd):
    s = deck.new(sd)
    cw = 6.8
    text(s, MX, TOP - 0.05, cw, 0.4, sd["chart_title"], size=18, bold=True)
    bar_chart(s, MX - 0.1, TOP + 0.3, cw + 0.1, 4.6, sd["cats"],
              [(sd["series"][0], sd["gemini"]), (sd["series"][1], sd["groq"])],
              [PRIMARY, ACCENT], maxv=112, fmt='[=100]0;0.0', size=16, label_size=16, gap=50, horizontal=True)
    x = MX + cw + 0.4
    w = W - MX - x
    table(s, x, TOP, w, sd["table"], [w - 2.6, 1.3, 1.3], row_h=0.55, size=16, aligns=["l", "c", "c"])
    box(s, x, TOP + 3.15, w, 1.75, fill=PRIMARY_SOFT)
    text(s, x + 0.3, TOP + 3.15, w - 0.6, 1.75, sd["conclusion"], size=17, bold=True, color=INK, anchor="m")


def s_b_speed(deck, sd):
    s = deck.new(sd)
    cw = 6.9
    text(s, MX, TOP - 0.05, cw, 0.4, sd["chart_title"], size=18, bold=True)
    ch = bar_chart(s, MX - 0.1, TOP + 0.35, cw, 3.85, sd["stages"], [("с", sd["secs"])], [PRIMARY],
                   horizontal=True, fmt='0.00', legend=False, size=16, label_size=16, gap=40)
    x = MX + cw + 0.4
    w = W - MX - x
    text(s, x, TOP - 0.05, w, 0.4, sd["donut_title"], size=18, bold=True)
    donut(s, x - 0.1, TOP + 0.35, 2.3, 2.3, ["Ожидание лимитов", "Сами запросы"],
          [sd["wait"], round(100 - sd["wait"], 1)], [ACCENT, PRIMARY])
    text(s, x + 2.35, TOP + 0.6, w - 2.35, 0.55, "96 %", size=30, bold=True, color="B85A00")
    text(s, x + 2.35, TOP + 1.15, w - 2.35, 0.6, "ожидание лимитов и перегрузки", size=16, color=MUTED)
    text(s, x + 2.35, TOP + 1.8, w - 2.35, 0.5, "4 % — сами запросы", size=16, color=PRIMARY, bold=True)
    for i, (k1, k2, col) in enumerate((("big1", "big1_text", SUCCESS), ("big2", "big2_text", MUTED))):
        bx = x + i * (w / 2 + 0.05)
        bw = w / 2 - 0.05
        box(s, bx, TOP + 2.85, bw, 1.35, fill=SUCCESS_SOFT if i == 0 else BG)
        text(s, bx + 0.2, TOP + 2.95, bw - 0.4, 0.6, sd[k1], size=28, bold=True, color=col)
        text(s, bx + 0.2, TOP + 3.55, bw - 0.4, 0.6, sd[k2], size=16, color=INK, spacing=1.0)
    box(s, MX, TOP + 4.37, CW, 0.6, fill=PRIMARY_SOFT)
    text(s, MX + 0.3, TOP + 4.37, CW - 0.6, 0.6, sd["bottom"], size=16, bold=True, anchor="m")


def s_b_usecase(deck, sd):
    s = deck.new(sd)
    im = Image.open(DIAGRAMS / "usecase.png")
    w = 4.95 * im.width / im.height
    picture(s, DIAGRAMS / "usecase.png", (W - w) / 2, TOP, h=4.95, radius=0.08, descr=sd["title"])


def s_b_security(deck, sd):
    s = deck.new(sd)
    gap = 0.3
    cw = (CW - 2 * gap) / 3
    for i, (head, desc) in enumerate(sd["cards"]):
        c, r = i % 3, i // 3
        x, y = MX + c * (cw + gap), TOP + r * 2.5
        box(s, x, y, cw, 2.2, fill=BG)
        circle(s, x + 0.3, y + 0.3, 0.5, PRIMARY_SOFT, str(i + 1), color=PRIMARY, size=18)
        text(s, x + 0.95, y + 0.3, cw - 1.2, 0.5, head, size=20, bold=True, anchor="m")
        text(s, x + 0.3, y + 1.0, cw - 0.6, 1.1, desc, size=17, color=MUTED, spacing=1.05)


def s_b_tests(deck, sd):
    s = deck.new(sd)
    table(s, MX, TOP, CW, sd["table"], [3.3, 2.1, CW - 5.4], row_h=0.62, size=17, aligns=["l", "c", "l"])




def s_b_dict(deck, sd):
    s = deck.new(sd)
    lw = 4.4
    y = TOP + 0.1
    for line in sd["raw"]:
        b = box(s, MX, y, lw, 0.7, fill=BG, radius=0.1)
        shape_text(b, {"t": line}, size=20, bold=True, pad=0.25)
        y += 0.9
    arrow(s, MX + lw + 0.15, TOP + 1.3, MX + lw + 0.95, TOP + 1.3, color=PRIMARY, width=3.5)
    cx = MX + lw + 1.15
    cw = 4.0
    box(s, cx, TOP, cw, 2.7, fill=WHITE, line=LINE_STRONG, radius=0.16)
    text(s, cx + 0.3, TOP + 0.2, cw - 0.6, 0.4, "Оперативная память", size=16, color=MUTED)
    yy = TOP + 0.75
    for k, v in sd["result"]:
        text(s, cx + 0.3, yy, 1.9, 0.5, k, size=17, color=MUTED, anchor="m")
        text(s, cx + 2.2, yy, cw - 2.4, 0.5, v, size=20, bold=True, anchor="m")
        yy += 0.6
    fx = cx + cw + 0.35
    fw = W - MX - fx
    for i, (num, lab) in enumerate(sd["facts"]):
        box(s, fx, TOP + i * 1.4, fw, 1.25, fill=PRIMARY_SOFT)
        text(s, fx + 0.25, TOP + i * 1.4 + 0.1, fw - 0.5, 0.6, num, size=30, bold=True, color=PRIMARY)
        text(s, fx + 0.25, TOP + i * 1.4 + 0.68, fw - 0.5, 0.55, lab, size=16, color=INK, spacing=1.0)
    y = TOP + 3.2
    n = len(sd["levels"])
    gap = 0.3
    lw2 = (CW - gap * (n - 1)) / n
    styles = [(SUCCESS_SOFT, SUCCESS), (INFO_SOFT, INFO), (DANGER_SOFT, DANGER)]
    for i, ((head, desc), (f, c)) in enumerate(zip(sd["levels"], styles)):
        x = MX + i * (lw2 + gap)
        box(s, x, y, lw2, 1.6, fill=f)
        text(s, x + 0.3, y + 0.2, lw2 - 0.6, 0.45, head, size=20, bold=True, color=c)
        text(s, x + 0.3, y + 0.75, lw2 - 0.6, 0.7, desc, size=17, color=INK)




def s_b_builds(deck, sd):
    s = deck.new(sd)
    rows = sd["table"]
    table(s, MX, TOP, CW, rows, [6.3, 1.9, 2.1, 1.83], row_h=0.48, size=16, aligns=["l", "c", "c", "c"],
          mark=lambda r, c: SUCCESS_SOFT if r == len(rows) - 1 else None)
    text(s, MX, TOP + 0.48 * len(rows) + 0.15, CW, 0.4, sd["note"], size=16, color=MUTED)


BUILDERS = {k[2:]: v for k, v in globals().items() if k.startswith("s_")}


def embed_fonts():
    """If PowerPoint is installed (Windows), re-save the deck with Inter embedded,
    so it looks the same on a computer without the font. Otherwise keep the file as is."""
    if sys.platform != "win32" or "--no-embed" in sys.argv:
        return
    tmp = OUT.with_name("_embed_tmp.pptx")
    ps = ("$pp = New-Object -ComObject PowerPoint.Application; "
          f"$p = $pp.Presentations.Open('{OUT}', -1, 0, 0); "
          f"$p.SaveAs('{tmp}', 24, -1); $p.Close(); "
          "if ($pp.Presentations.Count -eq 0) { $pp.Quit() }")  # never close the user's open decks
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=300,
                       capture_output=True)
        tmp.replace(OUT)
        print("fonts embedded by PowerPoint")
    except Exception as e:  # no PowerPoint: the deck still works, Inter must be installed to look right
        tmp.unlink(missing_ok=True)
        print(f"fonts not embedded ({type(e).__name__}); install docs/presentation/fonts on the defense PC")


def main():
    data = yaml.safe_load((HERE / "slides.yaml").read_text(encoding="utf-8"))
    deck = Deck(data)
    for sd in data["slides"]:
        BUILDERS[sd["id"]](deck, sd)
    deck.prs.core_properties.title = "ALT STORES — защита ВКР"
    deck.prs.core_properties.author = data["author"]["name"]
    deck.prs.save(OUT)
    embed_fonts()
    main_time = sum(sd.get("time", 0) for sd in data["slides"])
    print(f"{OUT.name}: {deck.n} slides, talk {main_time // 60}:{main_time % 60:02d}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
