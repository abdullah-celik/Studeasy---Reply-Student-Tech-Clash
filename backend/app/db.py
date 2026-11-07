from app.config import get_settings
from supabase import AsyncClient, acreate_client

_client: AsyncClient | None = None


def check_service_key(key: str) -> None:
    """Fail fast if the backend was given a public key: with it, reads silently return
    nothing and every write is rejected by Row Level Security."""
    import base64
    import json

    if key.startswith("sb_publishable_"):
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is the publishable (public) key. Use the secret key "
            "(sb_secret_...) or the legacy service_role key from Supabase > Project Settings > API Keys."
        )
    parts = key.split(".")
    if len(parts) == 3:  # legacy JWT key: check its role claim
        try:
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        except ValueError:
            return
        if payload.get("role") == "anon":
            raise RuntimeError(
                "SUPABASE_SERVICE_ROLE_KEY is the anon key. Use the service_role key instead."
            )


async def init_supabase() -> AsyncClient:
    """Create the shared service-role client once at startup."""
    global _client
    if _client is None:
        s = get_settings()
        check_service_key(s.supabase_service_role_key)
        _client = await acreate_client(s.supabase_url, s.supabase_service_role_key)
    return _client


def get_db() -> AsyncClient:
    if _client is None:
        raise RuntimeError("Supabase client not initialised; is the app lifespan running?")
    return _client
