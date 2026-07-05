"""Unit tests for billing/trial access logic (Phase 4).

Model: 7-day reverse trial with a one-time token grant on signup. After the
trial, Beginner Top Picks / search verdict / Pro terminal deterministic
data stay free forever; AI/LLM-narrated features always require tokens
regardless of plan (Pro subscription does not grant unlimited AI -- it
only removes the post-trial platform restriction, if any is ever added).
"""
from datetime import datetime, timedelta, timezone

import pytest

from services import billing


def test_trial_active_when_within_window():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    trial_ends_at = (now + timedelta(days=3)).isoformat()
    assert billing.is_trial_active(trial_ends_at, now) is True


def test_trial_inactive_when_expired():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    trial_ends_at = (now - timedelta(days=1)).isoformat()
    assert billing.is_trial_active(trial_ends_at, now) is False


def test_trial_inactive_when_none():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    assert billing.is_trial_active(None, now) is False


def test_plan_status_trial():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    trial_ends_at = (now + timedelta(days=2)).isoformat()
    assert billing.plan_status(plan="free", trial_ends_at=trial_ends_at, now=now) == "trial"


def test_plan_status_pro_overrides_expired_trial():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    trial_ends_at = (now - timedelta(days=10)).isoformat()
    assert billing.plan_status(plan="pro", trial_ends_at=trial_ends_at, now=now) == "pro"


def test_plan_status_free_after_trial_expires():
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    trial_ends_at = (now - timedelta(days=1)).isoformat()
    assert billing.plan_status(plan="free", trial_ends_at=trial_ends_at, now=now) == "free"


def test_new_trial_expiry_is_seven_days_out():
    now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)
    expiry = billing.new_trial_expiry(now)
    assert expiry == (now + timedelta(days=7)).isoformat()


def test_trial_token_grant_is_positive():
    assert billing.TRIAL_TOKEN_GRANT > 0


# --- checkout session params (pure, no network) ------------------------------

def test_checkout_params_subscription_uses_pro_price_and_metadata():
    params = billing.build_checkout_params(
        mode="subscription", user_id="user-1", pro_price_id="price_pro123",
        success_url="https://app/success", cancel_url="https://app/cancel",
    )
    assert params["mode"] == "subscription"
    assert params["line_items"] == [{"price": "price_pro123", "quantity": 1}]
    assert params["client_reference_id"] == "user-1"
    assert params["metadata"] == {"user_id": "user-1", "kind": "subscription"}


def test_checkout_params_token_pack_carries_amount_in_metadata():
    params = billing.build_checkout_params(
        mode="payment", user_id="user-1", pro_price_id="price_pro123",
        success_url="https://app/success", cancel_url="https://app/cancel",
        token_price_id="price_tokens50", token_amount=50,
    )
    assert params["mode"] == "payment"
    assert params["line_items"] == [{"price": "price_tokens50", "quantity": 1}]
    assert params["metadata"] == {"user_id": "user-1", "kind": "token_pack", "token_amount": "50"}


def test_checkout_params_rejects_unknown_mode():
    with pytest.raises(ValueError):
        billing.build_checkout_params(
            mode="refund", user_id="user-1", pro_price_id="price_pro123",
            success_url="https://app/success", cancel_url="https://app/cancel",
        )


def test_checkout_params_token_pack_requires_price_and_amount():
    with pytest.raises(ValueError):
        billing.build_checkout_params(
            mode="payment", user_id="user-1", pro_price_id="price_pro123",
            success_url="https://app/success", cancel_url="https://app/cancel",
        )


# --- webhook event parsing (pure, no network) ---------------------------------

def test_parse_webhook_subscription_completed():
    event = {
        "id": "evt_1", "type": "checkout.session.completed",
        "data": {"object": {"customer": "cus_1", "client_reference_id": "user-1",
                             "metadata": {"user_id": "user-1", "kind": "subscription"}}},
    }
    result = billing.parse_webhook_event(event)
    assert result == {
        "event_id": "evt_1", "event_type": "checkout.session.completed",
        "action": "activate_subscription", "user_id": "user-1",
        "customer_id": "cus_1", "token_amount": None,
    }


def test_parse_webhook_token_pack_completed():
    event = {
        "id": "evt_2", "type": "checkout.session.completed",
        "data": {"object": {"customer": "cus_1", "client_reference_id": "user-1",
                             "metadata": {"user_id": "user-1", "kind": "token_pack", "token_amount": "50"}}},
    }
    result = billing.parse_webhook_event(event)
    assert result["action"] == "credit_tokens"
    assert result["token_amount"] == 50


def test_parse_webhook_subscription_cancelled():
    event = {
        "id": "evt_3", "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_1"}},
    }
    result = billing.parse_webhook_event(event)
    assert result["action"] == "deactivate_subscription"
    assert result["customer_id"] == "cus_1"


def test_parse_webhook_unhandled_event_type_is_noop():
    event = {"id": "evt_4", "type": "invoice.paid", "data": {"object": {}}}
    result = billing.parse_webhook_event(event)
    assert result["action"] == "noop"
