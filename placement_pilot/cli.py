"""Command line: placement-pilot jd.txt --resume resume.pdf --batch 2027"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import core, llm

ICON = {"yes": "✅ ELIGIBLE", "no": "❌ NOT ELIGIBLE", "unclear": "⚠️  UNCLEAR"}


def _read(path: str) -> str:
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return core.pdf_to_text(p.read_bytes())
    return p.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="placement-pilot",
                                 description="Check if a job is really fresher-eligible and tailor your résumé to it.")
    ap.add_argument("jd", help="job description file (.txt/.md/.pdf) or '-' for stdin")
    ap.add_argument("--resume", help="your résumé (.pdf or .txt)")
    ap.add_argument("--batch", type=int, help="your graduation year, e.g. 2027")
    ap.add_argument("--json", action="store_true", help="print raw JSON")
    a = ap.parse_args(argv)

    jd = sys.stdin.read() if a.jd == "-" else _read(a.jd)
    resume = _read(a.resume) if a.resume else None
    try:
        rep = core.analyse(jd, resume, a.batch)
    except (ValueError, llm.LLMError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
        return 0

    e = rep.eligibility
    print(f"\n{e.get('role','?')} @ {e.get('company','?')}")
    print(ICON.get(e.get("eligible"), "?"), "-", e.get("reason", ""))
    for k in ("pay", "location", "work_mode", "deadline"):
        if e.get(k):
            print(f"  {k}: {e[k]}")
    if e.get("red_flags"):
        print("  red flags:", "; ".join(e["red_flags"]))
    t = rep.tailoring
    if t:
        print(f"\nMatch score: {t['match_score']}/100")
        print("  missing:", ", ".join(t.get("missing_skills", [])) or "none")
        print("\nSummary:\n ", t.get("tailored_summary", ""))
        for b in t.get("tailored_bullets", []):
            print(f"  • {b.get('rewritten')}")
        print("\nCover note:\n", t.get("cover_note", ""))
    for w in rep.warnings:
        print("note:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
