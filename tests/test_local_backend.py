"""Tests for the local (Ollama) research backend and its preflight.

Covers backend selection (cloud vs local switches), per-backend system-message
shaping, the RESEARCH_USE_LOCAL resolution, and the three preflight failure
modes — all mocked, so no network or real Ollama is needed.
"""

import pytest

import journal_bot.llm_client as lc
import journal_bot.settings as s
from journal_bot.research_agent import _resolve_local, _system_message


# --- fakes -----------------------------------------------------------------

class _FakeResp:
    def __init__(self, names):
        self._names = names

    def raise_for_status(self):
        pass

    def json(self):
        return {"models": [{"name": n} for n in self._names]}


class _FakeChatResp:
    def __init__(self, tool_calls):
        self.choices = [type("_Ch", (), {"message": type("_M", (), {"tool_calls": tool_calls})()})()]


class _Completions:
    def __init__(self, exc, tool_calls):
        self._exc = exc
        self._tool_calls = tool_calls

    def create(self, **kw):
        if self._exc:
            raise self._exc
        return _FakeChatResp(self._tool_calls)


class _FakeClient:
    """Fake Ollama client. By default the probe emits a tool call (capable)."""
    def __init__(self, exc=None, tool_calls=("call",)):
        tc = list(tool_calls) if tool_calls else None
        self.chat = type("_Chat", (), {"completions": _Completions(exc, tc)})()


@pytest.fixture(autouse=True)
def _reset_toolcall_cache(monkeypatch):
    monkeypatch.setattr(lc, "_TOOLCALL_CAPABLE", {})


def _patch_tags(monkeypatch, names=None, raise_exc=None):
    def fake_get(url, timeout=None):
        if raise_exc:
            raise raise_exc
        return _FakeResp(names or [])
    monkeypatch.setattr(lc.httpx, "get", fake_get)


# --- backend selection -----------------------------------------------------

def test_local_backend_switches(monkeypatch):
    monkeypatch.setattr(s, "MODEL_AGENT_LOCAL", "qwen3:8b")
    b = lc.build_research_backend(local=True)
    assert b.is_local
    assert b.model == "qwen3:8b"
    assert b.sends_cache_control is False
    assert b.extra_body == {}


def test_cloud_backend_switches(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")  # avoid key prompt
    monkeypatch.setattr(s, "MODEL_AGENT", "anthropic/claude-opus-4.6")
    b = lc.build_research_backend(local=False)
    assert b.is_local is False
    assert b.model == "anthropic/claude-opus-4.6"
    assert b.sends_cache_control is True
    assert b.extra_body == {"transforms": ["middle-out"]}


def test_explicit_model_overrides_default(monkeypatch):
    b = lc.build_research_backend(local=True, model="llama3.3:latest")
    assert b.model == "llama3.3:latest"


# --- system message shaping ------------------------------------------------

def test_system_message_local_is_plain_string():
    b = lc.build_research_backend(local=True)
    msg = _system_message("SYS", b)
    assert msg["role"] == "system"
    assert msg["content"] == "SYS"  # plain string, no cache_control block


def test_system_message_cloud_has_cache_control(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    b = lc.build_research_backend(local=False)
    msg = _system_message("SYS", b)
    assert isinstance(msg["content"], list)
    assert msg["content"][0]["cache_control"] == {"type": "ephemeral"}


# --- RESEARCH_USE_LOCAL resolution -----------------------------------------

def test_resolve_local_precedence(monkeypatch):
    monkeypatch.setattr(s, "RESEARCH_USE_LOCAL", True)
    assert _resolve_local(None) is True          # falls back to setting
    assert _resolve_local(False) is False         # explicit override wins
    monkeypatch.setattr(s, "RESEARCH_USE_LOCAL", False)
    assert _resolve_local(None) is False
    assert _resolve_local(True) is True


# --- preflight failure modes -----------------------------------------------

def test_preflight_server_down(monkeypatch):
    _patch_tags(monkeypatch, raise_exc=ConnectionError("refused"))
    ok, msg = lc.check_local_backend("mistral-nemo:latest")
    assert ok is False
    assert "nicht erreichbar" in msg


def test_preflight_model_missing(monkeypatch):
    _patch_tags(monkeypatch, names=["other-model:latest"])
    ok, msg = lc.check_local_backend("mistral-nemo:latest")
    assert ok is False
    assert "nicht vorhanden" in msg
    assert "ollama pull mistral-nemo:latest" in msg


def test_preflight_runner_broken(monkeypatch):
    _patch_tags(monkeypatch, names=["mistral-nemo:latest"])
    monkeypatch.setattr(lc, "build_ollama_client", lambda: _FakeClient(exc=RuntimeError("no llama-server")))
    ok, msg = lc.check_local_backend("mistral-nemo:latest")
    assert ok is False
    assert "lässt sich nicht ausführen" in msg
    assert "no llama-server" in msg


def test_preflight_ok(monkeypatch):
    _patch_tags(monkeypatch, names=["mistral-nemo:latest"])
    monkeypatch.setattr(lc, "build_ollama_client", lambda: _FakeClient())
    ok, msg = lc.check_local_backend("mistral-nemo:latest")
    assert ok is True
    assert msg == ""


def test_preflight_accepts_base_name_match(monkeypatch):
    # model pulled as a specific tag; request uses ':latest' — base name matches
    _patch_tags(monkeypatch, names=["mistral-nemo:12b-instruct"])
    monkeypatch.setattr(lc, "build_ollama_client", lambda: _FakeClient())
    ok, msg = lc.check_local_backend("mistral-nemo:latest")
    assert ok is True


def test_preflight_rejects_model_without_structured_toolcalls(monkeypatch):
    # runs fine, but emits no structured tool_calls (e.g. mistral-nemo on 0.12.x)
    _patch_tags(monkeypatch, names=["mistral-nemo:latest"])
    monkeypatch.setattr(lc, "build_ollama_client", lambda: _FakeClient(tool_calls=None))
    ok, msg = lc.check_local_backend("mistral-nemo:latest")
    assert ok is False
    assert "keine" in msg and "tool_calls" in msg


def test_preflight_caches_capability(monkeypatch):
    _patch_tags(monkeypatch, names=["qwen3:8b"])
    calls = {"n": 0}

    def counting_client():
        calls["n"] += 1
        return _FakeClient()

    monkeypatch.setattr(lc, "build_ollama_client", counting_client)
    assert lc.check_local_backend("qwen3:8b") == (True, "")
    assert lc.check_local_backend("qwen3:8b") == (True, "")
    assert calls["n"] == 1  # second call served from cache, no second probe


def test_list_local_models(monkeypatch):
    _patch_tags(monkeypatch, names=["qwen3:8b", "llama3.3:latest", "mistral-nemo:latest"])
    assert lc.list_local_models() == ["llama3.3:latest", "mistral-nemo:latest", "qwen3:8b"]


def test_list_local_models_returns_empty_on_error(monkeypatch):
    _patch_tags(monkeypatch, raise_exc=ConnectionError("down"))
    assert lc.list_local_models() == []
