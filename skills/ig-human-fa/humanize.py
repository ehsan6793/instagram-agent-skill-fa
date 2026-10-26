#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
humanize.py - پاک‌کردنِ اثرِ انگشتِ ماشین از یه متنِ فارسی.

Strip the machine fingerprint out of a Persian draft. Passes, in this order:

  0. SPELLING     ي/ك عربی -> ی/ک، رقمِ عربی -> فارسی، کشیده حذف. (پاکسازیِ املا، نه اثرِ ماشین)
  1. INVISIBLE    حذفِ کاراکترهای نامرئی که کیبوردِ آدم تولید نمی‌کنه. ولی نیم‌فاصله‌ی بینِ دو حرف،
                  ZWJ توی ایموجی و LRM/RLM روی خطِ فارسی+لاتین «می‌مونن»: بدونشون فارسی خراب می‌شه.
  2. TYPOGRAPHIC  خط تیره‌ی بلند -> «،»، گیومه‌ی فرنگی -> «»، سه‌نقطه، بولت.
  3. LEXICAL      عبارت‌های کلیشه‌ایِ slop.json (دنیای پرشتابِ امروز، شایان ذکر است…) -> ساده یا حذف.
  4. SPOKEN       (اختیاری، --spoken) کتابی -> محاوره‌ای: می‌خواهم->می‌خوام، را->رو، است->ـه. تقریبیه.

ساختارهای ماشینی (سه‌تایی، «نه تنها… بلکه»، دیوارِ هشتگ) فقط «گزارش» می‌شن و خودکار بازنویسی
نمی‌شن: بازنویسیِ شکلِ جمله قضاوت می‌خواد، پس کارِ مدله، نه regex.

Usage
  python3 humanize.py draft.txt
  python3 humanize.py draft.txt --report
  python3 humanize.py draft.txt --spoken --report
  python3 humanize.py draft.txt --persian-digits --persian-punct
  python3 humanize.py draft.txt -o clean.txt
  python3 humanize.py draft.txt --json
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:                      # python -I does not add the script dir
    sys.path.insert(0, HERE)

import fatext as F                            # noqa: E402

F.ensure_utf8()

LEX = os.path.join(HERE, "slop.json")
URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")
PUNCT = "،؛؟,.;:!?"


def load_lexicon(path=LEX):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def protect_urls(text):
    found = []

    def stash(m):
        found.append(m.group(0))
        return f"\x00URL{len(found) - 1}\x00"

    return URL_RE.sub(stash, text), found


def restore_urls(text, found):
    for i, url in enumerate(found):
        text = text.replace(f"\x00URL{i}\x00", url)
    return text


def pass_typographic(text, lex):
    hits = []
    for entry in lex["typographic"]:
        ch = entry["from"]
        n = text.count(ch)
        if not n:
            continue
        hits.append({"name": f"{ch} {entry['name']}", "count": n, "to": entry["to"].strip() or "(حذف)"})
        if ch == "—":
            text = re.sub(r"\s*—\s*", "، ", text)
        elif ch == "–":
            text = re.sub(r"\s*–\s*(?=\d)", "-", text)
            text = re.sub(r"\s+–\s+", "، ", text)
            text = text.replace("–", "-")
        else:
            text = text.replace(ch, entry["to"])
    return text, hits


def _cleanup(text):
    """After deleting a clause, remove the punctuation it leaves orphaned."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?m)^[ \t]*(?:[،؛,;:][ \t]*)+", "", text)         # line opens on a comma
    text = re.sub(r"(?m)^[ \t](?=\S)", "", text)
    text = re.sub(r"[ \t]+([،؛؟,.;:!?])", r"\1", text)                  # space before punctuation
    text = re.sub(r"([،,])\s*([،,.;:!؟?])", r"\2", text)                 # comma then other mark
    text = text.replace("...", "\x00ELL\x00")
    text = re.sub(r"\.\s*\.+", ".", text)
    text = re.sub(r"([!؟?])\s*\.", r"\1", text)
    text = text.replace("\x00ELL\x00", "...")
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?m)[ \t]+$", "", text)
    return text


def _apply_entries(text, entries):
    """Longest first so phrases win. Returns (text, hits)."""
    hits = []
    for entry in sorted(entries, key=lambda e: len(e["find"]), reverse=True):
        pattern = F.phrase_regex(entry["find"])
        found = pattern.findall(text)
        if not found:
            continue
        repl = entry["replace"]
        hits.append({"find": entry["find"].replace(F.ZWNJ, "‌"), "replace": repl or "(حذف)",
                     "count": len(found), "family": entry.get("family", "spoken")})
        text = pattern.sub(lambda m, r=repl: r, text)
    return text, hits


def pass_lexical(text, lex):
    text, hits = _apply_entries(text, lex["phrases"] + lex["words"])
    return _cleanup(text), hits


_CONS = "بپتثجچحخدذرزژسشصضطظعغفقکگلمنی"
_PART = r"(?:شد|کرد|گرفت|داد|رفت|آمد|بود|دید|گفت|خورد|باخت|ساخت|نوشت|فروخت|خرید|گذاشت|افتاد|ماند)"


def pass_spoken(text, lex):
    """Written -> colloquial. Approximate on purpose: read the result."""
    text, hits = _apply_entries(text, lex.get("spoken", []))
    extra = [
        (r"(?<=\S) را(?=[\s،؛.!؟?]|$)", " رو", "را -> رو"),
        (r"(\b" + _PART + r"ه) است(?![\w‌])", r"\1", "شده است -> شده"),
        (r"([^\W\d_]*[" + _CONS + r"]) است(?![\w‌])", r"\1ه", "… است -> …ه"),
        (r"([^\W\d_]*[او]) است(?![\w‌])", r"\1ست", "… است -> …ست"),
    ]
    for pat, repl, name in extra:
        text, n = re.subn(pat, repl, text)
        if n:
            hits.append({"find": name, "replace": "محاوره‌ای", "count": n, "family": "spoken"})
    return _cleanup(text), hits


def scan_structures(text, lex):
    flags = []
    form = F.match_form(text)
    for s in lex["structures"]:
        try:
            pattern = re.compile(s["regex"], re.MULTILINE)
        except re.error:
            continue
        found = pattern.findall(form) or pattern.findall(text)
        if found:
            flags.append({"name": s["name"], "count": len(found), "fix": s["fix"], "id": s["id"]})
    lens = [len(F.words(s)) for s in F.sentences(text, min_words=3)]
    if len(lens) >= 4:
        mean = sum(lens) / len(lens)
        var = sum((n - mean) ** 2 for n in lens) / len(lens)
        cv = (var ** 0.5) / mean if mean else 0
        if cv < 0.35:
            flags.append({"id": "uniform-length", "name": f"طولِ جمله‌ها یکنواخته (تنوع {cv:.2f})",
                          "count": len(lens),
                          "fix": "یه جمله رو نصف کن. یکی دیگه رو بلند بذار. ماشین یکدست می‌نویسه."})
    reg_f, reg_s, n = F.register_counts(text)
    if n >= 12 and reg_f >= 3 and reg_f > reg_s:
        flags.append({"id": "register", "name": f"لحنِ کتابی (کتابی {reg_f:g} در برابر محاوره‌ای {reg_s:g})",
                      "count": int(reg_f),
                      "fix": "این متن رو کسی جلوی دوربین نمی‌گه. با --spoken محاوره‌ای‌اش کن و بعد بخونش."})
    return flags


def humanize(text, lex, spoken=False, persian_digits=False, persian_punct=False):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text, urls = protect_urls(text)
    text, spell = F.normalize_letters(text)
    text, inv = F.clean_invisible(text)
    text, typo = pass_typographic(text, lex)
    text, lexi = pass_lexical(text, lex)
    spoken_hits = []
    if spoken:
        text, spoken_hits = pass_spoken(text, lex)
    if persian_punct:
        text = F.persian_punctuation(text)
    if persian_digits:
        text = F.to_persian_digits(text)
    text = _cleanup(text)
    structures = scan_structures(text, lex)
    text = restore_urls(text, urls)
    return text.strip() + "\n", {
        "spelling": spell, "invisible": inv, "typographic": typo,
        "lexical": lexi, "spoken": spoken_hits, "structures": structures,
    }


def render_report(report, out=sys.stderr):
    V = F.V

    def head(title):
        print(f"\n{title}\n" + "-" * len(title), file=out)

    total = sum(h["count"] for k in ("invisible", "typographic", "lexical", "spoken") for h in report[k])
    head("HUMANIZE REPORT  |  گزارش")
    print(V(f"{total} ردپای ماشینی پاک شد، {len(report['structures'])} نشانه‌ی ساختاری برای بازنویسیِ دستی"),
          file=out)
    if report["spelling"]:
        head("0. SPELLING | املا")
        for h in report["spelling"]:
            print(f"  {h['count']:>3}x  " + V(h["name"]), file=out)
    if report["invisible"]:
        head("1. INVISIBLE CHARACTERS | کاراکترهای نامرئی")
        for h in report["invisible"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['action']}", file=out)
    if report["typographic"]:
        head("2. TYPOGRAPHY | تایپوگرافی")
        for h in report["typographic"]:
            print(f"  {h['count']:>3}x  " + V(f"{h['name']}  ->  {h['to']}"), file=out)
    if report["lexical"]:
        head("3. SLOP LEXICON | کلیشه‌ها")
        for h in report["lexical"]:
            print(f"  {h['count']:>3}x  " + V(f"{h['find']}  ->  {h['replace']}") + f"   [{h['family']}]", file=out)
    if report["spoken"]:
        head("4. SPOKEN | محاوره‌ای‌سازی (تقریبی، بخونش)")
        for h in report["spoken"]:
            print(f"  {h['count']:>3}x  " + V(f"{h['find']}  ->  {h['replace']}"), file=out)
    if report["structures"]:
        head("5. STRUCTURAL TELLS | خودکار اصلاح نمی‌شه، خودت بازنویسی کن")
        for h in report["structures"]:
            print(f"  {h['count']:>3}x  " + V(h["name"]) + "\n        " + V(h["fix"]), file=out)
    if not any(report.values()):
        head("CLEAN")
        print("  Nothing to strip.", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Strip the machine fingerprint out of a Persian draft.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("-o", "--out", help="write cleaned text here instead of stdout")
    ap.add_argument("--report", action="store_true", help="print what changed, to stderr")
    ap.add_argument("--json", action="store_true", help="emit {text, report} as JSON")
    ap.add_argument("--spoken", action="store_true", help="colloquialise written Persian (approximate)")
    ap.add_argument("--persian-digits", action="store_true", help="convert all digits to ۰-۹")
    ap.add_argument("--persian-punct", action="store_true", help="convert ? , ; after Persian letters to ؟ ، ؛")
    ap.add_argument("--visual", action="store_true", help="fix display in bidi-less terminals (report only)")
    ap.add_argument("--lexicon", default=LEX, help="path to slop.json")
    args = ap.parse_args()
    if args.visual:
        F.set_visual(True)

    raw = sys.stdin.read() if args.input == "-" else F.read_text(args.input)
    lex = load_lexicon(args.lexicon)
    clean, report = humanize(raw, lex, spoken=args.spoken, persian_digits=args.persian_digits,
                             persian_punct=args.persian_punct)

    if args.json:
        print(json.dumps({"text": clean, "report": report}, indent=2, ensure_ascii=False))
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(clean)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(clean)
    if args.report:
        render_report(report)


if __name__ == "__main__":
    main()
