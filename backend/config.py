"""Shared app configuration and module-level state: the Supabase client,
Stripe setup, in-memory caches, rate limiter, and CORS config. Split out of
main.py (Phase 4) so routers can import this instead of main itself.
"""
import os

import stripe
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from supabase import Client, create_client

load_dotenv()

# --- Stripe ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID_PRO = os.getenv("STRIPE_PRICE_ID_PRO")
FRONTEND_URL = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")[0].strip()
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# --- FastAPI app + middleware ---
app = FastAPI()

# Rate limiting on Claude-backed routes -- they cost real money per call.
# Per-IP (not per-user) for simplicity; a shared-IP false positive just
# means a retry, whereas an unthrottled route is a real cost/abuse risk.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
LLM_RATE_LIMIT = "10/minute"

# Explicit origins only. Set FRONTEND_ORIGINS on Render, e.g.:
# FRONTEND_ORIGINS=https://your-app.vercel.app,http://localhost:3000
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory caches ---
market_cache = {}
MARKET_CACHE_TTL = 60
SCREENER_CACHE = {}
TRACK_RECORD_CACHE = {}
TRACK_RECORD_CACHE_TTL = 3600  # public page; signals table only changes nightly

# --- Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        supabase = None
else:
    supabase = None

_HORIZON_BY_TRADE_STYLE = {"Day Trade": "day", "Long Term": "longterm"}
_DEFAULT_HORIZON = "swing"
_MAX_SCREENER_RESULTS = 10
