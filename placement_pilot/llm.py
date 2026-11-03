"""Thin client for the BharatCode OpenAI-compatible model API."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

BASE_URL = os.environ.get("BHARATCODE_BASE_URL", "https://bharatcode.ai/api/model/v1")
MODEL = os.environ.get("BHARATCODE_MODEL", "qwen-3.8-27b")


class LLMError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("BHARATCODE_API_KEY", "").strip()
    if not key:
        raise LLMError(
            "BHARATCODE_API_KEY is not set. Get a key at https://bharatcode.ai/account "
            "and export it (server-side only)."
        )
    return key


def chat(messages: list[dict[str, str]], *, max_tokens: int = 4000,
         temperature: float = 0.2, retries: int = 3, timeout: float = 120.0) -> str:
    """Call /chat/completions and return the assistant text.

    Retries on 503 (model busy), as the BharatCode docs recommend, and refuses
    to return output that was cut short by the token budget.
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = httpx.post(f"{BASE_URL}/chat/completions", json=payload,
                           headers=headers, timeout=timeout)
        except httpx.HTTPError as e:  # network hiccup
            last_err = e
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 503:
            last_err = LLMError("BharatCode model is busy (503)")
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code >= 400:
            rid = r.headers.get("x-request-id", "n/a")
            raise LLMError(f"BharatCode API error {r.status_code} (x-request-id {rid}): {r.text[:300]}")
        data = r.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            # Budget exhausted: a bigger budget is the fix, not the same retry.
            payload["max_tokens"] = min(32000, payload["max_tokens"] * 2)
            last_err = LLMError("Output cut short by max_tokens")
            continue
        return choice["message"]["content"] or ""
    raise LLMError(str(last_err) if last_err else "BharatCode request failed")


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> Any:
    """Parse the first JSON object in a model reply (tolerates fences/think tags)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise LLMError("Model did not return valid JSON")


def chat_json(system: str, user: str, **kw) -> Any:
    reply = chat([{"role": "system", "content": system},
                  {"role": "user", "content": user}], **kw)
    try:
        return extract_json(reply)
    except (LLMError, json.JSONDecodeError):
        # One repair pass: ask the model to fix its own output.
        fixed = chat([
            {"role": "system", "content": "Return ONLY valid minified JSON. No prose."},
            {"role": "user", "content": f"Fix this into valid JSON matching the intended schema:\n{reply}"},
        ], max_tokens=kw.get("max_tokens", 4000))
        return extract_json(fixed)
