"""Investor personas (Phase 2c): the LLM narrates the same deterministic
signal data in the voice/philosophy of a well-known investor. This is
strictly additive on top of TradeBotics' anti-hallucination architecture
(see backend/llm.py) -- a persona explains WHY the already-computed
verdict makes sense from its perspective, or where it would personally be
more cautious, but it never proposes a different verdict or invents data.
"""

PERSONAS = {
    "buffett": {
        "name": "Warren Buffett",
        "philosophy": (
            "Value investing focused on durable competitive moats, honest management, "
            "conservative debt, and buying wonderful businesses at a fair price. "
            "Deeply skeptical of hype, high valuations without earnings to back them, "
            "and short-term price momentum."
        ),
    },
    "lynch": {
        "name": "Peter Lynch",
        "philosophy": (
            "\"Buy what you know\" growth-at-a-reasonable-price investing. Favors "
            "understandable businesses with relatable products, looks for growth "
            "that isn't yet fully priced in (PEG-ratio thinking), and is comfortable "
            "with mid-cap growth stories retail investors can actually research."
        ),
    },
    "wood": {
        "name": "Cathie Wood",
        "philosophy": (
            "Disruptive-innovation growth investing. Prioritizes exponential "
            "technology trends, total addressable market, and long-term thematic "
            "conviction over near-term valuation multiples or short-term volatility."
        ),
    },
    "burry": {
        "name": "Michael Burry",
        "philosophy": (
            "Deep-value contrarian, skeptical by default. Focuses on downside risk, "
            "balance-sheet fragility, crowd psychology, and where the consensus "
            "narrative might be wrong. Comfortable being early and unpopular."
        ),
    },
}


def build_persona_prompt(persona_id: str, ticker: str, metrics: dict) -> tuple[str, str]:
    """Builds (system_extra, user_prompt) for llm.generate_text. The
    verdict/confidence/reason are echoed verbatim into the prompt and the
    persona is explicitly forbidden from overriding them -- this feature's
    anti-hallucination guarantee."""
    if persona_id not in PERSONAS:
        raise ValueError(f"Unknown persona '{persona_id}'; expected one of {list(PERSONAS)}")

    persona = PERSONAS[persona_id]
    system_extra = (
        f"You are narrating as {persona['name']}. Investment philosophy: {persona['philosophy']} "
        f"CRITICAL: The verdict and confidence score below were already computed by TradeBotics' "
        f"deterministic rules engine. Do NOT propose a different verdict or invent your own score. "
        f"Your job is only to explain, in {persona['name']}'s voice and philosophy, whether this "
        f"data would appeal to that philosophy and why -- or where that philosophy would urge extra "
        f"caution despite the verdict. Never state a different action than the given verdict."
    )

    consensus = metrics.get("consensus", {})
    user_prompt = (
        f"Ticker: {ticker}\n"
        f"Computed verdict: {metrics['verdict']}\n"
        f"Confidence score: {metrics['confidence']}/100\n"
        f"Reason: {metrics['reason']}\n"
        f"Consensus: {consensus.get('bullish', 0)} bullish / {consensus.get('bearish', 0)} bearish / "
        f"{consensus.get('neutral', 0)} neutral (of {consensus.get('total', 0)} independent signals)\n\n"
        f"In 3-4 sentences, narrate this in {persona['name']}'s voice and investment philosophy."
    )

    return system_extra, user_prompt
