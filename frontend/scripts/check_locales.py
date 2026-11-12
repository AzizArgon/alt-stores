"""Phase 15: uz.json and en.json have the keys of ru.json (plural forms by the language), no empty values,
the same {{params}}. `--merge DIR` first builds them from translation parts DIR/uz_*.json, DIR/en_*.json."""
import glob, json, re, sys
from pathlib import Path

LOC = Path(__file__).resolve().parent.parent / "src" / "locales"
PLURAL = re.compile(r"_(zero|one|two|few|many|other)$")
PARAM = re.compile(r"\{\{\s*(\w+)")


def flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{prefix}{k}."))
        else:
            out[prefix + k] = v
    return out


def merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            merge(a[k], v)
        else:
            a[k] = v
    return a


def ordered(ref, d):
    """Keys in the order of ru.json (a plural base keeps the language's forms in place)."""
    out = {}
    for k, v in ref.items():
        if isinstance(v, dict):
            if isinstance(d.get(k), dict):
                out[k] = ordered(v, d[k])
            continue
        base = plural_base(k, ref)
        if base:
            for form in ("one", "other"):
                if f"{base}_{form}" in d and f"{base}_{form}" not in out:
                    out[f"{base}_{form}"] = d[f"{base}_{form}"]
        elif k in d:
            out[k] = d[k]
    for k, v in d.items():
        if k not in out and not (isinstance(v, dict) and k in out):
            out[k] = v
    return out


def plural_base(k, keys):
    """"found_many" is a plural form when "found_one" exists too ("too_many" alone is a plain key)."""
    base = PLURAL.sub("", k)
    return base if base != k and f"{base}_one" in keys else None


def params(text):
    return set(PARAM.findall(str(text))) - {"count"}


def check(ru, other, lang):
    """A plain key: the same params. Plural forms (uz, en: one / other): "other" has the params of the ru
    many/other form, "one" — no params the ru forms do not have."""
    errors = []
    fr, fo = flat(ru), flat(other)
    want = {}  # key -> (params that must be there, params that may be there)
    for k, v in fr.items():
        base = plural_base(k, fr)
        if base:
            forms = [t for kk, t in fr.items() if plural_base(kk, fr) == base]
            allowed = set().union(*(params(t) for t in forms))
            many = fr.get(f"{base}_other") or fr.get(f"{base}_many") or v
            want[f"{base}_one"] = (set(), allowed)
            want[f"{base}_other"] = (params(many), allowed)
        else:
            want[k] = (params(v), params(v))
    for k, (must, may) in want.items():
        if k not in fo:
            errors.append(f"{lang}: missing {k}")
        elif not str(fo[k]).strip():
            errors.append(f"{lang}: empty {k}")
        elif not (must <= params(fo[k]) <= may):
            errors.append(f"{lang}: params differ {k}: {sorted(must)} vs {sorted(params(fo[k]))}")
    for k in fo:
        if k not in want:
            errors.append(f"{lang}: extra {k}")
    return errors


if __name__ == "__main__":
    ru = json.loads((LOC / "ru.json").read_text(encoding="utf8"))
    if len(sys.argv) > 2 and sys.argv[1] == "--merge":
        for lang in ("uz", "en"):
            d = {}
            for p in sorted(glob.glob(f"{sys.argv[2]}/{lang}_*.json")):
                merge(d, json.loads(Path(p).read_text(encoding="utf8")))
            (LOC / f"{lang}.json").write_text(json.dumps(ordered(ru, d), ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    errs = []
    for lang in ("uz", "en"):
        errs += check(ru, json.loads((LOC / f"{lang}.json").read_text(encoding="utf8")), lang)
    sys.stdout.reconfigure(encoding="utf8")
    print("\n".join(errs) if errs else "ok")
    sys.exit(1 if errs else 0)
