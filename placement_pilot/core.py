"""PlacementPilot core: fresher-eligibility check, scam screen, résumé tailoring."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from . import llm

# ---------------------------------------------------------------- heuristics
# Fast, offline signals that run before (and alongside) the model, so the
# verdict is explainable and still useful if the model is busy.

SCAM_PATTERNS = {
    r"registration fee|security deposit|refundable deposit|pay (?:a|the) fee|training fee": "Asks the candidate to pay a fee",
    r"whatsapp only|contact on whatsapp|telegram": "Recruiting only through WhatsApp/Telegram",
    r"no interview|direct joining|100% placement|guaranteed (?:job|placement)": "Promises a job with no selection process",
    r"aadhaar|pan card|bank details|otp": "Asks for identity/bank details up front",
    r"@gmail\.com|@yahoo\.com|@outlook\.com": "Recruiter uses a free personal email domain",
}

EXP_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+|-|to|–)?\s*(\d+(?:\.\d+)?)?\s*(?:\+)?\s*(?:years?|yrs?)", re.I)
BATCH_RE = re.compile(r"\b(20[2-3]\d)\b")
FRESHER_RE = re.compile(r"\bfresher|fresh graduate|new grad|entry[- ]level|0\s*(?:-|to)\s*\d+\s*years?|campus|intern(?:ship)?\b", re.I)


def heuristic_signals(jd: str) -> dict:
    text = jd.lower()
    flags = [msg for pat, msg in SCAM_PATTERNS.items() if re.search(pat, text)]
    exps = []
    for m in EXP_RE.finditer(jd):
        try:
            exps.append(float(m.group(1)))
        except ValueError:
            pass
    years = sorted({int(y) for y in BATCH_RE.findall(jd)})
    return {
        "min_experience_years_mentioned": min(exps) if exps else None,
        "batch_years_mentioned": years,
        "fresher_language": bool(FRESHER_RE.search(jd)),
        "red_flags": flags,
    }


# ---------------------------------------------------------------- prompts
ELIGIBILITY_SYSTEM = """You are PlacementPilot, a careful placement officer for Indian engineering students.
Read a job description and decide whether a FRESHER from a given graduation batch can genuinely apply.
Be strict: 'Freshers' tags on portals are often wrong; trust the actual requirements text.
Return ONLY JSON with this schema:
{
 "role": str, "company": str,
 "employment_type": "full-time"|"internship"|"contract"|"unknown",
 "eligible": "yes"|"no"|"unclear",
 "reason": str,                       // one or two sentences quoting the decisive requirement
 "min_experience_years": number|null,
 "allowed_batches": [int],            // empty if not stated
 "pay": str|null,                     // CTC or stipend exactly as written, else null
 "location": str|null, "work_mode": "onsite"|"hybrid"|"remote"|"unknown",
 "must_have_skills": [str], "nice_to_have_skills": [str],
 "red_flags": [str],                  // fees, vague company, personal emails, unpaid, etc.
 "deadline": str|null
}"""

TAILOR_SYSTEM = """You are PlacementPilot, an honest résumé coach for Indian freshers.
Compare the candidate's résumé with the job description.
RULES: never invent experience, employers, metrics or skills the résumé does not support.
You may rephrase, reorder and surface relevant existing work using the JD's vocabulary.
Return ONLY JSON:
{
 "match_score": int,                  // 0-100, how well the résumé fits the must-haves
 "matched_skills": [str],
 "missing_skills": [str],             // JD must-haves the résumé does not show
 "tailored_summary": str,             // 2-3 line professional summary for this role
 "tailored_bullets": [ {"section": str, "original": str, "rewritten": str} ],  // up to 6
 "learn_next": [str],                 // up to 3 concrete things to close the gap fast
 "cover_note": str                    // <=120 words, plain, no clichés
}"""


@dataclass
class Report:
    eligibility: dict
    signals: dict
    tailoring: dict | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"eligibility": self.eligibility, "signals": self.signals,
                "tailoring": self.tailoring, "warnings": self.warnings}


def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages).strip()


def check_eligibility(jd: str, batch: int | None = None) -> tuple[dict, dict]:
    signals = heuristic_signals(jd)
    who = f"Candidate graduates in {batch}." if batch else "Candidate is a fresher."
    result = llm.chat_json(ELIGIBILITY_SYSTEM, f"{who}\n\nJOB DESCRIPTION:\n{jd[:20000]}")
    # Merge offline red flags so nothing the regex caught is dropped.
    flags = list(dict.fromkeys((result.get("red_flags") or []) + signals["red_flags"]))
    result["red_flags"] = flags
    # Guardrail: if the JD names batches and the candidate's isn't one, it's a no.
    allowed = result.get("allowed_batches") or []
    if batch and allowed and batch not in allowed and result.get("eligible") == "yes":
        result["eligible"] = "no"
        result["reason"] = f"Open only to batches {allowed}; you graduate in {batch}."
    return result, signals


def tailor(jd: str, resume_text: str) -> dict:
    user = f"JOB DESCRIPTION:\n{jd[:15000]}\n\nRÉSUMÉ:\n{resume_text[:15000]}"
    out = llm.chat_json(TAILOR_SYSTEM, user, max_tokens=6000)
    try:
        out["match_score"] = max(0, min(100, int(out.get("match_score", 0))))
    except (TypeError, ValueError):
        out["match_score"] = 0
    return out


def analyse(jd: str, resume_text: str | None = None, batch: int | None = None) -> Report:
    if len(jd.strip()) < 80:
        raise ValueError("Paste the full job description (at least a few lines).")
    elig, signals = check_eligibility(jd, batch)
    rep = Report(eligibility=elig, signals=signals)
    if resume_text and resume_text.strip():
        if elig.get("eligible") == "no":
            rep.warnings.append("Not fresher-eligible, so tailoring was skipped to save your time.")
        else:
            rep.tailoring = tailor(jd, resume_text)
    return rep
