from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from rich.console import Console

load_dotenv()
console = Console()
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


async def ask_llm(prompt: str, model: str = "gpt-4.1") -> str:
    """Single-shot completion. Logs prompt/response with rich for visibility in demos."""
    console.print(f"[blue][LLM ▶][/blue] {prompt.strip()[:120]}…")
    res = await _get_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    message = res.choices[0].message.content or ""
    console.print(f"[green][LLM ◀][/green] {message.strip()[:120]}…")
    return message
