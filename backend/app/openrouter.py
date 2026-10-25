"""Backup language models through OpenRouter, used only when Gemini cannot plan a run.

OpenRouter serves open models (Gemma, Nemotron...) behind one OpenAI-compatible API, some of them free.
Free models have their own daily request limit and may be slower, so they are the second line: Gemini
first, then these, then the fixed plan, which needs no model at all. Without OPENROUTER_API_KEY this
module is never called.
"""
import httpx

from . import config

URL = "https://openrouter.ai/api/v1/chat/completions"
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests replace the network


class OpenRouterError(Exception):
    pass


async def chat(model: str, messages: list[dict], *, tools: list[dict] | None = None, json_mode: bool = False,
               timeout: float = 12.0) -> dict:
    """One chat completion; returns the assistant message. Raises OpenRouterError on any refusal."""
    body: dict = {"model": model, "messages": messages, "temperature": 0.2}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                           "parameters": t["parameters_json_schema"]}}
                         for t in tools]
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
               "HTTP-Referer": "https://comprende.vercel.app", "X-Title": "Comprende"}
    async with httpx.AsyncClient(timeout=timeout, transport=TRANSPORT) as client:
        r = await client.post(URL, json=body, headers=headers)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or "error" in data or not data.get("choices"):
        raise OpenRouterError(f"{r.status_code} {data.get('error') or r.text[:200]}")
    return data["choices"][0]["message"]
