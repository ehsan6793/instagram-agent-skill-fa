#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beats.py - تبدیل اسکریپتِ ریل به beat sheet زمان‌دار، قبل از ضبط.

Estimates how long each line takes to say, stacks them into timecodes, and flags the
things that kill a Reel in the edit: a hook past the three-second mark, a beat long
enough for the viewer to leave, a run of lines with nothing concrete in them, a
total length that misses your target, and a last line that doesn't loop to the hook.

زمان‌ها تخمینن (تعداد کلمه ÷ سرعتِ گفتار). سرعتِ پیش‌فرض ۱۳۸ کلمه در دقیقه‌ست، که حدسِ
معقول برای فارسیِ محاوره‌ایه و کالیبره نشده. یه بار یه اسکریپت رو بلند و با تایمر بخون و
عددِ خودت رو بده:

    python3 beats.py script.txt --calibrate "۴۲ کلمه / ۲۸ ثانیه"   # سرعتِ خودت رو حساب می‌کنه
    python3 beats.py script.txt --wpm 150 --target 30

فارسیِ نوشتاری آهسته‌تر از محاوره‌ایه و آدم‌ها معمولاً بین ۱۲۰ تا ۱۶۰ کلمه در دقیقه‌ان.

Usage
  python3 beats.py script.txt
  python3 beats.py script.txt --target 30
  python3 beats.py script.txt --wpm 150 --target 45
  python3 beats.py script.txt --json
  python3 beats.py script.txt --visual     # ترمینالِ ویندوز که فارسی رو وارونه می‌ده
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fatext as F                                    # noqa: E402

F.ensure_utf8()

DEFAULT_WPM = 138
HOOK_WINDOW = 3.0        # ثانیه. بعدش شست تصمیمش رو گرفته.
MAX_BEAT = 4.0           # ثانیه روی یک ایده بدون تغییر روی صفحه.
ABSTRACT_RUN = 3         # چند بیتِ پشت‌سرهم بدون هیچ چیزِ قابل‌چک.


def tc(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def split_beats(raw, wps):
    """هر خط یک بیته، مگه اینکه خط اونقدر بلند باشه که نشه یه بیت حسابش کرد."""
    beats = []
    for line in [l.strip() for l in raw.splitlines()]:
        if not line or line.startswith("#"):
            continue
        if len(F.words(line)) / wps <= MAX_BEAT * 1.5:
            beats.append(line)
            continue
        parts = [p.strip() for p in F.SENT_RE.findall(line) if p.strip()]
        buf = ""
        for part in parts:
            candidate = (buf + " " + part).strip()
            if buf and len(F.words(candidate)) / wps > MAX_BEAT:
                beats.append(buf)
                buf = part
            else:
                buf = candidate
        if buf:
            beats.append(buf)
    return beats


def parse_calibration(s):
    """«۴۲ کلمه / ۲۸ ثانیه» یا «42/28» -> words per minute."""
    nums = re.findall(r"\d+(?:\.\d+)?", F.prep(s))
    if len(nums) < 2:
        raise ValueError("دو عدد لازمه: تعداد کلمه و ثانیه، مثلاً «42 / 28»")
    w, sec = float(nums[0]), float(nums[1])
    if sec <= 0:
        raise ValueError("ثانیه باید بیشتر از صفر باشه")
    return round(w / sec * 60, 1)


def _content_tokens(text):
    return [t for t in F.match_tokens(text) if t not in F.FA_STOPWORDS and len(t) > 1]


def analyse(raw, wpm=DEFAULT_WPM, target=None):
    wps = wpm / 60.0
    beats = split_beats(raw, wps)
    if not beats:
        return None

    rows, clock = [], 0.0
    for i, text in enumerate(beats):
        n = len(F.words(text))
        dur = n / wps
        rows.append({
            "n": i + 1, "start": round(clock, 2), "dur": round(dur, 2), "words": n,
            "text": text, "concrete": F.concrete_count(text), "label": "", "flags": [],
        })
        clock += dur
    total = clock

    for r in rows:
        if r["n"] == 1 or r["start"] + r["dur"] <= HOOK_WINDOW:
            r["label"] = "HOOK"
    rows[-1]["label"] = "CTA" if rows[-1]["label"] != "HOOK" else "HOOK/CTA"
    half = total / 2
    for r in rows:
        if not r["label"] and r["start"] <= half < r["start"] + r["dur"]:
            r["label"] = "MID"

    notes = []
    if rows[0]["dur"] > HOOK_WINDOW:
        rows[0]["flags"].append(f"هوک {rows[0]['dur']:.1f} ثانیه‌ست، بیشتر از {HOOK_WINDOW:.0f} ثانیه")
        notes.append(f"بیتِ ۱ گفتنش {rows[0]['dur']:.1f} ثانیه طول می‌کشه. به {int(HOOK_WINDOW * wps)} کلمه یا "
                     "کمتر برسونش، وگرنه هوک بعد از تصمیمِ بیننده می‌رسه.")
    if rows[0]["concrete"] == 0:
        notes.append("بیتِ ۱ نه عدد داره نه اسم. هوکِ بدون چیزِ قابل‌چک همونیه که اسکرول می‌شه.")

    for r in rows:
        if r["dur"] > MAX_BEAT:
            r["flags"].append(f"{r['dur']:.1f} ثانیه روی یک بیت")
    long_beats = [r["n"] for r in rows if r["dur"] > MAX_BEAT]
    if long_beats:
        notes.append(f"بیت(های) {'، '.join(map(str, long_beats))} از {MAX_BEAT:.0f} ثانیه بلندترن. "
                     "یا خط رو بشکن یا وسطش چیزی که روی صفحه‌ست رو عوض کن. فریمِ ثابت جاییه که آدم‌ها می‌رن.")

    run, start = 0, None
    for r in rows:
        if r["concrete"] == 0:
            run += 1
            start = start if start is not None else r["n"]
            if run == ABSTRACT_RUN:
                notes.append(f"بیت‌های {start} تا {r['n']} هیچ چیزِ مشخصی ندارن. توی یکی‌شون یه عدد، "
                             "اسم یا قیمت بذار.")
        else:
            run, start = 0, None

    first, last = _content_tokens(rows[0]["text"]), _content_tokens(rows[-1]["text"])
    loop = sorted({a for a in first for b in last if F.same_word(a, b)})
    if len(rows) > 1 and loop:
        notes.append(f"حلقه: بیتِ آخر کلمه‌ی «{'، '.join(loop[:3])}» رو از هوک تکرار می‌کنه. "
                     "دیدنِ دوم ریچِ مجانیه.")
    elif len(rows) > 1:
        notes.append("حلقه نداره. بیتِ آخر هیچ کلمه‌ای با هوک مشترک نداره و ویدیو صاف تموم می‌شه. "
                     "تکرارِ یه کلمه از بیتِ ۱ ارزون‌ترین راهِ برگشتِ بیننده‌ست.")

    if target:
        delta = total - target
        if abs(delta) <= target * 0.1:
            notes.append(f"طول روی هدفه ({total:.1f} ثانیه از {target:g}).")
        elif delta > 0:
            notes.append(f"{delta:.1f} ثانیه بیشتر از هدفه. حدود {int(delta * wps)} کلمه کم کن.")
        else:
            notes.append(f"{-delta:.1f} ثانیه کمتر از هدفه. یا {int(-delta * wps)} کلمه اضافه کن یا کوتاه "
                         "ضبطش کن. کوتاه معمولاً درسته.")

    return {"wpm": wpm, "target": target, "total_seconds": round(total, 2),
            "total_words": sum(r["words"] for r in rows), "beats": rows, "notes": notes}


def render(a, out=sys.stdout):
    V = F.V
    head = (f"BEAT SHEET  |  {a['total_words']} کلمه  |  ~{a['total_seconds']:.1f}s "
            f"at {a['wpm']:g} wpm" + (f"  |  target {a['target']:g}s" if a["target"] else ""))
    print("\n" + V(head), file=out)
    print("=" * 72, file=out)
    for r in a["beats"]:
        label = f"{r['label']:<8}" if r["label"] else " " * 8
        print(f"  {tc(r['start'])}  {r['dur']:4.1f}s  {label}" + V(r["text"]), file=out)
        for f in r["flags"]:
            print(f"  {'':>6}  {'':>5}  {'':<8}^ " + V(f), file=out)
    print("-" * 72, file=out)
    for n in a["notes"]:
        print("  - " + V(n), file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Time a Persian Reel script into a beat sheet.")
    ap.add_argument("input", nargs="?", default="-", help="script file, or - for stdin")
    ap.add_argument("--wpm", type=float, default=None, help=f"speaking rate (default {DEFAULT_WPM})")
    ap.add_argument("--calibrate", help="e.g. \"42 / 28\": words you read / seconds it took; sets --wpm")
    ap.add_argument("--target", type=float, help="target length in seconds")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--visual", action="store_true", help="fix Persian display in bidi-less terminals")
    args = ap.parse_args()
    if args.visual:
        F.set_visual(True)

    wpm = args.wpm or DEFAULT_WPM
    if args.calibrate:
        try:
            wpm = parse_calibration(args.calibrate)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)
        print(f"سرعتِ گفتارِ تو: {wpm:g} کلمه در دقیقه", file=sys.stderr)

    raw = sys.stdin.read() if args.input == "-" else F.read_text(args.input)
    a = analyse(raw, wpm=wpm, target=args.target)
    if not a:
        print("empty script", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0)


if __name__ == "__main__":
    main()
