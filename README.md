# ✈️ PlacementPilot

**Is this job really for freshers?** Paste any job post and PlacementPilot tells you in seconds
whether a fresher from your batch can genuinely apply, flags scam signs, and tailors your
résumé to the role, without inventing a single line.

Built on the **BharatCode API** (`qwen-3.8-27b`) for the BharatCode Build League.

## Why

Indian students lose hours every placement season to posts that are tagged "Freshers" but
ask for 1–3 years, are open only to the 2025 batch, or quietly ask for a "registration fee".
PlacementPilot reads the actual requirements text like a strict placement officer would.

## What you get

| | |
|---|---|
| ✅ **Eligibility verdict** | yes / no / unclear, with the exact requirement that decided it |
| 🎓 **Batch guardrail** | if the post names batches and yours isn't one, it's a no, even if the model is optimistic |
| 🚩 **Scam screen** | fees, deposits, WhatsApp-only recruiting, "no interview" promises, personal-email recruiters, Aadhaar/bank asks |
| 📊 **Match score** | how well your résumé covers the must-haves, plus gaps and what to learn next |
| ✍️ **Honest tailoring** | a role-specific summary, rewritten bullets that only use what's already on your résumé, and a short cover note |
| ⏭️ **Saves time** | tailoring is skipped automatically when the role isn't fresher-eligible |

Offline regex signals run alongside the model, so red flags are never dropped and every
verdict is explainable.

## Quick start

```bash
git clone https://github.com/jayanith/placement-pilot && cd placement-pilot
pip install -r requirements.txt
export BHARATCODE_API_KEY=bc_live_your_key_here   # from https://bharatcode.ai/account
```

**Web app**

```bash
uvicorn placement_pilot.server:app --reload
# open http://localhost:8000
```

**CLI**

```bash
python -m placement_pilot examples/sample_jd.txt --batch 2027 --resume my_resume.pdf
python -m placement_pilot examples/sample_jd.txt --json      # raw JSON
cat jd.txt | python -m placement_pilot -                      # from stdin
```

**Docker**

```bash
docker build -t placement-pilot . && docker run -p 8000:8000 -e BHARATCODE_API_KEY=... placement-pilot
```

## API

`POST /api/analyse` (multipart form)

| field | required | |
|---|---|---|
| `jd` | yes | full job description text |
| `batch` | no | graduation year, e.g. `2027` |
| `resume_text` / `resume_pdf` | no | paste text or upload a PDF (≤5 MB) |

Returns `{ eligibility, signals, tailoring, warnings }`.

## How it uses BharatCode

- OpenAI-compatible `POST /chat/completions` at `https://bharatcode.ai/api/model/v1`, model `qwen-3.8-27b`.
- Strict JSON schemas in the system prompt, tolerant parsing (code fences, think tags) and one self-repair pass.
- Retries on `503` (model busy) with backoff; on `finish_reason: length` it raises the output budget instead of repeating the same request, as the BharatCode docs advise.
- The API key stays server-side; the browser never sees it.

## Project layout

```
placement_pilot/
  llm.py      BharatCode client (retries, JSON extraction)
  core.py     heuristics, prompts, eligibility + tailoring pipeline
  server.py   FastAPI app
  cli.py      command-line interface
static/index.html   single-page UI
tests/              pytest suite (no API key needed)
```

## Tests

```bash
pip install pytest && pytest -q
```

## Roadmap

- Telegram bot: forward a job post, get the verdict back
- Batch mode: rank a whole spreadsheet of job links
- Browser extension for Naukri / LinkedIn / Unstop job pages

## License

MIT © 2026 Jayanith Chowdhary
