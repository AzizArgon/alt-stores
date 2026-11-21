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


# ------------------------------------------------------------------ screenshots
SHOTS = ROOT_SHOTS = HERE.parent / "screenshots" / "final"
# name: max height in source pixels after the automatic trim of empty side margins
SHOT_LIST = {"01_home": 1080, "02_search_12400f": 900, "03_product_offers": 1500, "04_used": 1000,
             "05_build": 1100, "06_seller_goods": 900, "07_import_preview": 1500, "08_stock": 760,
             "08b_stock_journal": 1000, "09_reservations": 600, "10_notifications": 1000, "11_admin": 800,
             "14_market": 1550, "15_buyer_reservations": 700, "01_home_uz": 760, "phone_home": 1624,
             "phone_product": 1624, "phone_seller_stock": 1624}


def shots():
    from PIL import Image, ImageChops
    for name, max_h in SHOT_LIST.items():
        im = Image.open(SHOTS / f"{name}.jpg").convert("RGB")
        im = im.crop((0, 0, im.width, min(im.height, max_h)))
        if name[:2] in ("01", "02", "03", "04", "05", "14", "15"):  # storefront: centered container
            im = im.crop((300, 0, 1620, im.height))
        im.save(OUT / f"shot_{name}.jpg", quality=90)


if __name__ == "__main__":
    shots()


# ------------------------------------------------------------------ experiment charts (docs/experiment.md)
C_RULES, C_GEMINI, C_GROQ = "#0d9488", "#2563eb", "#ea580c"  # validated: scripts/validate_palette.js


def _axes_clean(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#9ca3af")
    ax.spines["bottom"].set_color("#9ca3af")
    ax.tick_params(colors=INK)
    ax.grid(axis="x", color="#e5e7eb", lw=0.8)
    ax.set_axisbelow(True)


def accuracy():
    """experiment.md 10.1-10.2: accuracy by field, phase 19, all sets."""
    fields = ["Категория", "Бренд", "Модель", "Цена", "Валюта", "Верная карточка", "Характеристики"]
    rules = [69.5, 68.6, 63.4, 100, 100, 74.6, 71.7]
    gemini = [99.1, 99.5, 97.2, 100, 100, 93.1, 94.5]
    groq = [98.9, 98.3, 96.8, 99.9, 99.9, 92.5, 94.5]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    y = range(len(fields))
    h = 0.26
    for k, (vals, color, label) in enumerate(((rules, C_RULES, "Только правила"), (gemini, C_GEMINI, "Правила + Gemini"),
                                              (groq, C_GROQ, "Правила + Groq"))):
        ax.barh([i + (k - 1) * (h + 0.02) for i in y], vals, height=h, color=color, label=label)
    for i, v in enumerate(gemini):
        ax.text(v + 0.6, i, f"{v:.1f}".replace(".", ","), va="center", fontsize=9, color=INK)
    ax.set_yticks(list(y), fields)
    ax.invert_yaxis()
    ax.set_xlim(0, 106)
    ax.set_xlabel("Доля верных значений, %")
    _axes_clean(ax)
    ax.legend(loc="lower left", frameon=False, ncol=3, bbox_to_anchor=(0, -0.28))
    save(fig, "accuracy.png")


def who_parsed():
    """experiment.md 11.2: who parsed the 2 359 rows of the real price list."""
    runs = ["Повторная загрузка\n(как на сервере)", "Первая загрузка\n(холодный прогон)", "Повтор после\nпервой загрузки"]
    cache = [2226, 0, 896]
    rules = [133, 641, 641]
    ai = [0, 1718, 822]
    fig, ax = plt.subplots(figsize=(8, 3.0))
    left = [0, 0, 0]
    for vals, color, label in ((cache, C_GEMINI, "Кэш"), (rules, C_RULES, "Правила"), (ai, C_GROQ, "Языковая модель")):
        ax.barh(runs, vals, left=left, color=color, label=label, height=0.55, edgecolor="white", linewidth=2)
        for i, v in enumerate(vals):
            if v > 150:
                ax.text(left[i] + v / 2, i, f"{v}", ha="center", va="center", fontsize=9.5, color="white", weight="bold")
        left = [a + b for a, b in zip(left, vals)]
    ax.invert_yaxis()
    ax.set_xlabel("Строк прайса (всего 2 359)")
    _axes_clean(ax)
    ax.legend(loc="lower left", frameon=False, ncol=3, bbox_to_anchor=(0, -0.42))
    save(fig, "who_parsed.png")


def providers():
    """experiment.md 10.2: Gemini vs Groq, same 384 rows — requests and time as two panels."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 2.6))
    for ax, vals, title, fmt in ((a1, [6, 31], "Запросов к модели", "{}"), (a2, [325, 740], "Время набора, с", "{}")):
        ax.barh(["Gemini", "Groq"], vals, color=[C_GEMINI, C_GROQ], height=0.5)
        for i, v in enumerate(vals):
            ax.text(v * 1.02, i, fmt.format(v), va="center", fontsize=10, color=INK)
        ax.set_title(title, fontsize=11, color=INK)
        ax.set_xlim(0, max(vals) * 1.2)
        ax.invert_yaxis()
        _axes_clean(ax)
    fig.tight_layout()
    save(fig, "providers.png")


if __name__ == "__main__":
    accuracy()
    who_parsed()
    providers()
