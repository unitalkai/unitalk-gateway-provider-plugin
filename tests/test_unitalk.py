"""Exercise the installed plugin through Hermes' provider discovery and runtime."""

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.fixture
def installed_provider(tmp_path, monkeypatch):
    home = tmp_path / "home"
    plugin_dir = home / "plugins" / "model-providers" / "unitalk"
    plugin_dir.mkdir(parents=True)
    plugin = Path(__file__).resolve().parents[1]
    for name in ("__init__.py", "plugin.yaml"):
        shutil.copy2(plugin / name, plugin_dir / name)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("UNITALK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    token = set_hermes_home_override(home)
    yield home
    reset_hermes_home_override(token)


@pytest.mark.parametrize(
    ("unitalk_key", "openai_key", "expected"),
    [("unitalk-secret", "openai-secret", "unitalk-secret"),
     (None, "openai-secret", "openai-secret"),
     ("unitalk-secret", None, "unitalk-secret")],
)
def test_runtime_uses_declared_key_precedence(installed_provider, monkeypatch, unitalk_key, openai_key, expected):
    if unitalk_key:
        monkeypatch.setenv("UNITALK_API_KEY", unitalk_key)
    if openai_key:
        monkeypatch.setenv("OPENAI_API_KEY", openai_key)
    from hermes_cli.runtime_provider import resolve_runtime_provider

    runtime = resolve_runtime_provider(requested="unitalk")
    assert runtime["provider"] == "unitalk"
    assert runtime["base_url"] == "https://llmgateway.unitalk.ai/v1"
    assert runtime["api_mode"] == "chat_completions"
    assert runtime["api_key"] == expected


def test_unitalk_key_takes_precedence_after_openai_fallback(installed_provider, monkeypatch):
    from hermes_cli.runtime_provider import resolve_runtime_provider

    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    assert resolve_runtime_provider(requested="unitalk")["api_key"] == "openai-secret"
    monkeypatch.setenv("UNITALK_API_KEY", "unitalk-secret")
    assert resolve_runtime_provider(requested="unitalk")["api_key"] == "unitalk-secret"


def test_profile_dotenv_key_takes_precedence(installed_provider, monkeypatch):
    from hermes_cli.runtime_provider import resolve_runtime_provider

    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    (installed_provider / ".env").write_text("UNITALK_API_KEY=unitalk-secret\n", encoding="utf-8")
    assert resolve_runtime_provider(requested="unitalk")["api_key"] == "unitalk-secret"


def test_missing_credentials_fail_closed(installed_provider):
    from hermes_cli.auth import AuthError
    from hermes_cli.runtime_provider import resolve_runtime_provider

    with pytest.raises(AuthError):
        resolve_runtime_provider(requested="unitalk")


def test_host_isolation_preserves_key_precedence(installed_provider, monkeypatch):
    (installed_provider / "config.yaml").write_text("plugins:\n  isolation: host\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    from hermes_cli.plugin_host_profiles import is_hosted_profile
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from providers import get_provider_profile

    assert is_hosted_profile(get_provider_profile("unitalk"))
    assert resolve_runtime_provider(requested="unitalk")["api_key"] == "openai-secret"
    monkeypatch.setenv("UNITALK_API_KEY", "unitalk-secret")
    assert resolve_runtime_provider(requested="unitalk")["api_key"] == "unitalk-secret"


def test_catalog_uses_bearer_auth(installed_provider):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("Authorization")))
            body = json.dumps({"data": [{"id": "unitalk-test-model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    from providers import get_provider_profile

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        profile = get_provider_profile("unitalk")
        models = profile.fetch_models(api_key="test-secret", base_url=f"http://127.0.0.1:{server.server_port}/v1")
        assert models == ["unitalk-test-model"]
        assert requests == [("/v1/models", "Bearer test-secret")]
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
