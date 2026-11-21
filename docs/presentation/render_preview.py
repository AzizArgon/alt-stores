"""Render ALT_STORES_defense.pptx to PDF (LibreOffice) and every slide to PNG in preview/.

Run from the repository root:  py -3.12 docs/presentation/render_preview.py
Needs LibreOffice (soffice) and: pip install pymupdf
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf as fitz

HERE = Path(__file__).resolve().parent
DECK = HERE / "ALT_STORES_defense.pptx"
PREVIEW = HERE / "preview"
PDF = HERE / "ALT_STORES_defense.pdf"


def soffice() -> str:
    for p in (shutil.which("soffice"), r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if p and Path(p).exists():
            return p
    sys.exit("LibreOffice not found: install it (winget install TheDocumentFoundation.LibreOffice)")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp, "profile").as_uri()
        subprocess.run([soffice(), f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
                        "--outdir", tmp, str(DECK)], check=True, timeout=300)
        shutil.copy(Path(tmp, DECK.with_suffix(".pdf").name), PDF)
    PREVIEW.mkdir(exist_ok=True)
    for old in PREVIEW.glob("slide-*.png"):
        old.unlink()
    doc = fitz.open(PDF)
    for i, page in enumerate(doc, 1):
        page.get_pixmap(dpi=110).save(PREVIEW / f"slide-{i:02d}.png")
    print(f"{PDF.name}: {len(doc)} pages -> {PREVIEW}")


if __name__ == "__main__":
    main()
