#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
detect.py - پنلِ شش‌تاییِ «این متن چقدر ماشینی به نظر می‌رسه؟» برای فارسی.

Six local checks: BURSTINESS, SPECIFICITY, SLOP DENSITY, FINGERPRINT, VOICE and REGISTER.
Computed on your machine from the text alone. Nothing is uploaded.

چیه:  heuristicهای محلی روی چیزهایی که تشخیص‌دهنده‌های عمومی و گوشِ آدم‌ها بهشون حساسن: تنوعِ
طولِ جمله، مشخص‌بودن، واژگانِ کلیشه‌ای، اثرِ انگشتِ تایپوگرافی و کاراکترِ نامرئی، صدای اول/دوم‌شخص،
و مهم‌تر از همه برای فارسی: لحن (کتابی در برابر محاوره‌ای).

چی نیست:  GPTZero و امثالش. این ابزارها فارسی رو ضعیف می‌فهمن و ما به هیچ‌کدوم وصل نیستیم.
وزن‌ها و آستانه‌ها هنوز روی داده‌ی فارسی کالیبره نشدن (نسخه‌ی انگلیسیِ اصلی هم فقط یه تستِ کوچک داره).
فقط همین رو می‌شه ادعا کرد: چیزهایی رو می‌گیره که بیشترِ متن‌های ماشینی دارن؛ رفعشون متن رو بهتر
می‌کنه، ولی تضمینِ عبور از هیچ ابزار خارجی نیست.

هر چک ۰ تا ۱۰۰ می‌ده، «انسانی»‌تر = بالاتر.

--register spoken   (پیش‌فرض) متن قراره گفته یا محاوره‌ای نوشته بشه: ریل، کامنت، دایرکت، استوری.
--register written  لحنِ کتابی ایرادی نداره (پست بلند، مقاله): چکِ REGISTER حذف می‌شه.

Usage
  python3 detect.py draft.txt
  python3 detect.py draft.txt --register written
  python3 detect.py before.txt after.txt     # مقایسه‌ی دو نسخه
  python3 detect.py draft.txt --json
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

LEX = os.path.join(HERE, "slop.json")


def clamp(n):
    return max(0.0, min(100.0, n))


def scale(value, human, machine):
    """Map value onto 0-100 where `human` -> 100 and `machine` -> 0."""
    if human == machine:
        return 50.0
    return clamp((value - machine) / (human - machine) * 100)


def check_burstiness(text):
    """آدم‌ها طولِ جمله رو شدید عوض می‌کنن. ماشین یکدست می‌نویسه."""
    lens = [len(F.words(s)) for s in F.sentences(text, min_words=3)]
    if len(lens) < 4:
        return 50.0, "برای قضاوت خیلی کوتاهه"
    mean = statistics.mean(lens)
    cv = statistics.pstdev(lens) / mean if mean else 0
    return scale(cv, human=0.60, machine=0.20), f"تنوع {cv:.2f} روی {len(lens)} جمله (می‌خوایم ۰٫۵ به بالا)"


def check_specificity(text):
    """عدد، اسم، @هندل، «نقل‌قول». کلیشه انتزاعیه."""
    n = len(F.words(text))
    if n < 25:
        return 50.0, "برای قضاوت خیلی کوتاهه"
    hits = F.concrete_count(text)
    density = hits * 100 / n
    return scale(density, human=6.0, machine=0.5), f"{hits} نشانه‌ی مشخص، {density:.1f} در هر ۱۰۰ کلمه (می‌خوایم ۴ به بالا)"


def _slop_hits(text, lex):
    hits, found = 0, []
    for entry in lex["words"] + lex["phrases"]:
        n = len(F.phrase_regex(entry["find"]).findall(text))
        if n:
            hits += n
            found.append(entry["find"])
    return hits, found


def check_slop(text, lex):
    n = len(F.words(text))
    if not n:
        return 50.0, "خالی"
    hits, found = _slop_hits(text, lex)
    density = hits * 100 / n
    detail = f"{hits} عبارتِ کلیشه‌ای، {density:.1f} در هر ۱۰۰ کلمه"
    if found:
        detail += " (" + "، ".join(sorted(found)[:4]) + ("، ..." if len(found) > 4 else "") + ")"
    return scale(density, human=0.0, machine=4.0), detail


def check_fingerprint(text):
    """کاراکترهایی که کیبوردِ گوشی تولید نمی‌کنه. نیم‌فاصله‌ی درست و ZWJ ایموجی شمرده نمی‌شن."""
    _, hits = F.clean_invisible(text)
    invisible = sum(h["count"] for h in hits if h["action"] == "delete")
    spaces = sum(h["count"] for h in hits if h["action"] == "space")
    em = text.count("—")
    curly = sum(text.count(c) for c in "‘’“”")
    ellip = text.count("…")
    mix = sum(text.count(c) for c in "يىك")        # Arabic yeh/kaf: copy-paste from elsewhere
    total = invisible * 4 + em * 2 + curly + ellip + spaces + mix * 0.5
    per1k = total * 1000 / max(len(text), 1)
    detail = (f"{invisible} نامرئی، {em} خط‌تیره‌ی بلند، {curly} گیومه‌ی فرنگی، "
              f"{ellip} سه‌نقطه‌ی یونیکد، {spaces} فاصله‌ی عجیب، {mix} ي/ك عربی")
    return scale(per1k, human=0.0, machine=12.0), detail


def check_voice(text, lex):
    """صدای اول/دوم‌شخص و ساختارهای پیش‌فرضِ مدل. فارسی ضمیر رو می‌اندازه، پس مقیاس پایین‌تره."""
    n = len(F.words(text))
    if n < 25:
        return 50.0, "برای قضاوت خیلی کوتاهه"
    person = F.person_density(text)
    form = F.match_form(text)
    tells, names = 0, []
    for s in lex["structures"]:
        try:
            k = len(re.compile(s["regex"], re.MULTILINE).findall(form))
        except re.error:
            continue
        if k:
            tells += k
            names.append(s["id"])
    bullets = [len(F.words(b)) for b in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", text)]
    uniform = len(bullets) >= 3 and statistics.pstdev(bullets) < 1.6
    score = scale(person, human=6.0, machine=0.5) * 0.55 + clamp(100 - tells * 22) * 0.45
    if uniform:
        score -= 12
        names.append("uniform-bullets")
    detail = f"{person:.1f} نشانه‌ی من/تو در هر ۱۰۰ کلمه، {tells} ساختارِ ماشینی"
    if names:
        detail += " [" + "، ".join(names[:4]) + "]"
    return clamp(score), detail


def check_register(text):
    """کتابی یا محاوره‌ای؟ بزرگ‌ترین نشونه‌ی فارسیِ ماشینی."""
    formal, spoken, n = F.register_counts(text)
    if n < 12:
        return 50.0, "برای قضاوت خیلی کوتاهه"
    net = (spoken - formal) * 100 / n          # >0 spoken, <0 formal
    return (scale(net, human=2.5, machine=-2.5),
            f"محاوره‌ای {spoken:g}، کتابی {formal:g} در {n} کلمه (می‌خوایم محاوره‌ای ≥ کتابی)")


BASE_CHECKS = ["BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"]
LABELS = {"BURSTINESS": "تنوعِ جمله", "SPECIFICITY": "مشخص‌بودن", "SLOP DENSITY": "کلیشه",
          "FINGERPRINT": "اثرِ انگشت", "VOICE": "صدا", "REGISTER": "لحن"}


def checks_for(register):
    return BASE_CHECKS + (["REGISTER"] if register != "written" else [])


def run(text, lex, register="spoken"):
    results = {
        "BURSTINESS": check_burstiness(text),
        "SPECIFICITY": check_specificity(text),
        "SLOP DENSITY": check_slop(text, lex),
        "FINGERPRINT": check_fingerprint(text),
        "VOICE": check_voice(text, lex),
    }
    if register != "written":
        results["REGISTER"] = check_register(text)
    checks = checks_for(register)
    scores = [results[c][0] for c in checks]
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4
    verdict = "PASS" if overall >= 70 and min(scores) >= 55 else ("REVIEW" if overall >= 50 else "FLAGGED")
    return results, overall, verdict


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render(results, overall, verdict, register, label=None, out=sys.stdout):
    V = F.V
    checks = checks_for(register)
    title = "AI DETECTION PANEL | پنل" + (f"  -  {label}" if label else "")
    print("\n" + title, file=out)
    print("=" * max(len(title), 66), file=out)
    for name in checks:
        score, detail = results[name]
        print(f"  {name:<13} {bar(score)} {score:5.1f}   " + V(LABELS[name]), file=out)
        print(f"  {'':<13} " + V(detail), file=out)
    print("-" * 66, file=out)
    print(f"  {'HUMAN SCORE':<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    if verdict != "PASS":
        weakest = min(checks, key=lambda c: results[c][0])
        print("\n  " + V(f"ضعیف‌ترین سیگنال: {LABELS[weakest]} ({weakest}). اول همون رو درست کن."), file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Score how machine-written a Persian draft looks.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("compare", nargs="?", help="second file, to show before/after")
    ap.add_argument("--register", choices=["spoken", "written"], default="spoken",
                    help="spoken (default): reels, comments, DMs. written: long-form, skip the register check")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--visual", action="store_true", help="fix display in bidi-less terminals")
    ap.add_argument("--lexicon", default=LEX)
    args = ap.parse_args()
    if args.visual:
        F.set_visual(True)

    with open(args.lexicon, encoding="utf-8") as fh:
        lex = json.load(fh)

    def read(p):
        return sys.stdin.read() if p == "-" else F.read_text(p)

    targets = [(args.input, read(args.input))]
    if args.compare:
        targets.append((args.compare, read(args.compare)))

    payload, raw = [], []
    for name, text in targets:
        results, overall, verdict = run(text, lex, args.register)
        raw.append((results, overall, verdict))
        payload.append({
            "source": name,
            "register": args.register,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "human_score": round(overall, 1),
            "verdict": verdict,
        })

    if args.json:
        print(json.dumps(payload if args.compare else payload[0], indent=2, ensure_ascii=False))
        return

    for (name, _), (results, overall, verdict) in zip(targets, raw):
        render(results, overall, verdict, args.register,
               label=os.path.basename(name) if args.compare else None)
    if args.compare:
        a, b = payload
        delta = b["human_score"] - a["human_score"]
        print(f"  {a['human_score']:.1f} {a['verdict']}  ->  {b['human_score']:.1f} {b['verdict']}   ({delta:+.1f})\n")

    sys.exit(0 if payload[-1]["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
