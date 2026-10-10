"""Number grounding: every number in an answer must come from a tool output or the user.

Small models paraphrase, so a number counts as grounded when it matches a source number exactly,
after rounding, as an absolute value (e.g. "28% less" for -28.1), or within 3% of it. Clock times
are checked the same way against times that appear in tool outputs.
"""

from __future__ import annotations

import json
import re

NUM = re.compile(r"(?<![\w.])[-−]?\d+(?:[.,]\d+)?(?![\w])")
TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
# Numbers that are safe without a source: small counts, ordinals, unit names like PM2.5.
SAFE = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 2.5, 24, 100}


def _numbers(text: str) -> list[float]:
    text = TIME.sub(" ", text)
    out = []
    for m in NUM.finditer(text):
        s = m.group(0).replace("−", "-").replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def _source_numbers(obj) -> set[float]:
    found: set[float] = set()

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            found.add(float(x))
        elif isinstance(x, str):
            found.update(_numbers(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(obj)
    return found


def _times(obj) -> set[str]:
    return {f"{int(h):02d}:{m}" for h, m in TIME.findall(json.dumps(obj, default=str))}


def check(answer: str, tool_outputs: list, user_text: str = "") -> tuple[bool, list[str]]:
    sources = _source_numbers(tool_outputs) | set(_numbers(user_text))
    candidates = sources | {abs(v) for v in sources}
    # Fractions are often stated as percentages (confidence 0.67 -> "67%").
    candidates |= {round(v * 100, 1) for v in candidates if 0 < abs(v) <= 1}
    candidates |= {round(v) for v in candidates} | {round(v, 1) for v in candidates}
    bad = []
    for v in _numbers(answer):
        a = abs(v)
        if a in SAFE or v in candidates or a in candidates:
            continue
        if any(c and abs(a - abs(c)) <= max(0.03 * abs(c), 0.5) for c in candidates):
            continue
        bad.append(f"{v:g}")
    allowed_times = _times(tool_outputs) | _times(user_text)
    for h, m in TIME.findall(answer):
        t = f"{int(h):02d}:{m}"
        if t not in allowed_times:
            bad.append(t)
    return (not bad), bad
