import os

# Dummy settings so modules import without a real .env (no network calls are made in tests).
os.environ.setdefault("MISTRAL_API_KEY", "test")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test")
