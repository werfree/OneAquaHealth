"""One place that decides which model provider answers.

Every model call in the project -- the assistant's tool loop, the briefing
narrator, the studio, and the officer's report routes -- goes through here, so
"which provider" is a property of the environment rather than something baked
into four different `chat.completions.create` call sites.

Two providers are supported:

  * ``openai``  -- the OpenAI API (or any service that speaks its wire protocol).
  * ``ollama``  -- a local or self-hosted `Ollama <https://ollama.com>`_ server.

The choice is made by ``LLM_PROVIDER`` when it is set, and otherwise guessed
from the credentials present: an ``OPENAI_API_KEY`` selects OpenAI, and an
``OLLAMA_BASE_URL`` (or a reachable local Ollama) selects Ollama. Guessing is
deliberately second to saying so explicitly -- if both are configured, only
``LLM_PROVIDER`` breaks the tie.

Ollama exposes an OpenAI-compatible ``/v1`` endpoint and returns the identical
``chat.completions`` shape, including tool calls, so the loop code stays the
same and only the base URL and credentials differ.

    provider        base URL                  credential
    openai          $OPENAI_BASE_URL          $OPENAI_API_KEY    (required)
    ollama          $OLLAMA_BASE_URL          $OLLAMA_API_KEY    (optional)

Nothing here embeds a key.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("OAH_LLM")

DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_OLLAMA_MODEL = "deepseek-v4.1-flash:cloud"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

KNOWN_PROVIDERS = ("openai", "ollama")

# Accepted spellings, so `--provider local` or `LLM_PROVIDER=OLLAMA` both work.
_ALIASES = {
    "openai": "openai",
    "open-ai": "openai",
    "oa": "openai",
    "gpt": "openai",
    "ollama": "ollama",
    "local": "ollama",
    "self-hosted": "ollama",
    "selfhosted": "ollama",
    "on-prem": "ollama",
}

# The model to fall back on for each provider when nothing more specific is set.
DEFAULT_MODELS = {"openai": DEFAULT_OPENAI_MODEL, "ollama": DEFAULT_OLLAMA_MODEL}


def _normalize(provider: Optional[str]) -> Optional[str]:
    if not provider:
        return None
    return _ALIASES.get(provider.strip().lower())


def _resolve_provider(provider: Optional[str] = None) -> str:
    """Pick a provider: the caller, then ``LLM_PROVIDER``, then the environment."""

    explicit = _normalize(provider) or _normalize(os.getenv("LLM_PROVIDER"))
    if explicit:
        return explicit

    # No explicit choice: infer from what is configured. A key means OpenAI was
    # intended; an Ollama base URL (or an ollama model configured) means Ollama.
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_MODEL"):
        return "ollama"
    return "ollama"


def default_model(provider: Optional[str] = None) -> str:
    """The model to use when a call does not name one.

    ``OPENAI_MODEL`` / ``OLLAMA_MODEL`` win for their own provider; the generic
    ``LLM_MODEL`` wins when it is set and no provider-specific name is.
    """

    resolved = _resolve_provider(provider)
    specific = os.getenv("OLLAMA_MODEL") if resolved == "ollama" else os.getenv("OPENAI_MODEL")
    return specific or os.getenv("LLM_MODEL") or DEFAULT_MODELS[resolved]


def active_provider(provider: Optional[str] = None) -> str:
    """The provider a call would use, for display and for tests."""

    return _resolve_provider(provider)


def client(provider: Optional[str] = None):
    """Build an OpenAI-compatible client for the selected provider.

    Both branches return the ``openai.OpenAI`` type; for Ollama it is pointed at
    that server's OpenAI-compatible ``/v1`` endpoint, which is why the rest of
    the codebase can treat the two identically.
    """

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The assistant needs an OpenAI-compatible SDK: pip install openai") from exc

    resolved = _resolve_provider(provider)

    if resolved == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        # Ollama ignores the key, but the SDK insists on a truthy one.
        return OpenAI(base_url=f"{base_url}/v1", api_key=os.getenv("OLLAMA_API_KEY") or "ollama")

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env (gitignored), export it, or set "
            "LLM_PROVIDER=ollama to run against a local model instead."
        )
    # OPENAI_BASE_URL lets OpenAI's wire protocol be served by a proxy or a
    # compatible gateway without a code change.
    base_url = os.getenv("OPENAI_BASE_URL")
    return OpenAI(base_url=base_url) if base_url else OpenAI()


def _client(provider: Optional[str] = None):
    """Backwards-compatible alias; the studio and officer import `_client`."""

    return client(provider)


def describe(provider: Optional[str] = None, model: Optional[str] = None) -> str:
    """A one-line ``provider/model`` label, safe to show a user."""

    resolved = _resolve_provider(provider)
    return f"{resolved}/{model or default_model(resolved)}"


def json_completion(client, *, model: str, messages: list, **kwargs):
    """Ask a provider for a JSON object, degrading if it rejects the hint.

    OpenAI honours ``response_format={"type": "json_object"}``. Some Ollama
    models reject the parameter outright rather than ignoring it, which would
    fail an executive report over a hint the prompt already states. Retry once
    without it instead of losing the request.
    """

    try:
        return client.chat.completions.create(
            model=model, messages=messages, response_format={"type": "json_object"}, **kwargs
        )
    except Exception as exc:  # provider-specific rejection, not a transport failure
        if "response_format" not in str(exc).lower():
            raise
        logger.info("Provider rejected response_format; retrying without it")
        return client.chat.completions.create(model=model, messages=messages, **kwargs)

