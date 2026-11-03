"""FastAPI web app: paste a JD, optionally upload a résumé, get a verdict."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import core, llm

STATIC = Path(__file__).resolve().parent.parent / "static"
app = FastAPI(title="PlacementPilot", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "model": llm.MODEL}


@app.post("/api/analyse")
async def analyse(
    jd: str = Form(...),
    batch: int | None = Form(None),
    resume_text: str | None = Form(None),
    resume_pdf: UploadFile | None = File(None),
):
    text = resume_text or ""
    if resume_pdf is not None and resume_pdf.filename:
        data = await resume_pdf.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, "Résumé PDF must be under 5 MB")
        try:
            text = core.pdf_to_text(data)
        except Exception:
            raise HTTPException(400, "Could not read that PDF; paste the text instead.")
    try:
        return core.analyse(jd, text or None, batch).to_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))
