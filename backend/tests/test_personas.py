"""Unit tests for investor personas (Phase 2c). Personas must only narrate
already-computed deterministic data -- they never decide a verdict."""
import pytest

from services import personas


def test_persona_ids_are_stable_and_known():
    assert set(personas.PERSONAS.keys()) == {"buffett", "lynch", "wood", "burry"}


def test_each_persona_has_name_and_philosophy():
    for persona_id, persona in personas.PERSONAS.items():
        assert persona["name"]
        assert persona["philosophy"]


def test_build_persona_prompt_unknown_id_raises():
    with pytest.raises(ValueError):
        personas.build_persona_prompt("nobody", "AAPL", {"verdict": "BUY", "confidence": 80, "reason": "test"})


def test_build_persona_prompt_includes_deterministic_verdict_verbatim():
    metrics = {"verdict": "BUY", "confidence": 82.5, "reason": "Trend and momentum align.",
               "consensus": {"bullish": 4, "bearish": 0, "neutral": 1, "total": 5}}
    system_extra, user_prompt = personas.build_persona_prompt("buffett", "AAPL", metrics)

    assert "Warren Buffett" in system_extra
    assert "BUY" in user_prompt
    assert "82.5" in user_prompt
    assert "Trend and momentum align." in user_prompt


def test_build_persona_prompt_forbids_overriding_verdict():
    """The persona's system prompt must explicitly forbid changing the
    verdict -- this is the anti-hallucination guarantee for this feature."""
    metrics = {"verdict": "WAIT", "confidence": 40.0, "reason": "test", "consensus": {}}
    system_extra, _ = personas.build_persona_prompt("lynch", "MSFT", metrics)
    assert "do not" in system_extra.lower() or "never" in system_extra.lower()
    assert "verdict" in system_extra.lower()


def test_build_persona_prompt_different_personas_have_different_voice():
    metrics = {"verdict": "HOLD", "confidence": 55.0, "reason": "test", "consensus": {}}
    _, buffett_prompt = personas.build_persona_prompt("buffett", "AAPL", metrics)
    _, wood_prompt = personas.build_persona_prompt("wood", "AAPL", metrics)
    assert buffett_prompt != wood_prompt
