#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hookscore.py - امتیازدهی به جمله‌ی اولِ ریل روی پنج ویژگی که هوک‌های خوب مشترک دارن،
و رتبه‌بندیِ چند هوک نسبت به هم.

Scores the first line of a Persian Reel on five properties, computed locally from
the text alone: LENGTH, SPECIFICITY, STAKES, FRONTLOAD, ADDRESS. A sixth thing,
REGISTER (written vs spoken Persian), is reported as a flag, not a score.

این چیه:  پنج heuristic محلی که روی خودِ متن اجرا می‌شن و ویژگی‌هایی رو می‌سنجن که هوک‌های
نگه‌دارنده‌ی مخاطب معمولاً دارن: جمله‌ای که زیر سه ثانیه گفته بشه، یه نشانه‌ی مشخص،
چیزی که روی خطه، حرفِ اصلی جلوی جمله، و یه نفر که مخاطب باشه.

این چی نیست:  پیش‌بینِ بازدید. نسخه‌ی انگلیسیِ این ابزار روی ۷۴ هوکِ واقعی تست شده
(AUC حدود ۰٫۸۳ برای جدا کردن هوکِ واقعی از هوکِ عمداً بد، و ۰٫۵۶ برای جدا کردنِ
موفق از ناموفقِ یک خالق، یعنی تقریباً شانسی). نسخه‌ی فارسی هنوز روی داده‌ی فارسی
کالیبره نشده؛ وزن‌ها و فهرست‌ها از روی همون منطق و دانشِ زبان ساخته شدن.
پس ازش برای گرفتنِ چیزهای واضح استفاده کن: سلام‌وعلیک، مقدمه، هوکِ بدون هیچ چیزِ مشخص،
و هوکی که گفتنش پنج ثانیه طول می‌کشه. اینکه کدوم از دو هوکِ معقول می‌ترکه رو
نمی‌تونه بگه؛ اون رو نمودار ماندگاری (retention) می‌گه.

Usage
  python3 hookscore.py hooks.txt              # یه هوک در هر خط، رتبه‌بندی‌شده
  python3 hookscore.py --hook "۱۸ میلیون تومن ضرر دادم، فقط به‌خاطر یه بند."
  python3 hookscore.py hooks.txt --json
  python3 hookscore.py hooks.txt --visual     # ترمینالِ ویندوز که فارسی رو وارونه نشون می‌ده
"""

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:                       # python -I does not add the script dir
    sys.path.insert(0, HERE)

import fatext as F                             # noqa: E402

F.ensure_utf8()

WPS = 2.3                                      # spoken Persian, ~138 words/minute
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")

# Words that put something on the line (match_form: no ZWNJ, yeh/kaf Persian).
STAKES = {
    "نکن", "نکنید", "نکنین", "نذار", "نذارید", "نزن", "نخر", "نگو", "هیچوقت", "هرگز", "هیچکس",
    "هیچی", "هیچ", "اشتباه", "اشتباهه", "اشتباهی", "ضرر", "باختم", "باخت", "ازدست", "سوخت", "سوزوندم",
    "دود", "آب", "گرون", "گرونتر", "مفت", "رایگان", "بیخود", "بیهوده", "الکی", "دروغ", "دروغه",
    "راز", "مخفی", "پنهان", "حقیقت", "واقعیت", "سوتی", "فاجعه", "خطر", "خطرناک", "هشدار",
    "ریسک", "پشیمون", "پشیمونی", "حیف", "حیفه", "نمیگه", "نمیگن", "نگفت", "نمیدونه", "بد",
    "بدترین", "بدتر", "مشکل", "شکست", "بازنده", "فریب", "کلاهبرداری", "تقلب", "تله", "دام",
    "ممنوع", "غیرقانونی", "اخراج", "ورشکست", "ورشکسته", "بیچاره", "نابود", "خراب", "گند",
    "فقط", "تنها", "اما", "ولی", "وگرنه", "مگه", "بدون", "قبل", "تا", "بجای", "الان", "هنوز",
    "دیگه", "همین", "قرار", "نبود", "نیست", "نیستی", "نمیشه", "نمیتونی", "نمیخرن", "نمیخره",
    "پس", "فرق", "حریف", "ترس", "بترسی", "بترس", "گران", "پول", "قیمت", "تومن", "تومان",
}

# Openers that spend the first second saying nothing (match_form).
WEAK_OPENERS = [
    "سلام", "درود", "خب", "خوب", "بله", "اوم", "امم", "ببخشید", "دوستان", "بچهها", "رفقا",
    "عزیزان", "امروز", "الان میخوام", "میخوام", "میخواستم", "راستش", "راستشو", "بذارید",
    "بذار ببینم", "یه سوال", "یک سوال", "آیا", "میدونستی", "میدونستید", "فکر کنم", "فکر میکنم",
    "توی این ویدیو", "تو این ویدیو", "در این ویدیو", "توی این ریل", "تو این ریل", "در این ریل",
    "امروز میخوام", "اینجا", "همونطور که", "همانطور که", "همونطور", "مثل که", "یه چیزی",
    "یکی از", "خیلی از", "خیلیها", "بعضیا", "بعضیها", "ما", "این", "یه", "یک", "من", "همه",
    "راستی", "اصلا", "اساسا", "بالاخره", "ببینید دوستان", "ببین دوست", "اگه تا حالا",
]

DEALBREAKERS = [
    (re.compile(r"^\s*(?:سلام|درود|وقت بخیر|صبح بخیر|شب بخیر|خسته نباشید)\b"),
     "سلام‌وعلیک. هیچ‌کس برای احوال‌پرسی اومده بیرونِ فید رو نیومده. بپر روی محتوا."),
    (re.compile(r"^\s*(?:اسکرول نکن|ادامه نده|نرو|نگذر|صبر کن)\b|\bاسکرول نکنید\b|\bاینجا بمون\b"),
     "«اسکرول نکن». اگه مجبور شدی التماس کنی، هنوز توجهش رو نگرفتی."),
    (re.compile(r"\b(?:توی|تو|در)\s+این\s+(?:ویدیو|ویدئو|ریل|کلیپ|پست)\b|\bامروز\s+میخوام\s+(?:بهتون|بهت)\s+(?:نشون|بگم|یاد)\b"
                r"|\bمیخوام\s+(?:بهتون|بهت)\s+(?:نشون|یاد)\b|\bبهتون\s+نشون\s+بدم\b"),
     "مقدمه‌ی ویدیو («توی این ویدیو…»). حذفش کن و با نتیجه شروع کن."),
    (re.compile(r"^\s*(?:دوستان(?: عزیز)?|بچهها|رفقا|عزیزان(?: من)?|فالوورای عزیز)\b"),
     "خطابِ کلی («دوستان»). اگه به همه بگی، به هیچ‌کس نگفتی؛ گروهِ مشخص رو صدا بزن."),
    (HASHTAG_RE,
     "هشتگ توی هوک. هشتگ ته کپشنه، اگه باشه."),
    (EMOJI_RE,
     "ایموجی توی هوک. روی صفحه یا جای کلمه‌ست یا ایموجی، نه هر دو."),
]


def clamp(n):
    return max(0.0, min(100.0, n))


def check_length(text):
    """باید قبل از حرکتِ شست برسه. حدود دو ثانیه. فارسی فعل‌آخره و ضمیر رو می‌اندازه،
    پس همون ایده با کلمه‌ی کمتر گفته می‌شه: بازه‌ی خوب ۴ تا ۱۱ کلمه‌ست."""
    n = len(F.words(text))
    secs = n / WPS
    chars = len(text.strip())
    if 4 <= n <= 11:
        score = 100.0
    elif n < 4:
        score = clamp(100 - (4 - n) * 22)
    else:
        score = clamp(100 - (n - 11) * 11)
    if chars > 55:
        score -= 12
    return clamp(score), f"{n} کلمه، {chars} نویسه، حدود {secs:.1f} ثانیه گفتاری (بازه‌ی خوب ۴ تا ۱۱ کلمه)"


def check_specificity(text):
    """یه چیزِ مشخص از سه چیزِ کلی بهتره. فارسی حرف بزرگ نداره، پس عدد، نام برند و
    @هندل و «نقل‌قول» و اسم‌های شناخته‌شده رو می‌شمریم."""
    m = F.concrete_markers(text)
    # «۱۸ میلیون» یک نشانه‌ست، نه دو تا: کلمه‌ی پولی که داخل عدد اومده دوباره شمرده نمی‌شه.
    joined = " ".join(m["nums"])
    m["spoken"] = [t for t in m["spoken"] if t not in joined]
    hits = sum(len(v) for v in m.values())
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = (m["nums"][:2] + m["latin"][:2] + m["handles"][:1] + m["names"][:2] + m["spoken"][:2])
    if not hits:
        return score, "نه عددی، نه اسمی، هیچ چیزِ قابل‌چک"
    return score, f"{hits} نشانه‌ی مشخص: " + "، ".join(found)


def check_stakes(text):
    """تنش، هزینه، نفی. چیزی که ممکنه بیننده از دست بده."""
    toks = F.match_tokens(text)
    markers = sorted({t for t in toks if t in STAKES})
    # neg verbs: «نمیـ…» / «نـ…» imperative negatives
    for t in toks:
        if re.fullmatch(r"نمی\w{2,}", t) and t not in markers:
            markers.append(t)
    if re.search(r"\d+\s*(?:میلیون|میلیارد|هزار|تومن|تومان|دلار|یورو)", F.match_form(text)) and "قیمت" not in markers:
        markers.append("قیمت")
    markers = [t for t in markers if t not in ("تومن", "تومان") or "قیمت" not in markers]
    n = len(set(markers))
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detail = f"{n} نشانه‌ی تنش" + (": " + "، ".join(list(dict.fromkeys(markers))[:4]) if markers else
                                    " - هیچ چیزی توی این جمله روی خط نیست")
    return clamp(score), detail


def _is_payload(tok, raw):
    return (tok in STAKES or tok in F.SPOKEN_NUMBERS or tok in F.MONEY_WORDS or tok in F.KNOWN_NAMES
            or bool(re.search(r"\d", tok)) or bool(re.search(r"[a-z]{3,}", tok))
            or (tok.startswith("@") and len(tok) > 2) or bool(re.fullmatch(r"ن?می\w{2,}", tok) and tok.startswith("نمی")))


def check_frontload(text):
    """کلمه‌ی جذاب نباید کلمه‌ی نهم باشه."""
    w = F.match_tokens(text)
    if not w:
        return 0.0, "خالی"
    pen = 0
    hit_opener = None
    first2 = " ".join(w[:2])
    first3 = " ".join(w[:3])
    for weak in WEAK_OPENERS:
        if w[0] == weak or first2 == weak or first3 == weak or first2.startswith(weak + " "):
            # «این/یه/یک/من/همه/ما» are weak only when nothing concrete follows soon
            if weak in ("این", "یه", "یک", "من", "همه", "ما", "یکی از", "خیلی از"):
                if any(_is_payload(t, t) for t in w[:3]):
                    continue
            pen, hit_opener = 30, weak
            break
    payload = next((i for i, t in enumerate(w) if _is_payload(t, t)), None)
    if payload is None:
        base, where = 30.0, "هیچ کلمه‌ی اصلی‌ای توی جمله نیست"
    elif payload <= 3:
        base, where = 100.0, f"کلمه‌ی اصلی: کلمه‌ی {payload + 1}"
    elif payload <= 6:
        base, where = 70.0, f"کلمه‌ی اصلی: کلمه‌ی {payload + 1}، می‌شه جلوتر بیاد"
    else:
        base, where = 40.0, f"کلمه‌ی اصلی: کلمه‌ی {payload + 1}، دیره"
    return clamp(base - pen), where + (f"؛ شروعِ ضعیف «{hit_opener}»" if hit_opener else "")


def check_address(text):
    """رو به یه نفر یا توی هوا؟"""
    w = F.match_tokens(text)
    if F.is_second_person(w):
        return 100.0, "با بیننده حرف می‌زنه"
    if w and w[0] in F.IMPERATIVES:
        return 90.0, f"شروع با فعل امر («{w[0]}»)"
    if F.is_first_person(w):
        return 70.0, "اول‌شخص، بیننده صدا زده نشده"
    return 35.0, "سوم‌شخص، کسی توی اتاق نیست"


CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]
LABELS = {"LENGTH": "طول", "SPECIFICITY": "مشخص‌بودن", "STAKES": "ریسک", "FRONTLOAD": "جلو-بودن",
          "ADDRESS": "خطاب"}


def register_flag(text):
    formal, spoken, n = F.register_counts(text)
    if n >= 4 and formal >= 2 and formal > spoken:
        return "لحنِ کتابی. این جمله رو کسی جلوی دوربین نمی‌گه؛ محاوره‌ای‌اش کن (--spoken توی humanize.py)."
    return None


def run(text):
    results = {
        "LENGTH": check_length(text),
        "SPECIFICITY": check_specificity(text),
        "STAKES": check_stakes(text),
        "FRONTLOAD": check_frontload(text),
        "ADDRESS": check_address(text),
    }
    form = F.match_form(text)
    flags = [msg for pattern, msg in DEALBREAKERS if pattern.search(form) or pattern.search(text)]
    reg = register_flag(text)
    if reg:
        flags.append(reg)
    scores = [results[c][0] for c in CHECKS]
    # ضعیف‌ترین ویژگی سقفِ هوک رو تعیین می‌کنه: یه ویژگیِ بد کافیه که شست بره.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render_one(text, results, overall, verdict, flags, out=sys.stdout):
    V = F.V
    print("\nHOOK SCORE  |  امتیازِ هوک", file=out)
    print("=" * 62, file=out)
    print("  " + V("«" + text.strip() + "»") + "\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {name:<12} {bar(score)} {score:5.1f}   {V(LABELS[name])}", file=out)
        print("  " + " " * 12 + " " + V(detail), file=out)
    print("-" * 62, file=out)
    print(f"  {'HOOK SCORE':<12} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    for f in flags:
        print("\n  DEALBREAKER  " + V(f), file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print("\n  " + V(f"ضعیف‌ترین ویژگی: {LABELS[weakest]} ({weakest}). همون رو درست کن و دوباره اجرا کن."), file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout):
    V = F.V
    print("\nHOOK RANKING  |  رتبه‌بندی هوک‌ها\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        print(f"{mark} {r['score']:5.1f} {r['verdict']:<7} " + V(hook), file=out)
        print(f"        weakest: {r['weakest']} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print("        dealbreaker: " + V(f), file=out)
    print("\n" + V("اولی رو بگیر. اگه اولی زیر ۵۰ بود، هیچ‌کدوم هوک نیست."), "\n", file=out)


def main():
    ap = argparse.ArgumentParser(description="Score a Persian Reel hook on five properties.")
    ap.add_argument("input", nargs="?", default="-", help="file with one hook per line, or -")
    ap.add_argument("--hook", help="score a single hook given on the command line")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--visual", action="store_true",
                    help="fix Persian display in terminals that don't do bidi (needs arabic-reshaper, python-bidi)")
    args = ap.parse_args()
    if args.visual:
        F.set_visual(True)

    if args.hook:
        lines = [args.hook]
    else:
        raw = sys.stdin.read() if args.input == "-" else F.read_text(args.input)
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        print("nothing to score", file=sys.stderr)
        sys.exit(2)

    payload = []
    for line in lines:
        results, overall, verdict, flags = run(line)
        payload.append({
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": min(CHECKS, key=lambda c: results[c][0]),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
        })

    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False))
        return

    if len(payload) == 1:
        results, overall, verdict, flags = run(lines[0])
        render_one(lines[0], results, overall, verdict, flags)
    else:
        render_table(sorted(payload, key=lambda r: -r["score"]))

    sys.exit(0 if max(p["score"] for p in payload) >= 70 else 1)


if __name__ == "__main__":
    main()
