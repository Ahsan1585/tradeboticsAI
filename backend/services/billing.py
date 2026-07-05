"""Billing/trial access logic (Phase 4).

Model (user-approved 2026-07-05): new signups get a 7-day full-access
"reverse trial" plus a one-time token grant. After the trial, Beginner
Top Picks / search verdict / Pro terminal deterministic data stay free
forever (near-zero marginal cost -- the nightly job runs once regardless
of viewer count). AI/LLM-narrated features (personas, deep-dive,
exit-strategy, portfolio-analysis) always require tokens, regardless of
plan -- a Pro subscription unlocks permanent full platform access but
deliberately does NOT grant unlimited AI, to keep variable LLM cost
bounded no matter how many users subscribe.
"""
from datetime import datetime, timedelta, timezone

TRIAL_DAYS = 7
TRIAL_TOKEN_GRANT = 50


def new_trial_expiry(now: datetime | None = None) -> str:
    """ISO timestamp for a new signup's trial expiry, TRIAL_DAYS out."""
    now = now or datetime.now(timezone.utc)
    return (now + timedelta(days=TRIAL_DAYS)).isoformat()


def is_trial_active(trial_ends_at: str | None, now: datetime | None = None) -> bool:
    if not trial_ends_at:
        return False
    now = now or datetime.now(timezone.utc)
    return datetime.fromisoformat(trial_ends_at) > now


def plan_status(plan: str, trial_ends_at: str | None, now: datetime | None = None) -> str:
    """One of 'pro' | 'trial' | 'free'. A paid plan always wins regardless
    of trial state; otherwise an active trial reads as full access."""
    if plan == "pro":
        return "pro"
    if is_trial_active(trial_ends_at, now):
        return "trial"
    return "free"


def has_full_platform_access(plan: str, trial_ends_at: str | None, now: datetime | None = None) -> bool:
    """True during an active trial or on a paid plan. Does NOT affect
    token-gated AI features, which are metered independently of plan."""
    return plan_status(plan, trial_ends_at, now) in ("pro", "trial")


def build_checkout_params(
    mode: str, user_id: str, pro_price_id: str, success_url: str, cancel_url: str,
    token_price_id: str | None = None, token_amount: int | None = None,
) -> dict:
    """Pure construction of Stripe Checkout Session kwargs -- no network
    call. `mode='subscription'` always uses the env-configured Pro price;
    `mode='payment'` (a token pack) requires the caller to supply which
    Stripe Price to charge and how many tokens it's worth, since token-pack
    products/prices are configured directly in the Stripe dashboard rather
    than hardcoded here."""
    if mode == "subscription":
        metadata = {"user_id": user_id, "kind": "subscription"}
        price_id = pro_price_id
    elif mode == "payment":
        if not token_price_id or not token_amount:
            raise ValueError("token_price_id and token_amount are required for a token-pack checkout.")
        metadata = {"user_id": user_id, "kind": "token_pack", "token_amount": str(token_amount)}
        price_id = token_price_id
    else:
        raise ValueError(f"Unknown checkout mode '{mode}'; expected 'subscription' or 'payment'.")

    return {
        "mode": mode,
        "line_items": [{"price": price_id, "quantity": 1}],
        "client_reference_id": user_id,
        "metadata": metadata,
        "success_url": success_url,
        "cancel_url": cancel_url,
    }


def parse_webhook_event(event: dict) -> dict:
    """Normalizes a Stripe event into {event_id, event_type, action,
    user_id, customer_id, token_amount}. Pure -- no network, no DB. The
    caller (main.py) applies the action idempotently against Supabase."""
    event_id = event["id"]
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata") or {}
        user_id = metadata.get("user_id") or obj.get("client_reference_id")
        kind = metadata.get("kind")
        if kind == "subscription":
            return {"event_id": event_id, "event_type": event_type, "action": "activate_subscription",
                    "user_id": user_id, "customer_id": obj.get("customer"), "token_amount": None}
        if kind == "token_pack":
            return {"event_id": event_id, "event_type": event_type, "action": "credit_tokens",
                    "user_id": user_id, "customer_id": obj.get("customer"),
                    "token_amount": int(metadata.get("token_amount", 0))}

    if event_type == "customer.subscription.deleted":
        return {"event_id": event_id, "event_type": event_type, "action": "deactivate_subscription",
                "user_id": None, "customer_id": obj.get("customer"), "token_amount": None}

    return {"event_id": event_id, "event_type": event_type, "action": "noop",
            "user_id": None, "customer_id": None, "token_amount": None}
