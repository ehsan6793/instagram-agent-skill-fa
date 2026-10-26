# NOTICE

This project is a **Persian (Farsi) adaptation** of
[`Jakeschincariol/instagram-agent-skill`](https://github.com/Jakeschincariol/instagram-agent-skill)
by Jake Schincariol, used under the MIT License (see `LICENSE`).

## What is inherited

The idea and the overall design of the pack: the thirteen skills and their roles, the
"score the weakest check, not just the average" verdict logic, the outlier-multiple
research method, the 26 original hook-formula concepts (ids 1 to 26 keep the same numbers
so cross-references line up), and the rule that nothing is ever posted automatically.

## What is new in this Persian version

- All thirteen skills rewritten in Persian (not machine-translated): colloquial register,
  Persian examples, Persian-market notes (Shamsi calendar, Saturday-start week, Tehran
  time, تومان, «قیمت؟» comments, link accessibility for audiences in Iran).
- `fatext.py`, a Persian text layer: ZWNJ-safe cleaning, ی/ک and digit normalisation,
  Persian tokenising and matching, a concreteness detector that works without capital
  letters, and a written-versus-colloquial register detector.
- Three new native hook formulas (#27 میگن ولی، #28 جوابِ قیمت، #29 پدرم می‌گفت).
- A Persian slop lexicon and an opt-in written-to-colloquial rewriter (`humanize.py --spoken`).
- A sixth detection check, REGISTER, which measures the biggest tell of machine-written
  Persian: written prose where a person on camera would speak.
- Windows-friendly behaviour: forced UTF-8 output, BOM-tolerant reading, optional
  `--visual` display mode for terminals without right-to-left support.

## Honest status

The scoring heuristics (hook score, human score) are **not calibrated on Persian data**.
The English original reports its own limits (they separate real hooks from deliberately bad
ones well, and separate a creator's hits from misses barely better than chance). The Persian
version inherits that limitation and adds the lack of a Persian test set.
