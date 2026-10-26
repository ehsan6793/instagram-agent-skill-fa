#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
swipe.py - رتبه‌بندیِ ریل‌هایی که جمع کردی بر اساس اینکه چقدر از میانگینِ خودِ همون پیج جلو زدن،
اسمِ فرمولِ هوکِ هر کدوم، و نوشتنِ فایلِ swipe.

Rank collected reels by how far each beat its own account, name the hook formula each
used, and write the swipe file. One correction is the point of this script: raw views are
not evidence. A 2,000,000-follower page doing 400,000 views had a quiet day. A 4,000-follower
page doing 400,000 views found something. This ranks on the multiple over the page's own baseline.

ورودی یه فایلِ جدا‌شده با تب (TSV) که موقعِ گشتن پر می‌کنی، هر ریل یه سطر، با یه سطرِ عنوان:

    account   followers   median   views   hook
    @someone  48K         11K      412K    هیچ‌کس بهت نمی‌گه که سی تا ریلِ اولت می‌سوزه

عددها هر شکلی که باشن خونده می‌شن: 412000، ۴۱۲٬۰۰۰، 412k، 1.2m، «۴۱۲ هزار»، «۱٫۲ میلیون».
`median` میانگینِ معمولیِ بازدیدِ اخیرِ اون پیجه و baselineِ بهتریه. اگه فقط `followers` داری،
median رو نذار؛ اسکریپت می‌گه از چی استفاده کرد. `hook` خطِ اولِ ریله، گفتاری یا روی صفحه، با کلماتِ خودشون.

Usage
  python3 swipe.py captured.tsv
  python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
  python3 swipe.py captured.tsv --json
  python3 swipe.py captured.tsv --visual
"""

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fatext as F                            # noqa: E402

F.ensure_utf8()

HOOKS_CANDIDATES = [os.path.join(HERE, "..", "ig-reel-fa", "hooks.json"),
                    os.path.join(HERE, "hooks.json")]
HOOKS = next((p for p in HOOKS_CANDIDATES if os.path.exists(p)), HOOKS_CANDIDATES[0])

score_hook = None
for _d in (os.path.join(HERE, "..", "ig-reel-fa"), HERE):    # optional: score the hooks too
    try:
        if os.path.exists(os.path.join(_d, "hookscore.py")):
            sys.path.insert(0, _d)
            from hookscore import run as score_hook    # noqa: E402
            break
    except Exception:
        score_hook = None

_MULT = {"k": 1e3, "m": 1e6, "b": 1e9, "هزار": 1e3, "میلیون": 1e6, "میلیارد": 1e9, "ک": 1e3}


def parse_count(s):
    """'412k' '۴۱۲٬۰۰۰' '1.2m' '۱٫۲ میلیون' '412 هزار' -> int, or None."""
    if s is None:
        return None
    t = F.prep(str(s)).strip().lower().replace("٫", ".").replace(",", "")
    t = F.match_form(t)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(k|m|b|هزار|میلیون|میلیارد)?\b", t)
    if not m:
        return None
    n = float(m.group(1)) * _MULT.get(m.group(2), 1)
    return int(round(n))


def load_formulas(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None
    by_id = {h["id"]: h for h in d["hooks"]}
    order = d.get("classify_order") or sorted(by_id)
    return [(by_id[i]["id"], by_id[i]["name"], re.compile(by_id[i]["match"], re.IGNORECASE))
            for i in order if i in by_id]


def classify(hook, formulas):
    if not formulas:
        return None, "unclassified"
    form = F.match_form(hook)
    for fid, name, pattern in formulas:
        if pattern.search(form):
            return fid, name
    return None, "unclassified"


def read_rows(path):
    raw = sys.stdin.read() if path == "-" else F.read_text(path)
    lines = [l for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return []
    head = [c.strip().lower() for c in lines[0].split("\t")]
    if "views" in head and "hook" in head:
        cols, body = head, lines[1:]
    else:
        cols, body = ["account", "followers", "views", "hook"], lines
    rows = []
    for line in body:
        cells = line.split("\t")
        if len(cells) < len(cols):
            cells += [""] * (len(cols) - len(cells))
        r = dict(zip(cols, [c.strip() for c in cells]))
        views = parse_count(r.get("views", ""))
        if not views:
            continue
        r["views"] = views
        for k in ("followers", "median"):
            r[k] = parse_count(r.get(k, ""))
        if r.get("hook"):
            rows.append(r)
    return rows


def analyse(rows, formulas):
    used_median = any(r.get("median") for r in rows)
    for r in rows:
        base = r.get("median") or r.get("followers") or 0
        r["baseline"] = base
        r["outlier"] = round(r["views"] / base, 2) if base else None
        r["formula_id"], r["formula"] = classify(r["hook"], formulas)
        r["words"] = len(F.words(r["hook"]))
        if score_hook:
            _, overall, verdict, _ = score_hook(r["hook"])
            r["hook_score"], r["hook_verdict"] = round(overall, 1), verdict
        else:
            r["hook_score"], r["hook_verdict"] = None, None
    ranked = sorted(rows, key=lambda r: -(r["outlier"] or 0))
    third = max(1, len(ranked) // 3)
    top, bottom = ranked[:third], ranked[-third:]

    def med(items, key):
        vals = [i[key] for i in items if i.get(key) is not None]
        return round(statistics.median(vals), 1) if vals else None

    counts = {}
    for r in top:
        counts[r["formula"]] = counts.get(r["formula"], 0) + 1
    return {
        "baseline": "account median" if used_median else "follower count",
        "n": len(ranked), "accounts": len({r.get("account", "") for r in ranked}),
        "reels": ranked,
        "top_formulas": sorted(counts.items(), key=lambda kv: -kv[1]),
        "top_hook_score": med(top, "hook_score"), "bottom_hook_score": med(bottom, "hook_score"),
        "top_words": med(top, "words"), "bottom_words": med(bottom, "words"),
        "unclassified": sum(1 for r in ranked if r["formula"] == "unclassified"),
    }


def render(a, out=sys.stdout):
    V = F.V
    head = (f"SWIPE FILE  |  {a['n']} reels  |  {a['accounts']} accounts  |  baseline: {a['baseline']}")
    print("\n" + head, file=out)
    print("=" * max(len(head), 78), file=out)
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "   ?"
        score = f"{r['hook_score']:.0f}" if r["hook_score"] is not None else " -"
        fid = f"#{r['formula_id']:<2}" if r["formula_id"] else "-  "
        print(f"  {mult:>7}  hook {score:>3}  {fid} " + V(r["formula"][:22]) +
              f"  {r.get('account', '')[:16]}  {r['views']:>10,}", file=out)
        print("           " + V("«" + r["hook"][:96] + "»"), file=out)
    print("-" * max(len(head), 78), file=out)
    print("WHAT IS WORKING IN THIS BATCH | چی توی این دسته جواب می‌ده", file=out)
    if a["top_formulas"]:
        print("  " + V("یک‌سومِ بالاییِ outlier: " + "، ".join(f"{n} x{c}" for n, c in a["top_formulas"][:4])), file=out)
    if a["top_hook_score"] is not None:
        print(f"  median hook score:  top {a['top_hook_score']:.0f}  vs bottom {a['bottom_hook_score']:.0f}", file=out)
    print(f"  median hook length: top {a['top_words']} words  vs bottom {a['bottom_words']} words", file=out)
    print("  " + V(f"دسته‌بندی‌نشده: {a['unclassified']} از {a['n']}. اینا رو با دست بخون؛ فرمولی که هنوز "
                   "نداری اونجا قایمه."), file=out)
    print("\n  " + V("یه دسته‌ی دستی‌جمع‌شده شاهده، نه اثبات. دوازده ریل چیزی نشون نمی‌ده؛ چهل ریل از شش پیج یه چیزی "
                     "نشون می‌ده. قبل از باور کردن بیشتر جمع کن.") + "\n", file=out)


def to_markdown(a):
    lines = ["# Swipe file", "",
             f"{a['n']} reels across {a['accounts']} accounts. Ranked by multiple over {a['baseline']}.", ""]
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "?"
        lines += [f"## {mult}  {r['formula']}  ({r.get('account', '')})",
                  f"- views: {r['views']:,}  baseline: {r['baseline']:,}",
                  f"- hook score: {r['hook_score']}  words: {r['words']}",
                  f"- hook: «{r['hook']}»", ""]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Rank collected reels by outlier multiple.")
    ap.add_argument("input", nargs="?", default="-", help="TSV file, or - for stdin")
    ap.add_argument("--hooks", default=HOOKS, help="path to ig-reel-fa/hooks.json")
    ap.add_argument("--out", help="also write the swipe file as markdown here")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--visual", action="store_true", help="fix display in bidi-less terminals")
    args = ap.parse_args()
    if args.visual:
        F.set_visual(True)

    rows = read_rows(args.input)
    if not rows:
        print("no usable rows. Need a tab-separated file with at least views and hook.", file=sys.stderr)
        sys.exit(2)
    formulas = load_formulas(args.hooks)
    a = analyse(rows, formulas)
    if not formulas:
        print("note: hooks.json not found, formulas not named. Pass --hooks.", file=sys.stderr)
    if score_hook is None:
        print("note: hookscore.py not importable, hook scores skipped.", file=sys.stderr)

    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    if args.out:
        path = os.path.expanduser(args.out)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(to_markdown(a))
        print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
