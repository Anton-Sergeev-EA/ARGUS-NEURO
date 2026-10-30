#!/usr/bin/env python3
"""Fail if the README translations drift apart or a documentation link is broken."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READMES = sorted(ROOT.glob("README*.md"))
REQUIRED = {
    "docs/BACKTEST.md",
    "docs/CURVES.md",
    "docs/METHODOLOGY.md",
    "docs/PUBLIC_BATTERY_DATA.md",
    "docs/USE_CASES.md",
}
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def local_links(path: Path) -> set[str]:
    found = set()
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if not re.match(r"[a-z]+:", target):
            found.add(target)
    return found


def main() -> int:
    problems: list[str] = []
    if len(READMES) != 9:
        problems.append(f"expected 9 README files, found {len(READMES)}")
    for readme in READMES:
        links = local_links(readme)
        for target in sorted(links):
            if not (ROOT / target).exists():
                problems.append(f"{readme.name}: broken link {target}")
        for target in sorted(REQUIRED - links):
            problems.append(f"{readme.name}: missing link to {target}")
    for doc in sorted((ROOT / "docs").glob("*.md")):
        for target in sorted(local_links(doc)):
            if not ((doc.parent / target).exists() or (ROOT / target).exists()):
                problems.append(f"docs/{doc.name}: broken link {target}")
    for problem in problems:
        print(problem)
    print("documentation consistent" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
