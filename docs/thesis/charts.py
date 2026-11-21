"""Figures for the thesis drawn with matplotlib -> figures/*.png.

Diagrams (pipeline, architecture) are redrawn here in a print-friendly landscape layout;
charts use the numbers from docs/experiment.md (sections 4, 10 and 11).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 12})

INK = "#1f2937"
BLUE, BLUE_BG = "#2563eb", "#dbeafe"
GREEN, GREEN_BG = "#15803d", "#dcfce7"
AMBER, AMBER_BG = "#b45309", "#fef3c7"
GRAY, GRAY_BG = "#6b7280", "#f3f4f6"
RED_BG = "#fee2e2"


# ------------------------------------------------------------------ diagram helpers
def box(ax, x, y, w, h, text, fc=BLUE_BG, ec=BLUE, size=9.5, bold_first=True):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=1.3))
    lines = text.split("\n")
    if bold_first and len(lines) > 1:
        ax.text(x, y + h / 2 - 0.22, lines[0], ha="center", va="top", fontsize=size, weight="bold", color=INK)
        ax.text(x, y + h / 2 - 0.68, "\n".join(lines[1:]), ha="center", va="top", fontsize=size - 1,
                color=INK, linespacing=1.25)
    else:
        ax.text(x, y, text, ha="center", va="center", fontsize=size, color=INK, weight="bold" if bold_first else None)


def arrow(ax, p, q, text="", color=INK, style="-|>", dashed=False, rad=0.0, tx=0, ty=0.15, size=9.5):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=14, color=color, lw=1.3,
                                 linestyle="--" if dashed else "-", connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((p[0] + q[0]) / 2 + tx, (p[1] + q[1]) / 2 + ty, text, ha="center", va="bottom",
                fontsize=size, color=color, style="italic")


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w * 2)
    ax.set_ylim(0, h * 2)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def pipeline():
    fig, ax = canvas(10, 6.4)
    W, H = 3.9, 2.0
    xs = [2.3, 7.2, 12.1, 17.0]
    r1, r2, r3 = 10.8, 6.6, 2.2
    box(ax, xs[0], r1, W, H, "1. Файл продавца\nExcel · CSV · PDF\nтекст поста Telegram", GRAY_BG, GRAY)
    box(ax, xs[1], r1, W, H, "2. Чтение\nmarkitdown / pdfplumber\nфайл → таблица Markdown")
    box(ax, xs[2], r1, W, H, "3. Очистка кодом\nцена, валюта, артикул,\nналичие — мимо ИИ", GREEN_BG, GREEN)
    box(ax, xs[3], r1, W, H, "4. Кэш разбора\nстрока уже встречалась?\nда → сразу к шагу 7")
    box(ax, xs[3], r2, W, H, "5. Правила\nаккуратная строка?\nда → сразу к шагу 7")
    box(ax, xs[2], r2, W, H, "6. Языковая модель\nGemini, запасной Groq;\nтолько непонятые строки", AMBER_BG, AMBER)
    box(ax, xs[1], r2, W, H, "7. Нормализация\nсловарь 31 категории;\nдогадки ИИ отсекаются")
    box(ax, xs[0], r2, W, H, "8. Карточка\nкод ИКПУ из справочника,\nключ сведения")
    box(ax, xs[0], r3, W, H, "9. Anti-Fraud\nправила кодом +\nподсказка ИИ (info)", RED_BG, "#b91c1c")
    box(ax, xs[1], r3, W, H, "10. Предпросмотр\nпродавец правит строки;\nправки → кэш")
    box(ax, xs[2], r3, W, H, "11. Публикация\nпредложения, история цен,\n«нет в наличии»", GREEN_BG, GREEN)
    for a, b in ((0, 1), (1, 2), (2, 3)):
        arrow(ax, (xs[a] + W / 2, r1), (xs[b] - W / 2, r1))
    arrow(ax, (xs[3], r1 - H / 2), (xs[3], r2 + H / 2), "нет", tx=0.35, ty=-0.1)
    arrow(ax, (xs[3] - W / 2, r2), (xs[2] + W / 2, r2), "нет")
    arrow(ax, (xs[2] - W / 2, r2), (xs[1] + W / 2, r2))
    arrow(ax, (xs[1] - W / 2, r2), (xs[0] + W / 2, r2))
    arrow(ax, (xs[0], r2 - H / 2), (xs[0], r3 + H / 2))
    arrow(ax, (xs[0] + W / 2, r3), (xs[1] - W / 2, r3))
    arrow(ax, (xs[1] + W / 2, r3), (xs[2] - W / 2, r3))
    save(fig, "pipeline.png")


def architecture():
    fig, ax = canvas(10, 5.6)
    box(ax, 2.0, 7.2, 3.2, 2.2, "Браузер\nпокупатель, продавец,\nадминистратор;\nПК и телефон", GRAY_BG, GRAY)
    box(ax, 6.0, 7.2, 2.8, 1.7, "Cloudflare\nHTTPS, защита")
    box(ax, 6.0, 4.4, 3.0, 1.9, "nginx сервера\n/ → web\n/api → backend")
    ax.add_patch(FancyBboxPatch((8.4, 0.6), 7.0, 9.6, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc="#f8fafc", ec=BLUE, lw=1.2, linestyle="--"))
    ax.text(11.9, 9.85, "VPS · Docker Compose", ha="center", fontsize=11, weight="bold", color=BLUE)
    box(ax, 10.2, 7.6, 3.0, 2.0, "Контейнер web\nReact + Vite (статика)\nRU · UZ · EN")
    box(ax, 13.6, 7.6, 3.4, 2.4, "Контейнер backend\nFastAPI, SQLAlchemy;\nразбор, Anti-Fraud,\nучёт, чат, брони", GREEN_BG,
        GREEN)
    box(ax, 10.2, 3.7, 3.0, 1.8, "SQLite\ndatabase.db,\n34 таблицы", AMBER_BG, AMBER)
    box(ax, 13.8, 3.7, 2.8, 1.8, "Фото\ndata/media\n(позже S3)", AMBER_BG, AMBER)
    box(ax, 12.0, 1.5, 3.6, 1.4, "Копии базы\ndata/backups, 14 дней", GRAY_BG, GRAY)
    box(ax, 18.05, 8.2, 3.8, 2.0, "Языковые модели\nGemini, запасной Groq;\nтолько непонятые строки", AMBER_BG, AMBER)
    box(ax, 18.0, 5.6, 3.2, 1.5, "Курс ЦБ\ncbu.uz, раз в день")
    box(ax, 18.0, 3.0, 3.2, 1.7, "Telegram-каналы\nпубличные посты")
    box(ax, 18.0, 0.9, 3.4, 1.4, "ПК автора\nежедневная копия", GRAY_BG, GRAY)
    arrow(ax, (3.6, 7.2), (4.6, 7.2))
    arrow(ax, (6.0, 6.35), (6.0, 5.25))
    arrow(ax, (7.4, 4.6), (8.7, 7.0))
    arrow(ax, (7.4, 4.2), (12.4, 6.6))
    arrow(ax, (13.8, 6.6), (11.4, 4.6))
    arrow(ax, (13.8, 6.6), (13.8, 4.6))
    arrow(ax, (15.3, 8.0), (16.15, 8.2))
    arrow(ax, (15.2, 7.2), (16.4, 5.7))
    arrow(ax, (15.2, 6.9), (16.4, 3.3))
    arrow(ax, (10.2, 2.8), (11.0, 2.1), dashed=True, color=GRAY)
    arrow(ax, (13.7, 1.3), (16.4, 0.9), dashed=True, color=GRAY)
    save(fig, "architecture.png")


if __name__ == "__main__":
    pipeline()
    architecture()
    print("charts: ok")
