"""AI backendy generatoru.

- AnthropicBackend: Claude pres oficialni SDK `anthropic`. Klic z ANTHROPIC_API_KEY.
- OpenAICompatBackend: libovolny OpenAI-kompatibilni server (nas AI stroj),
  POST {base_url}/chat/completions. Jen standardni knihovna (urllib).
  Konfigurace: OPENAI_BASE_URL, OPENAI_API_KEY (volitelny), OPENAI_MODEL,
  OPENAI_EXTRA_BODY (volitelny JSON navic do pozadavku).

Oba maji metodu complete(system, user) -> (text, info).
Chyby: FatalBackendError (spatny klic/model -> zastavit davku),
       BackendError (docasna chyba / odmitnuti -> preskocit tento napad).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class BackendError(Exception):
    pass


class FatalBackendError(BackendError):
    pass


class AnthropicBackend:
    name = "anthropic"
    DEFAULT_MODEL = "claude-opus-5-5"

    def __init__(self, model=None, effort="medium", max_tokens=16000):
        import anthropic
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()          # ANTHROPIC_API_KEY z prostredi / .env
        self.model = model or self.DEFAULT_MODEL
        self.effort = effort
        self.max_tokens = max_tokens

    def complete(self, system, user):
        a = self._anthropic
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                # system prompt je pro celou davku stejny -> cache
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort},
                # pri odmitnuti bezpecnostnim filtrem zkusit server-side fallback model
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except (a.AuthenticationError, a.PermissionDeniedError, a.NotFoundError,
                a.BadRequestError) as e:
            raise FatalBackendError(f"Anthropic {e.status_code}: {e.message}") from e
        except a.RateLimitError as e:
            raise BackendError(f"Anthropic rate limit: {e.message}") from e
        except a.APIStatusError as e:
            raise BackendError(f"Anthropic {e.status_code}: {e.message}") from e
        except a.APIConnectionError as e:
            raise BackendError(f"Anthropic: chyba spojení: {e}") from e

        if resp.stop_reason == "refusal":
            cat = getattr(resp.stop_details, "category", None) if resp.stop_details else None
            raise BackendError(f"model odmítl požadavek (kategorie {cat})")
        if resp.stop_reason == "max_tokens":
            raise BackendError(f"odpověď useknutá na max_tokens={self.max_tokens}")
        text = "".join(b.text for b in resp.content if b.type == "text")
        u = resp.usage
        info = {
            "backend": self.name,
            "model": resp.model,
            "request_id": getattr(resp, "_request_id", None),
            "usage": {
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", None) or 0,
                "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", None) or 0,
            },
        }
        return text, info


class OpenAICompatBackend:
    name = "openai"

    def __init__(self, model=None, base_url=None, api_key=None, max_tokens=16000,
                 temperature=None, timeout=900, retries=2):
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
        if not self.base_url:
            raise FatalBackendError("chybí OPENAI_BASE_URL (např. http://ai-stroj:8000/v1)")
        self.model = model or os.environ.get("OPENAI_MODEL")
        if not self.model:
            raise FatalBackendError("chybí model: zadej --model nebo OPENAI_MODEL")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or ""
        host = urllib.parse.urlsplit(self.base_url).hostname or ""
        if (self.api_key and self.base_url.startswith("http://")
                and host not in ("localhost", "127.0.0.1", "::1")):
            print(f"VAROVÁNÍ: API klíč by šel nešifrovaně přes {self.base_url} – "
                  "použij https://", file=sys.stderr, flush=True)
        self.max_tokens = max_tokens
        # OPENAI_EXTRA_BODY: JSON pridany do kazdeho pozadavku, napr. vypnuti
        # premysleni u Qwen3: {"chat_template_kwargs": {"enable_thinking": false}}
        raw = os.environ.get("OPENAI_EXTRA_BODY", "").strip()
        try:
            self.extra_body = json.loads(raw) if raw else {}
        except ValueError as e:
            raise FatalBackendError(f"OPENAI_EXTRA_BODY není platný JSON: {e}") from e
        if not isinstance(self.extra_body, dict):
            raise FatalBackendError("OPENAI_EXTRA_BODY musí být JSON objekt {...}")
        self.temperature = temperature
        self.timeout = timeout
        self.retries = retries

    def _post(self, body):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(f"{self.base_url}/chat/completions",
                                     data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def complete(self, system, user):
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": self.max_tokens,
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        body.update(self.extra_body)

        for attempt in range(self.retries + 1):
            try:
                data = self._post(body)
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                if e.code in (400, 401, 403, 404):
                    raise FatalBackendError(f"{self.base_url}: HTTP {e.code}: {detail}") from e
                err = BackendError(f"{self.base_url}: HTTP {e.code}: {detail}")
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                err = BackendError(f"{self.base_url}: chyba spojení: {e}")
            except ValueError as e:
                err = BackendError(f"{self.base_url}: odpověď není JSON: {e}")
            if attempt == self.retries:
                raise err
            time.sleep(2 ** attempt * 2)

        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise BackendError(f"nečekaný tvar odpovědi: {str(data)[:300]}") from e
        if choice.get("finish_reason") == "length":
            raise BackendError(f"odpověď useknutá na max_tokens={self.max_tokens}")
        u = data.get("usage") or {}
        info = {
            "backend": self.name,
            "model": data.get("model") or self.model,
            "base_url": self.base_url,
            "usage": {"input_tokens": u.get("prompt_tokens"),
                      "output_tokens": u.get("completion_tokens")},
        }
        return text, info


def make_backend(name, model=None, effort="medium"):
    if name == "anthropic":
        return AnthropicBackend(model=model, effort=effort)
    if name == "openai":
        return OpenAICompatBackend(model=model)
    raise FatalBackendError(f"neznámý backend {name!r} (anthropic | openai)")
