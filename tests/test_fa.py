# -*- coding: utf-8 -*-
"""Tests for the Persian Instagram skill pack.  Run:  python3 -m unittest discover -s tests -v"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "skills")
ZWNJ, ZWJ = "‌", "‍"


def load(skill, module):
    """Import skills/<skill>/<module>.py as an isolated module (each skill is a standalone folder)."""
    path = os.path.join(SK, skill, module + ".py")
    sys.path.insert(0, os.path.join(SK, skill))
    try:
        spec = importlib.util.spec_from_file_location(f"{skill}_{module}".replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


def run_cli(skill, script, *args, stdin=None):
    cmd = [sys.executable, "-I", os.path.join(SK, skill, script), *args]
    env = dict(os.environ, PYTHONIOENCODING="")      # make sure we do not rely on the caller's setting
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


ROBOT = (
    "سلام دوستان عزیز! در دنیای پرشتاب امروز، بدون شک بازاریابی در اینستاگرام نقش کلیدی ایفا می‌کند — "
    "و این فقط یک ابزار نیست، بلکه یک سفر هیجان‌انگیز است. 🚀\n\n"
    "لازم به ذکر است که بهینه‌سازی پروفایل بسیار ضروری است. همچنین می‌توانید محتوای ارزشمند تولید نمایید. "
    "بنابراین جهت افزایش فروش، نظرات خود را در کامنت‌ها بنویسید.\n\n"
    "در نهایت می‌توان گفت که این راهکار جامع، سریع، ساده و کارآمد است!!!\n#a #b #c #d #e #f\n"
)
HUMAN = (
    "۴۷ تا ریل اولم میانگین ۳۰۰ بازدید گرفت. دیروز نشستم ببینم چرا. ریلِ ۴۸م ۴۰۰ هزار تا شد.\n\n"
    "فقط یه چیز عوض کردم: دیگه با «سلام» شروع نمی‌کردم. خیلی ساده بود، ولی هیچ‌کس بهم نگفته بود. "
    "فکر می‌کردم مشکل از الگوریتمه. نه. مشکل از ثانیه‌ی اول بود.\n\n"
    "اگه تو هم ریل می‌ذاری و بازدیدت جایی گیر کرده، همین رو امتحان کن. جواب بده یا نده، سه روز طول می‌کشه تا بفهمی.\n"
)


class FatextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = load("ig-reel-fa", "fatext")

    def test_zwnj_between_letters_kept_stray_removed(self):
        text = "می" + ZWNJ + "روم کتاب" + ZWNJ + ZWNJ + "ها " + ZWNJ + "x " + "یک" + ZWNJ
        out, hits = self.F.clean_invisible(text)
        self.assertIn("می" + ZWNJ + "روم", out)
        self.assertIn("کتاب" + ZWNJ + "ها", out)
        self.assertNotIn(ZWNJ + ZWNJ, out)
        self.assertFalse(out.endswith(ZWNJ))
        self.assertTrue(hits)

    def test_zwj_kept_in_emoji_only(self):
        fam = "\U0001F468" + ZWJ + "\U0001F469" + ZWJ + "\U0001F467"
        out, _ = self.F.clean_invisible("a" + ZWJ + "b " + fam)
        self.assertIn(fam, out)
        self.assertNotIn("a" + ZWJ, out)

    def test_exotic_spaces_and_bom(self):
        out, hits = self.F.clean_invisible("a b c﻿d​e")
        self.assertEqual(out, "a b cde")
        self.assertEqual(sum(h["count"] for h in hits), 4)

    def test_lrm_only_on_mixed_lines(self):
        lrm = "‎"
        mixed, _ = self.F.clean_invisible("سلام Instagram" + lrm)
        pure, _ = self.F.clean_invisible("سلام" + lrm)
        self.assertIn(lrm, mixed)
        self.assertNotIn(lrm, pure)

    def test_digits_and_letters(self):
        self.assertEqual(self.F.to_ascii_digits("۱۲۳٤٥٦"), "123456")
        self.assertEqual(self.F.to_persian_digits("a 123"), "a ۱۲۳")
        out, _ = self.F.normalize_letters("كتاب ي")
        self.assertEqual(out, "کتاب ی")

    def test_match_form(self):
        mf = self.F.match_form
        self.assertEqual(mf("هیچ" + ZWNJ + "کس ۱۸٬۰۰۰٬۰۰۰"), "هیچکس 18000000")
        self.assertEqual(mf("می کنم"), "میکنم")
        self.assertEqual(mf("کتاب ها"), "کتابها")
        self.assertEqual(mf("می" + ZWNJ + "خوام"), mf("میخوام"))

    def test_phrase_regex_tolerates_spelling(self):
        rx = self.F.phrase_regex("می" + ZWNJ + "توانید")
        for variant in ("می" + ZWNJ + "توانید", "میتوانید", "می توانید"):
            self.assertTrue(rx.search("شما " + variant + " بیایید"), variant)
        self.assertIsNone(rx.search("میتوانیدها"))

    def test_concreteness_without_capitals(self):
        m = self.F.concrete_markers("۱۸ میلیون تومن از @ali توی دیجی‌کالا و Instagram و «قرارداد»")
        self.assertTrue(m["nums"] and m["handles"] and m["quoted"] and m["latin"])
        self.assertEqual(self.F.concrete_count("سلام خوبی چطوری"), 0)

    def test_register_detects_written_vs_spoken(self):
        f1, s1, _ = self.F.register_counts("بنابراین جهت افزایش فروش می‌توانید اقدام نمایید و همچنین بسیار موفق شوید")
        f2, s2, _ = self.F.register_counts("برای همین واسه فروش بیشتر می‌تونی یه کاری بکنی و خیلی هم موفق شی")
        self.assertGreater(f1, s1)
        self.assertGreater(s2, f2)

    def test_copies_identical(self):
        canon = read(os.path.join(SK, "ig-reel-fa", "fatext.py"))
        for d in ("ig-caption-fa", "ig-human-fa", "ig-viral-fa"):
            self.assertEqual(read(os.path.join(SK, d, "fatext.py")), canon, d)


class HooksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = load("ig-reel-fa", "fatext")
        with open(os.path.join(SK, "ig-reel-fa", "hooks.json"), encoding="utf-8") as fh:
            cls.d = json.load(fh)

    def test_ids_and_order(self):
        ids = [h["id"] for h in self.d["hooks"]]
        self.assertEqual(sorted(ids), list(range(1, 30)))
        self.assertEqual(sorted(self.d["classify_order"]), list(range(1, 30)))
        self.assertEqual(self.d["count"], 29)

    def test_fields_present(self):
        for h in self.d["hooks"]:
            for k in ("name", "template", "example", "on_screen", "best_for", "trap", "match"):
                self.assertTrue(h.get(k), (h["id"], k))
            self.assertNotIn(ZWNJ, h["match"], f"#{h['id']}: write match in match_form (no half-spaces)")
            re.compile(h["match"])

    def test_each_example_classifies_to_itself(self):
        by = {h["id"]: re.compile(h["match"], re.I) for h in self.d["hooks"]}
        for h in self.d["hooks"]:
            form = self.F.match_form(h["example"])
            hit = next((i for i in self.d["classify_order"] if by[i].search(form)), None)
            self.assertEqual(hit, h["id"], f"#{h['id']} {h['name']} classified as #{hit}")

    def test_examples_survive_spelling_variants(self):
        by = {h["id"]: re.compile(h["match"], re.I) for h in self.d["hooks"]}
        h = next(x for x in self.d["hooks"] if x["id"] == 3)
        for variant in ("هیچکس بهت نمیگه که سی تا ریل اولت میسوزه", "هیچ کس بهت نمی‌گه که سی تا ریل اولت می‌سوزه"):
            self.assertTrue(by[3].search(self.F.match_form(variant)), variant)

    def test_no_invented_statistics_claimed_as_real(self):
        t = next(h for h in self.d["hooks"] if h["id"] == 23)
        self.assertIn("آمار واقعی نیست", t["trap"])


class HookscoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hs = load("ig-reel-fa", "hookscore")

    def score(self, s):
        return self.hs.run(s)[1]

    def test_good_beats_bad(self):
        good = self.score("۱۸ میلیون تومن ضرر دادم، فقط به‌خاطر یه بند توی قرارداد.")
        greeting = self.score("سلام دوستان امروز می‌خوام درباره‌ی بازاریابی توی اینستاگرام صحبت کنم.")
        written = self.score("بنابراین جهت افزایش فروش می‌بایست محتوای مناسب تولید نمود.")
        self.assertGreater(good, 70)
        self.assertLess(greeting, 40)
        self.assertLess(written, 40)

    def test_dealbreakers(self):
        _, _, _, flags = self.hs.run("سلام بچه‌ها امروز میخوام بگم")
        self.assertTrue(flags)
        _, _, _, flags = self.hs.run("توی این ویدیو بهتون نشون میدم چطور")
        self.assertTrue(any("مقدمه" in f for f in flags))

    def test_no_double_counting_money(self):
        _, detail = self.hs.check_specificity("۱۸ میلیون تومن ضرر")
        self.assertIn("1" + "8", detail)

    def test_cli_json_and_exit_codes(self):
        p = run_cli("ig-reel-fa", "hookscore.py", "-", "--json", stdin="۱۸ میلیون تومن ضرر دادم، فقط به‌خاطر یه بند.\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("score", json.loads(p.stdout))
        p = run_cli("ig-reel-fa", "hookscore.py", "-", stdin="سلام دوستان\n")
        self.assertEqual(p.returncode, 1)


class BeatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load("ig-reel-fa", "beats")

    def test_calibrate_parser(self):
        self.assertEqual(self.b.parse_calibration("۴۲ کلمه / ۲۸ ثانیه"), 90.0)
        self.assertEqual(self.b.parse_calibration("42/21"), 120.0)
        with self.assertRaises(ValueError):
            self.b.parse_calibration("42")

    def test_flags_long_hook_and_loop(self):
        script = ("۱۸ میلیون تومن ضرر دادم، فقط به‌خاطر یه بند توی قرارداد که هیچ‌کس بهم نگفته بود.\n"
                  "من بندِ هشت رو امضا کردم.\nقبل از امضا، همیشه بندِ هشت رو بخون.\n")
        a = self.b.analyse(script, wpm=138, target=10)
        self.assertEqual(a["beats"][0]["label"], "HOOK")
        self.assertTrue(a["beats"][0]["flags"])
        self.assertTrue(any("حلقه:" in n for n in a["notes"]))

    def test_cli(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write("۱۸ میلیون تومن ضرر دادم.\nبندِ هشت رو بخون.\n")
        try:
            p = run_cli("ig-reel-fa", "beats.py", fh.name, "--json")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout)["wpm"], 138)
        finally:
            os.unlink(fh.name)


class HumanizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = load("ig-human-fa", "humanize")
        cls.d = load("ig-human-fa", "detect")
        cls.F = load("ig-human-fa", "fatext")
        cls.lex = cls.h.load_lexicon(os.path.join(SK, "ig-human-fa", "slop.json"))

    def hum(self, text, **kw):
        return self.h.humanize(text, self.lex, **kw)

    def test_persian_survives(self):
        text = "او می" + ZWNJ + "رود و کتاب" + ZWNJ + "ها را می" + ZWNJ + "خواند.​\n"
        out, _ = self.hum(text)
        self.assertIn("می" + ZWNJ + "رود", out)
        self.assertIn("کتاب" + ZWNJ + "ها", out)
        self.assertNotIn("​", out)

    def test_idempotent(self):
        for kw in ({}, {"spoken": True}):
            once, _ = self.hum(ROBOT, **kw)
            twice, _ = self.hum(once, **kw)
            self.assertEqual(once, twice, kw)

    def test_no_orphan_punctuation(self):
        out, _ = self.hum("بدون شک، سلام. دوستان عزیز، امروز می" + ZWNJ + "خوام بگم.")
        self.assertNotRegex(out, r"(?m)^\s*[،,.]")
        self.assertNotRegex(out, r"[،,]\s*[،,.]")

    def test_slop_replaced_and_urls_untouched(self):
        out, rep = self.hum("در دنیای امروز بدون شک https://example.com/دنیای-امروز مهم است.")
        self.assertIn("https://example.com/دنیای-امروز", out)
        self.assertNotIn("بدون شک", out)
        self.assertTrue(rep["lexical"])

    def test_em_dash_and_quotes(self):
        out, _ = self.hum("این — خوبه و “تست” می‌شه…")
        self.assertNotIn("—", out)
        self.assertIn("«تست»", out)

    def test_spoken_rules(self):
        out, rep = self.hum("می" + ZWNJ + "خواهم این را بگویم. این مهم است. او نیز می" + ZWNJ + "داند.", spoken=True)
        self.assertIn("می" + ZWNJ + "خوام", out)
        self.assertIn(" رو ", out)
        self.assertIn("مهمه", out)
        self.assertIn("هم", out)
        self.assertTrue(rep["spoken"])

    def test_structures_flagged_not_rewritten(self):
        out, rep = self.hum("این فقط یک ابزار نیست، بلکه یک سفر است.")
        self.assertIn("بلکه", out)
        self.assertTrue(any(s["id"] == "not-just" for s in rep["structures"]))

    def test_hashtag_wall_and_cap(self):
        _, rep = self.hum("متن\n#a #b #c #d #e #f")
        self.assertTrue(any(s["id"] == "hashtag-wall" for s in rep["structures"]))
        _, rep = self.hum("متن\n#a #b #c #d #e")
        self.assertFalse(any(s["id"] == "hashtag-wall" for s in rep["structures"]))

    def test_detect_separates_robot_from_human(self):
        r = self.d.run(ROBOT, self.lex)[1]
        hmn = self.d.run(HUMAN, self.lex)[1]
        cleaned = self.d.run(self.hum(ROBOT, spoken=True)[0], self.lex)[1]
        self.assertGreater(hmn - r, 25)
        self.assertGreater(cleaned, r + 15)

    def test_detect_register_switch(self):
        formal = "بنابراین جهت افزایش فروش می‌توانید اقدام نمایید. همچنین بسیار مهم است که اکنون شروع کنید. " * 2
        spoken_panel = self.d.run(formal, self.lex, "spoken")[0]
        written_panel = self.d.run(formal, self.lex, "written")[0]
        self.assertIn("REGISTER", spoken_panel)
        self.assertNotIn("REGISTER", written_panel)
        self.assertLess(spoken_panel["REGISTER"][0], 30)

    def test_fingerprint_does_not_punish_legit_zwnj(self):
        text = "می" + ZWNJ + "روم و کتاب" + ZWNJ + "ها رو می" + ZWNJ + "خونم. " * 8
        score, _ = self.d.check_fingerprint(text)
        self.assertEqual(score, 100.0)

    def test_lexicon_valid(self):
        for e in self.lex["phrases"] + self.lex["words"]:
            self.assertTrue(e["find"])
            self.F.phrase_regex(e["find"])
        for s in self.lex["structures"]:
            re.compile(s["regex"])
        ids = [s["id"] for s in self.lex["structures"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_cli_stdin_roundtrip_and_report(self):
        p = run_cli("ig-human-fa", "humanize.py", "-", "--report", stdin=ROBOT)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("HUMANIZE REPORT", p.stderr)
        self.assertNotIn("دوستان عزیز", p.stdout)


class CaptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load("ig-caption-fa", "caption")

    def status(self, a, name):
        return next(x["status"] for x in a["checks"] if x["check"] == name)

    def test_ready_caption(self):
        text = ("۱۸ میلیون تومن ضرر دادم، فقط به‌خاطر یه بند توی قرارداد.\n\nسه ماه بعد مشتری پولش رو پس خواست.\n\n"
                "ذخیره‌ش کن تا یادت نره.\n\n#قرارداد #فریلنسری #بازاریابی")
        a = self.c.analyse(text, keywords=["قرارداد"])
        self.assertEqual(a["verdict"], "READY", a["checks"])

    def test_hashtag_cap_and_filler(self):
        a = self.c.analyse("جمله‌ی اول ۱۰۰ تومن\n#a #b #c #d #e #f")
        self.assertEqual(self.status(a, "HASHTAGS"), "FAIL")
        a = self.c.analyse("جمله‌ی اول ۱۰۰ تومن\n#ایران #اکسپلور #ریلز")
        self.assertEqual(self.status(a, "HASHTAGS"), "WARN")

    def test_greeting_and_hashtag_first(self):
        self.assertEqual(self.status(self.c.analyse("سلام دوستان امروز"), "FIRST LINE"), "WARN")
        self.assertEqual(self.status(self.c.analyse("#قرارداد متن"), "FIRST LINE"), "FAIL")

    def test_asks_counted(self):
        a = self.c.analyse("متن ۲۰ تومن. ذخیره‌ش کن و دایرکت بده و فالو کن.")
        self.assertGreaterEqual(len(a["asks"]), 3)
        self.assertEqual(self.status(a, "ONE ASK"), "WARN")

    def test_link_and_spelling(self):
        a = self.c.analyse("ببین https://example.com ۱۲ و 12 كتاب؟".replace("؟", "?"))
        self.assertEqual(self.status(a, "LINKS"), "WARN")
        self.assertEqual(self.status(a, "SPELLING"), "WARN")

    def test_search_terms_spelling_tolerant(self):
        a = self.c.analyse("درباره‌ی نرم" + ZWNJ + "افزار قرارداد ۲ تومن", keywords=["نرمافزار قرارداد"])
        self.assertEqual(self.status(a, "SEARCH TERMS"), "PASS")

    def test_too_long(self):
        a = self.c.analyse("ا" * 2300)
        self.assertEqual(self.status(a, "LENGTH"), "FAIL")


class SwipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load("ig-viral-fa", "swipe")

    def test_parse_count(self):
        p = self.s.parse_count
        self.assertEqual(p("412000"), 412000)
        self.assertEqual(p("۴۱۲٬۰۰۰"), 412000)
        self.assertEqual(p("412k"), 412000)
        self.assertEqual(p("1.2m"), 1200000)
        self.assertEqual(p("۱٫۲ میلیون"), 1200000)
        self.assertEqual(p("۴۱۲ هزار"), 412000)
        self.assertIsNone(p("abc"))

    def test_cli_ranks_by_outlier(self):
        tsv = ("account\tfollowers\tmedian\tviews\thook\n"
               "@a\t48K\t11K\t412K\tهیچ‌کس بهت نمی‌گه که سی تا ریلِ اولت می‌سوزه\n"
               "@b\t۲ میلیون\t۴۰۰ هزار\t۴۱۲٬۰۰۰\tسلام دوستان امروز می‌خوام بگم\n")
        p = run_cli("ig-viral-fa", "swipe.py", "-", "--json", stdin=tsv)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(p.stdout)
        self.assertEqual(d["reels"][0]["account"], "@a")
        self.assertEqual(d["reels"][0]["formula_id"], 3)
        self.assertAlmostEqual(d["reels"][0]["outlier"], 37.45, places=1)


class PackTests(unittest.TestCase):
    SKILLS = ["reel", "viral", "caption", "carousel", "story", "plan", "profile", "audit", "comment", "reply",
              "dm", "repurpose", "human"]

    def test_thirteen_skills_with_valid_frontmatter(self):
        dirs = sorted(d for d in os.listdir(SK) if d.startswith("ig-"))
        self.assertEqual(dirs, sorted(f"ig-{n}-fa" for n in self.SKILLS))
        for d in dirs:
            text = read(os.path.join(SK, d, "SKILL.md"))
            m = re.match(r"---\n(.*?)\n---\n", text, re.S)
            self.assertTrue(m, d)
            fm = m.group(1)
            self.assertRegex(fm, rf"(?m)^name: {re.escape(d)}$")
            self.assertRegex(fm, r"(?m)^description: >-$")
            desc = " ".join(l.strip() for l in fm.split("description: >-")[1].splitlines() if l.strip())
            self.assertGreater(len(desc), 60, d)
            self.assertLess(len(desc), 1024, d)
            self.assertNotIn("<", desc)

    def test_referenced_scripts_exist(self):
        for d in os.listdir(SK):
            text = read(os.path.join(SK, d, "SKILL.md"))
            for script in set(re.findall(r"python3 (\w+\.py)", text)):
                self.assertTrue(os.path.exists(os.path.join(SK, d, script)), f"{d} mentions {script}")

    def test_cross_references_point_to_real_skills(self):
        names = {f"ig-{n}-fa" for n in self.SKILLS}
        for d in names:
            text = read(os.path.join(SK, d, "SKILL.md"))
            for ref in re.findall(r"/(ig-[a-z]+(?:-fa)?)\b", text):
                self.assertIn(ref, names, f"{d} references /{ref}")

    def test_rubric_sums_to_100(self):
        r = json.loads(read(os.path.join(SK, "ig-profile-fa", "rubric.json")))
        self.assertEqual(sum(i["points"] for i in r["items"]), 100)
        self.assertEqual(len(r["items"]), 12)

    def test_manifests(self):
        p = json.loads(read(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
        m = json.loads(read(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
        self.assertEqual(p["name"], "instagram-agent-fa")
        self.assertEqual(m["plugins"][0]["name"], p["name"])
        self.assertTrue(read(os.path.join(ROOT, "LICENSE")).startswith("MIT License"))

    def test_all_python_compiles_and_is_utf8(self):
        for dirpath, _, files in os.walk(ROOT):
            if ".git" in dirpath:
                continue
            for f in files:
                if f.endswith(".py"):
                    src = read(os.path.join(dirpath, f))
                    compile(src, f, "exec")

    def test_no_bom_or_crlf_in_text_files(self):
        for dirpath, _, files in os.walk(ROOT):
            if ".git" in dirpath:
                continue
            for f in files:
                if f.endswith((".py", ".md", ".json", ".yml")):
                    with open(os.path.join(dirpath, f), "rb") as fh:
                        raw = fh.read()
                    self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f)
                    self.assertNotIn(b"\r\n", raw, f)

    def test_hashtag_cap_statement_consistent(self):
        text = read(os.path.join(SK, "ig-caption-fa", "SKILL.md"))
        self.assertIn("۱۸ دسامبر ۲۰۲۵", text)
        self.assertEqual(load("ig-caption-fa", "caption").HASHTAG_LIMIT, 5)


if __name__ == "__main__":
    unittest.main()
