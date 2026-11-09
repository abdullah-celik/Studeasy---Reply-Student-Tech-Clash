import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from app import llm
from app.agents.orchestrator import Route
from app.config import Settings, get_settings

BASE = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_x"}


@pytest.fixture
def provider(monkeypatch):
    """Rebuild settings and cached models for the given provider."""

    def use(name: str, **env: str):
        for k, v in {**BASE, "LLM_PROVIDER": name, **env}.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()
        llm._model.cache_clear()
        llm._mistral_chat.cache_clear()
        llm._cloudflare_chat.cache_clear()
        llm.embeddings.cache_clear()
        llm._throttle.cache_clear()
        return get_settings()

    yield use
    get_settings.cache_clear()
    llm._model.cache_clear()
    llm._mistral_chat.cache_clear()
    llm._cloudflare_chat.cache_clear()
    llm.embeddings.cache_clear()
    llm._throttle.cache_clear()


def test_cloudflare_is_the_default_and_uses_1024_vectors(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    for k, v in BASE.items():
        monkeypatch.setenv(k, v)
    s = Settings(_env_file=None)
    assert s.llm_provider == "cloudflare"
    assert s.vector_size == 1024
    assert s.chat_model_name.startswith("@cf/")


@pytest.mark.parametrize(
    ("name", "env", "missing"),
    [
        ("cloudflare", {"CLOUDFLARE_API_TOKEN": ""}, "CLOUDFLARE_API_TOKEN"),
        ("mistral", {"MISTRAL_API_KEY": ""}, "MISTRAL_API_KEY"),
        ("openai", {"OPENAI_API_KEY": ""}, "OPENAI_API_KEY"),
    ],
)
def test_missing_provider_key_fails_clearly(monkeypatch, name, env, missing):
    for k, v in {**BASE, "LLM_PROVIDER": name, **env}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValidationError, match=missing):
        Settings(_env_file=None)


def test_cloudflare_uses_its_openai_compatible_endpoint(provider):
    provider("cloudflare", CLOUDFLARE_ACCOUNT_ID="acct123", CLOUDFLARE_API_TOKEN="cf-test")
    chat = llm.chat_model()
    assert chat.model_name == "@cf/meta/llama-4-scout-17b-16e-instruct"
    assert chat.openai_api_base == "https://api.cloudflare.com/client/v4/accounts/acct123/ai/v1"
    p = chat._get_request_payload([HumanMessage("hi")])
    assert "reasoning_effort" not in p and "stream_options" not in p
    assert llm.chat_model("@cf/zai-org/glm-4.7-flash").model_name == "@cf/zai-org/glm-4.7-flash"
    emb = llm.embeddings()
    assert emb.model == "@cf/baai/bge-m3"
    assert emb.check_embedding_ctx_length is False


def test_friendly_message_when_daily_allowance_is_used_up():
    err = RuntimeError("4006: you have used up your daily free allocation of 10,000 neurons")
    assert "resets every day" in llm.ai_error_message(err)
    assert llm.ai_error_message(ValueError("boom")) is None


def test_mistral_models_share_one_throttle(provider):
    provider("mistral", MISTRAL_API_KEY="m-test")
    chat = llm.chat_model()
    assert chat.model == "mistral-small-latest"
    assert chat.rate_limiter is llm._throttle()
    emb = llm.embeddings()
    assert emb.model == "mistral-embed"


@pytest.mark.asyncio
async def test_mistral_embeddings_send_batches_one_by_one(provider, monkeypatch):
    provider("mistral", MISTRAL_API_KEY="m-test", MISTRAL_REQUESTS_PER_SECOND="1000")
    emb = llm.embeddings()
    calls: list[int] = []

    async def fake_parent(self, texts):
        calls.append(len(texts))
        return [[0.0] * 1024 for _ in texts]

    from langchain_mistralai import MistralAIEmbeddings

    monkeypatch.setattr(MistralAIEmbeddings, "aembed_documents", fake_parent)
    texts = ["x" * 6000] * 5  # 30k characters -> several batches of at most 16k
    out = await emb.aembed_documents(texts)
    assert len(out) == 5
    assert len(calls) > 1 and sum(calls) == 5


def test_openai_still_works_when_selected(provider):
    s = provider("openai", OPENAI_API_KEY="sk-test")
    assert s.vector_size == 1536
    p = llm.chat_model()._get_request_payload([HumanMessage("hi")])
    assert p["model"] == "gpt-6-luna"
    assert p["reasoning_effort"] == "low"
    assert "temperature" not in p
    bound = llm._model("none").bind_tools([Route], tool_choice="Route")
    p = bound.bound._get_request_payload([HumanMessage("hi")], **bound.kwargs)
    effort = p.get("reasoning", {}).get("effort") or p.get("reasoning_effort")
    assert effort == "none"


def test_rate_limit_detection():
    import httpx

    req = httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions")
    err = httpx.HTTPStatusError("busy", request=req, response=httpx.Response(429, request=req))
    assert llm.is_rate_limited(err)
    assert not llm.is_rate_limited(ValueError("x"))


def test_cloudflare_settings_accept_common_misspellings(monkeypatch):
    for k, v in BASE.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLAUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLAUDFLARE_API_TOKEN", "tok")
    s = Settings(_env_file=None)
    assert (s.cloudflare_account_id, s.cloudflare_api_token) == ("acct", "tok")
