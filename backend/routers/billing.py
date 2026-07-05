"""Billing endpoints (Phase 4): trial status, Stripe checkout, and the
Stripe webhook. Split out of main.py as the first extracted router.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from config import supabase, stripe, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID_PRO, FRONTEND_URL
from auth import get_current_user
from services import billing

router = APIRouter()


class CheckoutRequest(BaseModel):
    mode: str  # "subscription" | "payment" (token pack)
    price_id: str | None = None    # required for token packs (from Stripe dashboard)
    token_amount: int | None = None  # required for token packs


@router.get("/billing/status")
async def billing_status(user_id: str = Depends(get_current_user)):
    """Returns the caller's plan status, lazily granting a new signup's
    7-day trial + one-time token allotment on first call if not already
    initialized. Idempotent: only initializes when trial_ends_at is unset."""
    profile_res = supabase.table('profiles').select('plan,trial_ends_at,ai_token_balance').eq('id', user_id).execute()
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="Profile not found.")
    profile = profile_res.data[0]

    if not profile.get('trial_ends_at'):
        trial_ends_at = billing.new_trial_expiry()
        supabase.table('profiles').update({'trial_ends_at': trial_ends_at}).eq('id', user_id).execute()
        supabase.rpc('credit_tokens', {'p_user_id': user_id, 'p_amount': billing.TRIAL_TOKEN_GRANT}).execute()
        profile['trial_ends_at'] = trial_ends_at
        profile['ai_token_balance'] = profile.get('ai_token_balance', 0) + billing.TRIAL_TOKEN_GRANT

    return {
        "plan": profile.get('plan', 'free'),
        "plan_status": billing.plan_status(profile.get('plan', 'free'), profile.get('trial_ends_at')),
        "trial_ends_at": profile.get('trial_ends_at'),
        "ai_token_balance": profile.get('ai_token_balance'),
    }


@router.post("/billing/checkout")
async def create_checkout_session(req: CheckoutRequest, user_id: str = Depends(get_current_user)):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Billing is not configured yet.")
    try:
        params = billing.build_checkout_params(
            mode=req.mode, user_id=user_id, pro_price_id=STRIPE_PRICE_ID_PRO,
            success_url=f"{FRONTEND_URL}/billing/success", cancel_url=f"{FRONTEND_URL}/billing/cancel",
            token_price_id=req.price_id, token_amount=req.token_amount,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        session = stripe.checkout.Session.create(**params)
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook is not configured yet.")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {e}")

    parsed = billing.parse_webhook_event(event)

    already_processed = supabase.table('stripe_events').select('event_id').eq('event_id', parsed['event_id']).execute()
    if already_processed.data:
        return {"status": "already_processed"}

    if parsed['action'] == 'activate_subscription' and parsed['user_id']:
        supabase.table('profiles').update({
            'plan': 'pro', 'stripe_customer_id': parsed['customer_id'],
        }).eq('id', parsed['user_id']).execute()
    elif parsed['action'] == 'credit_tokens' and parsed['user_id'] and parsed['token_amount']:
        supabase.rpc('credit_tokens', {'p_user_id': parsed['user_id'], 'p_amount': parsed['token_amount']}).execute()
    elif parsed['action'] == 'deactivate_subscription' and parsed['customer_id']:
        supabase.table('profiles').update({'plan': 'free'}).eq('stripe_customer_id', parsed['customer_id']).execute()

    supabase.table('stripe_events').insert({'event_id': parsed['event_id'], 'event_type': parsed['event_type']}).execute()
    return {"status": "ok"}
