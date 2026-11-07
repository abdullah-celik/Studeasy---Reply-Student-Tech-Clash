from app.config import get_settings
from supabase import AsyncClient, acreate_client

_client: AsyncClient | None = None


async def init_supabase() -> AsyncClient:
    """Create the shared service-role client once at startup."""
    global _client
    if _client is None:
        s = get_settings()
        _client = await acreate_client(s.supabase_url, s.supabase_service_role_key)
    return _client


def get_db() -> AsyncClient:
    if _client is None:
        raise RuntimeError("Supabase client not initialised; is the app lifespan running?")
    return _client
