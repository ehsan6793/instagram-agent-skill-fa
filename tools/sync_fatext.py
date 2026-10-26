#!/usr/bin/env python3
"""Keep the four copies of fatext.py identical.

Skills are installed as separate folders (~/.claude/skills/ig-*-fa), so each skill that
needs the shared Persian text layer carries its own copy. The canonical one lives in
skills/ig-reel-fa/fatext.py. Edit THAT file, then run:

    python3 tools/sync_fatext.py          # copy canonical -> the others
    python3 tools/sync_fatext.py --check  # exit 1 if any copy differs (used by CI)
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(ROOT, "skills", "ig-reel-fa", "fatext.py")
COPIES = [os.path.join(ROOT, "skills", d, "fatext.py")
          for d in ("ig-caption-fa", "ig-human-fa", "ig-viral-fa")]


def read(p):
    with open(p, "rb") as fh:
        return fh.read()


def main():
    check = "--check" in sys.argv
    want = read(CANON)
    bad = []
    for p in COPIES:
        if not os.path.exists(p) or read(p) != want:
            bad.append(p)
            if not check:
                shutil.copyfile(CANON, p)
    rel = lambda p: os.path.relpath(p, ROOT)
    if check:
        if bad:
            print("fatext.py copies out of sync:\n  " + "\n  ".join(map(rel, bad)), file=sys.stderr)
            sys.exit(1)
        print("fatext.py copies are in sync")
    else:
        print("synced:" if bad else "already in sync", *map(rel, bad))


if __name__ == "__main__":
    main()
