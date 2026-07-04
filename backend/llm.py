"""Anthropic Claude LLM helper.

Single place the app talks to the LLM. The model NEVER decides trade
signals or invents numbers — endpoints hand it computed data and it
writes the narrative around that data (anti-hallucination by design).
"""
import os
import sys

from anthropic import AsyncAnthropic

# Default: Haiku 4.5 — cheapest accurate model ($1/$5 per MTok, ~$0.004/briefing).
# Per-endpoint upgrades (e.g. claude-sonnet-5 for premium deep dives) are a
# one-line env change: LLM_MODEL_DEFAULT / LLM_MODEL_<PURPOSE>.
DEFAULT_MODEL = os.getenv("LLM_MODEL_DEFAULT", "claude-haiku-4-5")

_API_KEY = os.getenv("ANTHROPIC_API_KEY")
_client: AsyncAnthropic | None = AsyncAnthropic(api_key=_API_KEY) if _API_KEY else None

# Injected into every call. This is the guardrail that keeps the model from
# inventing data: it may only restate/explain what the backend computed.
SYSTEM_GUARDRAIL = (
    "You are the narrative layer of TradeBotics, a stock-analysis platform. "
    "STRICT RULES: Use ONLY the numbers and facts provided in the prompt. "
    "Never invent prices, indicator values, dates, or statistics. "
    "If a value you need is missing, explicitly say it is unavailable instead of guessing. "
    "All output is educational analysis, not financial advice."
)


def llm_available() -> bool:
    return _client is not None


def get_model(purpose: str | None = None) -> str:
    """Resolve the model for an endpoint, e.g. LLM_MODEL_DEEP_DIVE overrides."""
    if purpose:
        override = os.getenv(f"LLM_MODEL_{purpose.upper()}")
        if override:
            return override
    return DEFAULT_MODEL


async def generate_text(
    prompt: str,
    system_extra: str = "",
    max_tokens: int = 1024,
    purpose: str | None = None,
) -> str | None:
    """Generate a narrative from supplied data. Returns None when the LLM is
    unavailable or declined, so callers can fall back gracefully."""
    if _client is None:
        return None
    system = SYSTEM_GUARDRAIL + (("\n" + system_extra) if system_extra else "")
    try:
        response = await _client.messages.create(
            model=get_model(purpose),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"[LLM ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        return None

    if response.stop_reason == "refusal":
        print("[LLM] request refused by safety system", file=sys.stderr)
        return None

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text or None
