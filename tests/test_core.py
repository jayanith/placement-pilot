import json

import pytest

from placement_pilot import core, llm


def test_heuristics_catch_scam_and_experience():
    jd = ("Hiring Software Engineer, 2-4 years experience. Pay a registration fee of Rs 999. "
          "Contact on WhatsApp only. Batches 2025, 2026.")
    s = core.heuristic_signals(jd)
    assert s["min_experience_years_mentioned"] == 2
    assert s["batch_years_mentioned"] == [2025, 2026]
    assert any("fee" in f for f in s["red_flags"])
    assert any("WhatsApp" in f for f in s["red_flags"])


def test_extract_json_handles_fences_and_think():
    txt = "<think>hmm</think>Here you go:\n```json\n{\"a\": 1}\n```"
    assert llm.extract_json(txt) == {"a": 1}
    assert llm.extract_json("noise {\"b\": 2} tail") == {"b": 2}


def test_batch_guardrail(monkeypatch):
    def fake(system, user, **kw):
        return {"role": "SDE", "company": "X", "eligible": "yes", "reason": "fresher ok",
                "allowed_batches": [2025, 2026], "red_flags": []}
    monkeypatch.setattr(llm, "chat_json", fake)
    elig, _ = core.check_eligibility("Fresher SDE role for batch 2025 and 2026 graduates. " * 3, 2027)
    assert elig["eligible"] == "no"
    assert "2027" in elig["reason"]


def test_tailoring_skipped_when_ineligible(monkeypatch):
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"eligible": "no", "reason": "5+ years", "red_flags": []})
    rep = core.analyse("Senior engineer, 5+ years of production experience required. " * 3, "resume text")
    assert rep.tailoring is None and rep.warnings


def test_short_jd_rejected():
    with pytest.raises(ValueError):
        core.analyse("too short")
