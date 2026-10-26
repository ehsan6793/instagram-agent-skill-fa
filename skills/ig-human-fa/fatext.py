#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fatext.py - shared Persian (Farsi) text helpers for the instagram-agent-skill-fa
pack. Every script imports this file from its own folder, so a skill folder can
be copied on its own. The canonical copy lives in skills/ig-reel-fa/ and
tools/sync_fatext.py copies it to the others (a test checks they are identical).

Why a shared module exists at all: the English tools assume Latin letters,
capital letters, apostrophe contractions and "delete every invisible
character". All four assumptions break on Persian.

  * ZWNJ (U+200C, "half-space" / نیم‌فاصله) is not an invisible watermark in
    Persian, it is part of the spelling: می‌روم, کتاب‌ها, ChatGPT‌ام. A tool
    that deletes it ruins the text. Here it is kept when it sits between two
    letters and removed only when it is stray.
  * ZWJ (U+200D) holds emoji sequences together. It is kept next to emoji.
  * LRM / RLM are kept on lines that mix Persian and Latin, where they may be
    doing a job, and removed elsewhere.
  * Persian has no capital letters, so "proper noun" detection needs another
    route: numbers, Latin brand names, @handles, quoted terms and a small
    editable list of well-known names.
  * Digits come as ASCII, Persian (۰-۹) or Arabic-Indic (٠-٩), with Arabic
    thousands separators. All of them are folded to ASCII before any counting.
  * Windows consoles default to a code page that cannot print Persian, so the
    scripts call ensure_utf8() first.

Nothing here touches the network.
"""

import re
import sys
import unicodedata

ZWNJ = "‌"
ZWJ = "‍"

# --------------------------------------------------------------------- io


def ensure_utf8():
    """Make stdin/stdout/stderr UTF-8 (Windows consoles are not by default)."""
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_text(path):
    """Read a file or stdin. utf-8-sig strips the BOM Windows Notepad adds."""
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


# ------------------------------------------------- terminal display (optional)

_VISUAL = False


def set_visual(on=True):
    """Optional: shape and reorder Persian for terminals with no bidi support.

    Needs `pip install arabic-reshaper python-bidi`. Without them the flag is
    ignored with a note. The Claude desktop app and web UI do not need it.
    """
    global _VISUAL
    _VISUAL = bool(on)
    if _VISUAL:
        try:
            import arabic_reshaper  # noqa: F401
            _display()  # noqa
        except Exception:
            print("note: --visual needs  pip install arabic-reshaper python-bidi",
                  file=sys.stderr)
            _VISUAL = False


def _display():
    try:
        from bidi.algorithm import get_display
    except Exception:  # newer python-bidi
        from bidi import get_display
    return get_display


def V(s):
    """Return s, shaped for a non-bidi terminal when --visual is on."""
    if not _VISUAL or not has_fa(s):
        return s
    import arabic_reshaper
    return _display()(arabic_reshaper.reshape(s))


# ------------------------------------------------------------- characters

FA_RE = re.compile("[ء-غف-يٮ-ۓەۺ-ۿ]")
LATIN_RE = re.compile(r"[A-Za-z]")

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_TO_ASCII = {ord(c): str(i) for i, c in enumerate(_PERSIAN_DIGITS)}
_TO_ASCII.update({ord(c): str(i) for i, c in enumerate(_ARABIC_DIGITS)})
_TO_PERSIAN = {ord(str(i)): c for i, c in enumerate(_PERSIAN_DIGITS)}
_ARABIC_TO_PERSIAN_DIGITS = {ord(c): _PERSIAN_DIGITS[i] for i, c in enumerate(_ARABIC_DIGITS)}
_LETTER_FIX = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"})


def is_fa_letter(ch):
    return bool(ch) and bool(FA_RE.match(ch))


def has_fa(s):
    return bool(FA_RE.search(s))


def to_ascii_digits(s):
    return s.translate(_TO_ASCII)


def to_persian_digits(s):
    return s.translate(_TO_PERSIAN)


def _emojiish(ch):
    if not ch:
        return False
    o = ord(ch)
    return (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF
            or 0x2190 <= o <= 0x21FF or o in (0xFE0F, 0x2640, 0x2642, 0x2695, 0x2696,
                                              0x2708, 0x2764, 0x203C, 0x2049))


# --------------------------------------------------------- tidy: letters

def normalize_letters(text):
    """Arabic yeh/kaf -> Persian, Arabic-Indic digits -> Persian, drop kashida.

    This is spelling hygiene, not a machine-fingerprint fix. Returns
    (text, hits).
    """
    hits = []
    yeh = sum(text.count(c) for c in "يى")
    kaf = text.count("ك")
    dig = sum(text.count(c) for c in _ARABIC_DIGITS)
    tat = text.count("ـ")
    if yeh:
        hits.append({"name": "ي/ى (Arabic yeh) -> ی", "count": yeh})
    if kaf:
        hits.append({"name": "ك (Arabic kaf) -> ک", "count": kaf})
    if dig:
        hits.append({"name": "٠-٩ (Arabic-Indic digits) -> ۰-۹", "count": dig})
    if tat:
        hits.append({"name": "ـ (kashida) removed", "count": tat})
    text = text.translate(_LETTER_FIX).translate(_ARABIC_TO_PERSIAN_DIGITS)
    text = text.replace("ـ", "")
    return text, hits


def persian_punctuation(text):
    """Latin ? , ; after a Persian letter -> ؟ ، ؛  (opt-in, spelling only)."""
    text = re.sub(r"(?<=[ء-غف-يٮ-ۓەۺ-ۿ])\?", "؟", text)
    text = re.sub(r"(?<=[ء-غف-يٮ-ۓەۺ-ۿ]),", "،", text)
    text = re.sub(r"(?<=[ء-غف-يٮ-ۓەۺ-ۿ]);", "؛", text)
    return text


# ----------------------------------------------------- invisible characters

def clean_invisible(text):
    """Remove machine-fingerprint characters, KEEP the ones Persian needs.

    Returns (text, hits). Each hit: {"name", "count", "action"}.
    Kept on purpose:
      ZWNJ between two letters (also Latin/digit + Persian, as in PDF‌ها)
      ZWJ between emoji
      LRM / RLM / ALM on lines that mix Persian and Latin letters
    Everything else in category Cf is deleted, and exotic spaces become " ".
    """
    counts = {}

    def note(name, action):
        key = (name, action)
        counts[key] = counts.get(key, 0) + 1

    out_lines = []
    for line in text.split("\n"):
        dup = len(re.findall(ZWNJ + "{2,}", line))
        if dup:
            line = re.sub(ZWNJ + "{2,}", ZWNJ, line)
            for _ in range(dup):
                note("U+200C duplicate ZWNJ", "delete")
        mixed = has_fa(line) and bool(LATIN_RE.search(line))
        chars = list(line)
        buf = []
        for i, ch in enumerate(chars):
            prev = buf[-1] if buf else ""
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            cat = unicodedata.category(ch)
            if ch == ZWNJ:
                if is_fa_letter(nxt) and (is_fa_letter(prev) or prev.isalnum()):
                    buf.append(ch)
                else:
                    note("U+200C stray ZWNJ (not between letters)", "delete")
                continue
            if ch == ZWJ:
                if _emojiish(prev) and _emojiish(nxt):
                    buf.append(ch)
                else:
                    note("U+200D ZERO WIDTH JOINER (outside an emoji)", "delete")
                continue
            if ch in ("‎", "‏", "؜"):
                if mixed:
                    buf.append(ch)
                else:
                    note("U+%04X %s" % (ord(ch), unicodedata.name(ch, "BIDI MARK")), "delete")
                continue
            if cat == "Cf":
                note("U+%04X %s" % (ord(ch), unicodedata.name(ch, "FORMAT CHARACTER")), "delete")
                continue
            if 0xE0000 <= ord(ch) <= 0xE007F:
                note("TAG CHARACTER (invisible ASCII smuggling)", "delete")
                continue
            if cat == "Zs" and ch != " ":
                note("U+%04X %s" % (ord(ch), unicodedata.name(ch, "SPACE")), "space")
                buf.append(" ")
                continue
            buf.append(ch)
        out_lines.append("".join(buf))
    hits = [{"name": k[0], "count": v, "action": k[1]} for k, v in sorted(counts.items())]
    return "\n".join(out_lines), hits


# --------------------------------------------------------------- tokenising

_THOUSANDS_RE = re.compile(r"(?<=\d)[,٬،](?=\d{3}(?!\d))")
WORD_RE = re.compile(r"[\w‌]+(?:['’\-][\w‌]+)*")


def prep(text):
    """ASCII digits, no thousands separators. Keeps everything else."""
    t = to_ascii_digits(text).replace("٫", ".")
    return _THOUSANDS_RE.sub("", t)


def words(text):
    """Spoken words. A ZWNJ-joined compound (می‌روم) is one word, as it is said."""
    return WORD_RE.findall(prep(text))


def match_form(text):
    """Canonical form for regex matching and set lookups.

    ASCII digits, no ZWNJ, Persian yeh/kaf, no diacritics, "می کنم" -> "میکنم",
    "کتاب ها" -> "کتابها", lower-case Latin, single spaces. Write every regex
    and word list in this form (so: no half-spaces in patterns).
    """
    t = prep(text).translate(_LETTER_FIX).replace("ـ", "")
    t = re.sub(r"[ً-ٰٟ]", "", t)
    t = t.replace(ZWNJ, "")
    t = re.sub(r"\b(ن?می) (?=[^\W\d_])", r"\1", t)
    t = re.sub(r"(?<=\S) (ها|های|هایی|تر|ترین)\b", r"\1", t)
    t = t.replace("هیچ کس", "هیچکس").replace("هیچ وقت", "هیچوقت")
    return re.sub(r"\s+", " ", t).strip().lower()


def match_tokens(text):
    return WORD_RE.findall(match_form(text))


def phrase_regex(find, flags=re.IGNORECASE):
    """Regex for a lexicon entry written WITH half-spaces, tolerant of spelling.

    ZWNJ in the entry matches ZWNJ, nothing, or a space; ی and ک match their
    Arabic variants; spaces match any run of spaces/ZWNJ. Word-bounded.
    """
    parts = []
    for ch in find:
        if ch == ZWNJ:
            parts.append("[‌ ]?")
        elif ch == " ":
            parts.append("[ ‌]+")
        elif ch == "ی":
            parts.append("[یيى]")
        elif ch == "ک":
            parts.append("[کك]")
        else:
            parts.append(re.escape(ch))
    return re.compile(r"(?<![\w‌])" + "".join(parts) + r"(?![\w‌])", flags)


SENT_RE = re.compile(r"[^.!؟?\n…]+[.!؟?…]*")


def sentences(text, min_words=3):
    return [s.strip() for s in SENT_RE.findall(text) if len(s.split()) >= min_words]


# -------------------------------------------------------------- concreteness

NUMBER_RE = re.compile(
    r"\d+(?:\.\d+)?\s?(?:%|٪|k\b|x\b|هزار|میلیون|میلیارد|درصد|برابر|تومان|تومن|دلار|یورو"
    r"|ساعت|دقیقه|ثانیه|روز|هفته|ماه|سال)?", re.IGNORECASE)
HANDLE_RE = re.compile(r"@[\w.]{2,}")
QUOTED_RE = re.compile(r"«[^»]{2,40}»|\"[^\"\n]{2,40}\"")
LATIN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+#.\-]{2,}\b")
LATIN_SKIP = {"the", "and", "for", "you", "not", "okay", "yes", "vs", "www", "com", "http", "https"}

SPOKEN_NUMBERS = {
    "صفر", "دو", "سه", "چهار", "پنج", "شش", "شیش", "هفت", "هشت", "ده", "یازده", "دوازده",
    "سیزده", "چهارده", "پونزده", "پانزده", "شونزده", "شانزده", "هفده", "هجده", "نوزده",
    "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود", "صد", "دویست", "سیصد",
    "چهارصد", "پونصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد", "هزار", "میلیون",
    "میلیارد", "ملیون", "ملیارد", "تریلیون", "نیم", "نصف", "دوبرابر", "سهبرابر",
    "چندبرابر", "هزارتومن", "میلیونی", "میلیاردی",
}
# "یک"/"یه" and "نه" are left out on purpose: filler and "no" far more often
# than a quantity.

MONEY_WORDS = {
    "تومان", "تومن", "ریال", "دلار", "یورو", "درصد", "سود", "فروش", "درآمد", "حقوق", "اجاره",
    "بدهی", "قرض", "جریمه", "مالیات", "بودجه", "هزینه", "قیمت", "پول", "میلیونر", "میلیاردر",
    "ضرر", "وام", "قسط", "سرمایه",
}

# An editable seed list. Persian has no capital letters, so a name has to be
# known to be noticed. Add the cities, brands and people your niche talks about.
_KNOWN_NAMES_RAW = [
    "تهران", "مشهد", "اصفهان", "شیراز", "تبریز", "کرج", "قم", "اهواز", "رشت", "کرمان", "یزد",
    "ارومیه", "همدان", "اراک", "بندرعباس", "زاهدان", "ساری", "گرگان", "قزوین", "سنندج",
    "کرمانشاه", "بوشهر", "کیش", "قشم",
    "دیجی‌کالا", "اسنپ", "دیوار", "تپسی", "ترب", "باسلام", "بانک ملی", "بانک ملت",
    "بانک صادرات", "پاسارگاد", "ایرانسل", "همراه‌اول", "رایتل", "آپارات", "روبیکا", "ایتا",
    "بله", "تلگرام", "واتساپ", "اینستاگرام", "یوتیوب", "گوگل", "دیجی‌کالا", "ایران‌خودرو",
    "سایپا", "ایران", "ایرانی",
]
KNOWN_NAMES = {match_form(n) for n in _KNOWN_NAMES_RAW} - {"بله"}


def concrete_markers(text):
    """Everything checkable in a line: numbers, Latin names, handles, quotes,
    known names, spoken numbers and money words."""
    prepped = prep(text)
    nums = [n.strip() for n in NUMBER_RE.findall(prepped) if n.strip()]
    handles = HANDLE_RE.findall(prepped)
    quoted = QUOTED_RE.findall(text)
    latin = [w for w in LATIN_WORD_RE.findall(prepped)
             if w.lower() not in LATIN_SKIP and not w.startswith("@")]
    toks = match_tokens(text)
    names = [t for t in toks if t in KNOWN_NAMES]
    spoken = [t for t in toks if t in SPOKEN_NUMBERS or t in MONEY_WORDS]
    return {"nums": nums, "handles": handles, "quoted": quoted, "latin": latin,
            "names": names, "spoken": spoken}


def concrete_count(text):
    m = concrete_markers(text)
    return sum(len(v) for v in m.values())


# ------------------------------------------------------------------ register
# The biggest tell in machine-written Persian is not a word, it is the
# register: written (کتابی) prose where a person on camera would speak
# (محاوره‌ای). These lists measure it. Entries are in match_form (no ZWNJ).

FORMAL_WEIGHTS = {
    "میباشد": 1, "میباشند": 1, "نمیباشد": 1, "گردید": 1, "گردیدند": 1, "نمودن": 1,
    "نمایید": 1, "نمایند": 1, "جهت": 1, "لذا": 1, "بنابراین": 1, "همچنین": 1, "زیرا": 1,
    "چراکه": 1, "چنانچه": 1, "هرگاه": 1, "بدینوسیله": 1, "درخصوص": 1, "پیرامون": 1,
    "اینجانب": 1, "ایشان": 1, "آنان": 1, "آنچه": 1, "اکنون": 1, "هماکنون": 1, "بسیار": 1,
    "نیز": 1, "لیکن": 1, "بدینترتیب": 1, "درنتیجه": 1, "درنهایت": 1, "علاوهبراین": 1,
    "افزونبراین": 1, "مجددا": 1, "هرچند": 1, "چنین": 1, "بایستی": 1, "میبایست": 1,
    "اما": 0.5, "را": 0.3, "آن": 0.3, "است": 0.5, "آنها": 0.4, "آنجا": 0.4, "او": 0.4,
}
_FORMAL_VERB = re.compile(r"^ن?می(?:خواه|توان|دان)(?:م|ی|د|یم|ید|ند)$|^(?:خواه)(?:م|ی|د|یم|ید|ند)$")

SPOKEN_WEIGHTS = {
    "رو": 1, "یه": 1, "یکم": 1, "یهو": 1, "اینجوری": 1, "اونجوری": 1, "چجوری": 1,
    "چطوری": 1, "واسه": 1, "برا": 1, "برام": 1, "برات": 1, "براتون": 1, "برامون": 1,
    "بهت": 1, "بهم": 1, "بهتون": 1, "ازت": 1, "ازم": 1, "ازتون": 1, "اونا": 1, "اینا": 1,
    "اون": 0.7, "دیگه": 0.5, "ولی": 0.5, "خیلی": 0.3, "نمیشه": 1, "میشه": 1, "بریم": 1,
    "اینو": 1, "اونو": 1, "همینو": 1, "کلی": 0.7, "یعنی": 0.4, "واقعا": 0.3, "راستش": 0.7,
}
_SPOKEN_VERB = re.compile(r"^ن?می(?:خوا|تون|دون|گ|ش|ر|د|ذار)(?:م|ی|ه|یم|ید|ین|ن)$")


def register_counts(text):
    """(formal_weight, spoken_weight, n_words) for a text."""
    toks = match_tokens(text)
    formal = spoken = 0.0
    for t in toks:
        formal += FORMAL_WEIGHTS.get(t, 0)
        spoken += SPOKEN_WEIGHTS.get(t, 0)
        if _FORMAL_VERB.match(t):
            formal += 1
        if _SPOKEN_VERB.match(t):
            spoken += 1
    return formal, spoken, len(toks)


# ----------------------------------------------------------- person / address

SECOND_PERSON = {
    "تو", "شما", "خودت", "خودتون", "خودتان", "شمایی", "توئی", "برات", "براتون", "بهت",
    "بهتون", "ازت", "ازتون", "باهات", "باهاتون", "برایت", "برایتان", "بهتان", "ازتان",
    "داری", "دارید", "دارین", "هستی", "هستید", "هستین", "بودی", "بودید", "کردی", "کردید",
    "ببین", "ببینید", "بدون", "بدونید", "بشنو", "میدونی", "میدونید", "ندونی",
}
FIRST_PERSON = {
    "من", "ما", "منو", "خودم", "خودمون", "برام", "برامون", "بهم", "بهمون", "ازم", "ازمون",
    "باهام", "دارم", "بودم", "داشتم", "بودیم", "داشتیم",
}
_PAST_1SG = ("کردم", "شدم", "دادم", "گرفتم", "خوردم", "باختم", "دیدم", "گفتم", "رفتم", "ساختم",
             "فروختم", "خریدم", "نوشتم", "اومدم", "آمدم", "موندم", "زدم", "ریختم", "پرداختم",
             "گذاشتم", "فهمیدم", "شنیدم", "خوندم", "خواندم", "پرسیدم", "فرستادم", "کردیم",
             "شدیم", "دادیم", "رفتیم", "گرفتیم", "باختیم")
IMPERATIVES = {
    "ببین", "ببینید", "نکن", "نکنید", "نذار", "نذارید", "نزن", "نرو", "نخر", "نگو", "بنویس",
    "بنویسید", "بخون", "بخونید", "بخر", "بخرید", "بساز", "بسازید", "بفرست", "بفرستید",
    "بگیر", "بگیرید", "بده", "بدید", "بردار", "بردارید", "کپی", "کپیش", "ذخیره", "سیو",
    "فالو", "شروع", "تست", "امتحان", "چک", "حذف", "پاک", "ول", "بیخیال", "صبر", "گوش",
    "دقت", "توجه", "بیا", "بیاید", "بذار", "بذارید", "بزار", "بزارید", "بگو", "بگید",
    "بدون", "بدونید", "بشنو", "بفهم", "بفهمید", "ثبت", "بپرس", "بپرسید", "بکش", "ببر",
    "بیار", "بیارید", "نشو", "نباش", "نباشید", "بمون", "نمون", "برو", "برید", "بریم",
    "استارت", "ادامه", "فراموش", "یادت", "یادتون",
}


def is_second_person(tokens):
    for t in tokens:
        if t in SECOND_PERSON or re.fullmatch(r"ن?می\w{2,}(?:ی|ید|ین)", t):
            return True
    return False


def is_first_person(tokens):
    for t in tokens:
        if t in FIRST_PERSON or t.endswith(_PAST_1SG) or re.fullmatch(r"ن?می\w{2,}م", t):
            return True
    return False


def person_density(text):
    """Person markers per 100 words (Persian drops pronouns, so the scale is lower)."""
    toks = match_tokens(text)
    if not toks:
        return 0.0
    hits = sum(1 for t in toks
               if t in SECOND_PERSON or t in FIRST_PERSON or t.endswith(_PAST_1SG)
               or re.fullmatch(r"ن?می\w{2,}(?:ی|ید|ین|م)", t))
    return hits * 100 / len(toks)


# ---------------------------------------------------------------- stopwords

FA_STOPWORDS = {
    "و", "را", "رو", "که", "این", "اون", "آن", "یه", "یک", "از", "به", "در", "تو", "توی",
    "با", "برای", "برا", "واسه", "هم", "ولی", "اما", "اگه", "اگر", "من", "ما", "شما", "او",
    "اونا", "آنها", "است", "هست", "بود", "شد", "می", "نمی", "هر", "همه", "همین", "دیگه",
    "خیلی", "فقط", "هیچ", "چه", "چی", "تا", "بعد", "قبل", "نه", "هم", "یا", "اینه", "اینم",
}


def stem(token):
    """Crude: cut a ZWNJ-attached suffix. Good enough to spot a repeated word."""
    return token.split(ZWNJ)[0]


def same_word(a, b):
    a, b = match_form(a), match_form(b)
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)) \
            and abs(len(a) - len(b)) <= 3:
        return True
    return False
