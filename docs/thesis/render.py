"""Open the built docx in Microsoft Word: update the table of contents and fields, save,
export PDF and (with --png) render every page to pages/NNN.png for a visual check."""
import sys
from pathlib import Path

import win32com.client

HERE = Path(__file__).resolve().parent
DOCX = HERE / "ALT_STORES_VKR.docx"
PDF = HERE / "ALT_STORES_VKR.pdf"


def word_update():
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str(DOCX))
        doc.Fields.Update()
        for t in doc.TablesOfContents:
            t.Update()
        doc.Repaginate()
        for t in doc.TablesOfContents:
            t.Update()
        pages = doc.ComputeStatistics(2)  # wdStatisticPages
        doc.Save()
        doc.ExportAsFixedFormat(str(PDF), 17)  # wdExportFormatPDF
        doc.Close(False)
    finally:
        word.Quit()
    return pages


def render_png():
    import fitz
    out = HERE / "pages"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    pdf = fitz.open(PDF)
    for i, page in enumerate(pdf, 1):
        page.get_pixmap(dpi=70).save(out / f"{i:03d}.png")
    return len(pdf)


if __name__ == "__main__":
    print("pages:", word_update())
    if "--png" in sys.argv:
        print("png:", render_png(), "->", HERE / "pages")


def contact_sheets(per_row=5, rows=2, width=300):
    """pages/sheet_NN.png: pages side by side (5x2) for a quick look."""
    from PIL import Image
    files = sorted((HERE / "pages").glob("[0-9]*.png"))
    per = per_row * rows
    for s in range(0, len(files), per):
        imgs = [Image.open(f) for f in files[s:s + per]]
        h = int(imgs[0].height * width / imgs[0].width)
        sheet = Image.new("RGB", (per_row * (width + 6), rows * (h + 6)), "gray")
        for k, im in enumerate(imgs):
            sheet.paste(im.resize((width, h)), ((k % per_row) * (width + 6), (k // per_row) * (h + 6)))
        sheet.save(HERE / "pages" / f"sheet_{s // per + 1:02d}.png")


if __name__ == "__main__" and "--png" in sys.argv:
    contact_sheets()
