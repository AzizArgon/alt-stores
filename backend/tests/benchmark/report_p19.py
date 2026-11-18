"""Phase 19: tables "Phase 7 -> Phase 19" for docs/experiment.md section 10 (results/tables_p19.md).

  .venv/Scripts/python.exe tests/benchmark/report_p19.py

Needs results/{rules,gemini,groq}_after.json (Phase 7) and *_p19.json (Phase 19 cold runs:
`scripts/benchmark_parser.py suite --config <c> --live --record p19 --tag p19`).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
NEW_CATEGORIES = {"consumables", "accessories", "bags", "webcams", "microphones", "scanners", "projector_screens",
                  "panels"}  # Phase 16.1: the Phase 7 labels call these goods "other"


def category_adjusted(run: dict) -> float:
    """Category accuracy when "other" in a Phase 7 label is also right for a Phase 16.1 category."""
    scored = correct = 0
    for ds in report.datasets(run):
        f = run[ds]["fields"]["category"]
        scored += f["scored"]
        correct += f["correct"]
        correct += sum(1 for e in run[ds]["errors"] if e["field"] == "category" and e["want"] == "other"
                       and e["got"] != "other")
    return 100 * correct / scored


def resources(runs: dict[str, dict]) -> str:
    lines = ["| Показатель | " + " | ".join(runs) + " |", "|---|" + "---|" * len(runs)]
    t = {n: report.totals(r)["stats"] for n, r in runs.items()}
    lines.append("| Запросов к ИИ | " + " | ".join(str(r["_run"].get("live_requests", 0)) for r in runs.values()) + " |")
    lines.append("| Время всего набора, с | " + " | ".join(f"{r['_run']['seconds']:.0f}" for r in runs.values()) + " |")
    lines.append("| Строк правилами без ИИ, % | " + " | ".join(f"{100 * s['rule'] / s['rows']:.1f}" for s in t.values()) + " |")
    lines.append("| Категория с учётом новых категорий 16.1, % | "
                 + " | ".join(f"{category_adjusted(r):.1f}" for r in runs.values()) + " |")
    return "\n".join(lines)


def main() -> None:
    names = {"Правила, ф.7": "rules_after", "Правила, ф.19": "rules_p19", "Gemini, ф.7": "gemini_after", "Gemini ф.7 + код ф.19": "gemini_p7replay",
             "Gemini, ф.19": "gemini_p19", "Groq, ф.7": "groq_after", "Groq ф.7 + код ф.19": "groq_p7replay", "Groq, ф.19": "groq_p19"}
    runs = {k: report.load(v) for k, v in names.items() if (RESULTS / f"{v}.json").exists()}
    out = ["## Сравнение конфигураций: фаза 7 → фаза 19 (все наборы)", report.config_table(runs),
           "## Ресурсы и поправка категорий", resources({k: v for k, v in runs.items() if "_run" in v})]
    for k in ("Gemini, ф.19", "Groq, ф.19"):
        if k in runs:
            out += [f"## По наборам: {k}", report.field_table(runs[k])]
    (RESULTS / "tables_p19.md").write_text("\n\n".join(out) + "\n", encoding="utf-8")
    print((RESULTS / "tables_p19.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
