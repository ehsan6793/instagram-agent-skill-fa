#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
caption.py - لینتِ کپشنِ اینستاگرام + نشان‌دادنِ دقیقِ چیزی که فید قبل از «... بیشتر» نشون می‌ده.

Lint a Persian Instagram caption and show the visible window before "... more".

اینستاگرام توی فید حدود ۱۲۵ نویسه از کپشن رو نشون می‌ده و بقیه پشتِ یه لمسه. اکثرِ کپشن‌های
شکست‌خورده همون‌جا می‌بازن: هوک توی جمله‌ی سومه، خطِ اول سلامه، یا کپشن با هشتگ شروع می‌شه.
این ابزار پنجره‌ی دیدنی رو توی یه کادر چاپ می‌کنه تا همون‌طور که یه غریبه‌ی در حالِ اسکرول می‌خونه،
بخونیش، بعد ده چکِ ارزشمند رو می‌زنه.

عددِ ۱۲۵ تقریبیه. عددِ واقعی با دستگاه، اندازه‌ی فونت و جای شکستِ خط عوض می‌شه، و خطِ فارسی (راست‌به‌چپ)
هم ممکنه کمی فرق کنه. پس حاشیه بذار؛ کپشن رو دقیقاً برای ۱۲۵ مهندسی نکن. با --truncate عوضش کن.

Usage
  python3 caption.py caption.txt
  python3 caption.py caption.txt --keywords "نرم‌افزار قرارداد,پیشنهاد قیمت"
  python3 caption.py caption.txt --json
  python3 caption.py caption.txt --visual     # ترمینالِ ویندوز که فارسی رو وارونه نشون می‌ده
"""

import argparse
import json
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fatext as F                            # noqa: E402

F.ensure_utf8()

LIMIT = 2200             # سقفِ سختِ کپشن.
TRUNCATE = 125           # تقریباً جایی که فید «... بیشتر» می‌ذاره.
HASHTAG_LIMIT = 5        # سقفِ هشتگ برای هر پست یا ریل. اینستاگرام ۱۸ دسامبر ۲۰۲۵ اعلام کرد و
                         # به‌تدریج اعمال می‌شه؛ قبلاً ۳۰ بود.

HASHTAG_RE = re.compile(r"(?:^|\s)(#[\w‌]+)")
MENTION_RE = re.compile(r"(?:^|\s)(@[A-Za-z0-9_.]+)")
LINK_RE = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|co|io|net|org|ai|app|ir|me)/\S*",
                     re.IGNORECASE)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿←-⇿️]")

# Asks, written against F.match_form (no ZWNJ, ASCII digits, Persian yeh/kaf).
ASKS = [
    (re.compile(r"\bکامنت\s+(?:کن|کنید|بذار|بذارید)\b[^.!؟?\n]{0,25}\b(?:کلمه|عبارت)?\s*[«\"]?\S+|\bزیر\s+(?:این\s+)?(?:پست|ریل)\s+(?:بنویس|بنویسید)\b"),
     "کامنتِ یک کلمه‌ی کلیدی"),
    (re.compile(r"\b(?:دایرکت|پیام|دایرکتم|پیوی)\s*(?:بده|بدید|بزن|بزنید|کن|کنید|بفرست|بفرستید)\b|\bبه\s+دایرکت\s+(?:بیا|بیاید)\b"),
     "دایرکت"),
    (re.compile(r"\b(?:ذخیره|سیو)(?:ش|اش|شون)?\s*(?:کن|کنید|کنین)\b|\bسیوش\s+کن\b"), "ذخیره"),
    (re.compile(r"\b(?:برای|واسه)\s+(?:یه|یک)\s+(?:دوست|نفر|رفیق|همکار)\s+(?:بفرست|بفرستید)\b|\bبفرست\s+(?:برای|واسه)\b|\bاشتراک\s*(?:بذار|بذارید)\b|\bشیر\s+کن\b"),
     "ارسال"),
    (re.compile(r"\b(?:فالو|دنبال)\s*(?:کن|کنید|کنین)\b|\bپیج\s+رو\s+دنبال\b"), "فالو"),
    (re.compile(r"\bلینک\s+(?:تو|توی|در)\s+بیو\b|\bلینک\s+بیو\b"), "لینک بیو"),
    (re.compile(r"\b(?:اسلاید|سوایپ)\s*(?:کن|کنید)\b|\bبکش\s+به\s+(?:چپ|راست)\b|\bبه\s+(?:چپ|راست)\s+بکش\b|\bاسلاید\s+(?:بعد|بعدی)\b"),
     "اسلاید"),
    (re.compile(r"\bبهم\s+بگو\b|\bبگو\s+(?:کدوم|چی|چرا|چطور)\b|\bکدوم\s+(?:یکی|رو)\b|\bنظرت\s+چیه\b"), "جواب‌دادن به سوال"),
]

FILLER_TAGS = {
    "#ایران", "#اینستاگرام", "#ریلز", "#ریل", "#پربازدید", "#ویدیو", "#وایرال", "#ایرانی", "#پیج_ایرانی",
    "#فالو", "#لایک", "#لایک_فالو", "#اکسپلور", "#اکسپلورر", "#پیشنهادی", "#ترند", "#دنبال_کن", "#فالوور",
    "#instagram", "#viral", "#fyp", "#explore", "#explorepage", "#foryou", "#trending", "#instagood",
    "#reels", "#reelsinstagram", "#follow", "#like4like", "#instadaily",
}
GREETINGS = ("سلام", "درود", "وقت بخیر", "صبح بخیر", "شب بخیر", "خسته نباشید", "روزتون بخیر", "عرض ادب")


def visible_window(text, cut):
    flat = text.strip()
    return flat if len(flat) <= cut else flat[:cut]


def render_box(window, truncated, out=sys.stdout, width=52):
    V = F.V
    print("\n  WHAT THE FEED SHOWS  |  چیزی که فید نشون می‌ده", file=out)
    print("  +" + "-" * (width + 2) + "+", file=out)
    lines = []
    for raw in window.split("\n"):
        lines.extend(textwrap.wrap(raw, width) or [""])
    for line in lines[:8]:
        shown = V(line)
        pad = " " * max(0, width - len(line))
        print(f"  | {shown}{pad} |", file=out)
    tail = "... more" if truncated else "(whole caption fits)"
    print("  +" + "-" * (width + 2 - len(tail) - 2) + f" {tail} " + "+", file=out)


def _spelling_notes(text):
    notes = []
    arabic = sum(text.count(c) for c in "يىك")
    if arabic:
        notes.append(f"{arabic} ي/ك عربی")
    fa_d = sum(1 for c in text if c in "۰۱۲۳۴۵۶۷۸۹")
    en_d = sum(1 for c in text if c in "0123456789")
    if fa_d and en_d:
        notes.append("رقمِ فارسی و لاتین قاطی")
    if re.search(r"(?<=[ء-غف-ي])\?", text):
        notes.append("علامتِ سوالِ لاتین (?) بعد از حرفِ فارسی، به‌جای ؟")
    stray = len(re.findall(r"‌(?!\w)|(?<!\w)‌|‌{2,}", text))
    if stray:
        notes.append(f"{stray} نیم‌فاصله‌ی ولگرد/تکراری")
    return notes


def analyse(text, cut=TRUNCATE, keywords=None):
    text = text.rstrip()
    stripped = text.strip()
    chars = len(stripped)
    lines = stripped.split("\n")
    first_line = lines[0].strip() if lines else ""
    tags = HASHTAG_RE.findall(stripped)
    mentions = MENTION_RE.findall(stripped)
    links = LINK_RE.findall(stripped)
    emoji = EMOJI_RE.findall(stripped)
    window = visible_window(stripped, cut)
    truncated = chars > cut
    form = F.match_form(stripped)
    asks = [name for pattern, name in ASKS if pattern.search(form)]
    filler = [t for t in tags if F.match_form(t) in {F.match_form(x) for x in FILLER_TAGS}]
    keywords = [k.strip() for k in (keywords or []) if k.strip()]
    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    add("LENGTH", "FAIL" if chars > LIMIT else "PASS",
        f"{chars} / {LIMIT} نویسه" + (f"، {chars - LIMIT} تا بیشتر از سقف" if chars > LIMIT else ""))

    fl_form = F.match_form(first_line)
    if not first_line:
        add("FIRST LINE", "FAIL", "کپشن با یه خطِ خالی شروع می‌شه")
    elif first_line.startswith("#") or first_line.startswith("@"):
        add("FIRST LINE", "FAIL", "با هشتگ یا منشن شروع می‌شه، توی تنها جایی که ارزشِ یه جمله رو داره")
    elif any(fl_form.startswith(F.match_form(g)) for g in GREETINGS):
        add("FIRST LINE", "WARN", "با سلام‌وعلیک شروع می‌شه. توی فید فقط ۱۲۵ نویسه داری؛ خرجِ احوال‌پرسی نکن")
    elif len(first_line) > cut:
        add("FIRST LINE", "WARN", f"{len(first_line)} نویسه، پس وسطِ فکر بریده می‌شه. اگه برش یه کلیف‌هنگره عیبی نداره، "
                                  "اگه وسطِ جمله‌ی پیرو باشه بده")
    else:
        add("FIRST LINE", "PASS", f"{len(first_line)} نویسه، کامل می‌رسه")

    cm = F.concrete_count(window)
    add("HOOK IS CONCRETE", "PASS" if cm else "WARN",
        f"{cm} عدد یا اسم توی پنجره‌ی دیدنی" + ("" if cm else " - قبل از لمس هیچ چیزِ قابل‌چکی نیست"))

    if len(tags) > HASHTAG_LIMIT:
        add("HASHTAGS", "FAIL", f"{len(tags)} هشتگ، بیشتر از سقفِ {HASHTAG_LIMIT} تای اینستاگرام. "
                                "هشتگ‌های بعد از پنجمی حساب نمی‌شن و بلوک قدیمی به نظر می‌رسه")
    elif len(tags) == HASHTAG_LIMIT and filler:
        add("HASHTAGS", "WARN", f"{len(tags)} هشتگ، روی سقف، و {len(filler)} تاش کلی‌ان. ۵ تا رو خرجِ موضوع کن")
    elif filler:
        add("HASHTAGS", "WARN", f"{len(tags)} هشتگ، {len(filler)} تاش کلی ({'، '.join(filler[:3])}). چیزی رو توصیف نمی‌کنن")
    else:
        add("HASHTAGS", "PASS", f"{len(tags)} هشتگ" + (": " + " ".join(tags) if tags else ""))

    if not tags:
        add("TAG PLACEMENT", "PASS", "هشتگی نیست که جاش مهم باشه")
    elif any(t in window for t in tags):
        add("TAG PLACEMENT", "WARN", "یه هشتگ توی پنجره‌ی دیدنیه و فضای فید رو خرجِ برچسب می‌کنه")
    else:
        add("TAG PLACEMENT", "PASS", "هشتگ‌ها زیرِ خطِ برش‌ان")

    add("LINKS", "WARN" if links else "PASS",
        (f"{len(links)} لینک توی کپشن، و لینکِ کپشن قابل‌کلیک نیست. بذارش توی بیو یا دایرکت"
         if links else "لینکِ مرده‌ای توی متن نیست"))

    if len(asks) == 1:
        add("ONE ASK", "PASS", f"یه درخواست: {asks[0]}")
    elif not asks:
        add("ONE ASK", "WARN", "هیچ درخواستی نیست. تصمیم بگیر این پست برای چیه")
    else:
        add("ONE ASK", "WARN", f"{len(asks)} درخواست ({'، '.join(asks)}). دو درخواست یعنی هیچ‌کدوم")

    density = len(emoji) * 100 / max(chars, 1)
    add("EMOJI", "WARN" if density > 4 else "PASS",
        f"{len(emoji)} ایموجی، {density:.1f} در هر ۱۰۰ نویسه" + (" - تزئینیه" if density > 4 else ""))

    formal, spoken, n = F.register_counts(stripped)
    if n >= 12 and formal >= 2 and formal > spoken:
        add("REGISTER", "WARN", f"لحنِ کتابی (کتابی {formal:g} در برابر محاوره‌ای {spoken:g}). "
                                "کپشن رو همون‌جوری بنویس که می‌گی (humanize.py --spoken)")
    else:
        add("REGISTER", "PASS", f"لحن: کتابی {formal:g}، محاوره‌ای {spoken:g}")

    notes = _spelling_notes(stripped)
    add("SPELLING", "WARN" if notes else "PASS", "؛ ".join(notes) if notes else "املا و رقم یکدسته")

    if keywords:
        low = form
        found = [k for k in keywords if F.match_form(k) in low]
        missing = [k for k in keywords if F.match_form(k) not in low]
        wform = F.match_form(window)
        in_window = [k for k in found if F.match_form(k) in wform]
        status = "PASS" if not missing else ("WARN" if found else "FAIL")
        add("SEARCH TERMS", status,
            f"{len(found)}/{len(keywords)} هست" + (f"، {len(in_window)} تاش توی پنجره‌ی دیدنی" if found else "")
            + (f". کم: {'، '.join(missing)}" if missing else ""))

    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    verdict = "FIX" if fails else ("REVIEW" if warns else "READY")
    return {
        "characters": chars, "limit": LIMIT, "truncate_at": cut, "visible": window, "truncated": truncated,
        "first_line_chars": len(first_line), "hashtags": tags, "mentions": mentions, "links": links,
        "emoji": len(emoji), "asks": asks, "checks": checks, "verdict": verdict,
    }


def render(a, out=sys.stdout):
    V = F.V
    head = (f"CAPTION LINT  |  {a['characters']} / {a['limit']} chars  |  "
            f"{len(a['hashtags'])} hashtags  |  {len(a['asks'])} ask(s)")
    print("\n" + head, file=out)
    print("=" * max(len(head), 62), file=out)
    render_box(a["visible"], a["truncated"], out=out)
    print("", file=out)
    for c in a["checks"]:
        print(f"  {c['status']:<5} {c['check']:<17} " + V(c["detail"]), file=out)
    print("-" * max(len(head), 62), file=out)
    print(f"  VERDICT  {a['verdict']}\n", file=out)


def main():
    ap = argparse.ArgumentParser(description="Lint a Persian Instagram caption.")
    ap.add_argument("input", nargs="?", default="-", help="caption file, or - for stdin")
    ap.add_argument("--truncate", type=int, default=TRUNCATE,
                    help=f"characters shown before '... more' (default {TRUNCATE})")
    ap.add_argument("--keywords", default="", help="comma-separated terms you want to be found for (، also works)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--visual", action="store_true", help="fix display in bidi-less terminals")
    args = ap.parse_args()
    if args.visual:
        F.set_visual(True)

    raw = sys.stdin.read() if args.input == "-" else F.read_text(args.input)
    kws = re.split(r"[,،]", args.keywords)
    a = analyse(raw, cut=args.truncate, keywords=kws)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0 if a["verdict"] == "READY" else 1)


if __name__ == "__main__":
    main()
