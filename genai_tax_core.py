"""
Core GenAI library for tax: send a tax situation description + instructions to the LLM, get full text response.
Single-shot only. No two-step; no schema filling (that is in tax_schema_filler).

- ask_llm(...) -> str  # tax, insights, schema filler: GenOS **chat/completions** (v3 HTTP) or Express **v2** — never /responses
- ask_llm_chat(...) -> str  # **chat UI only**: on v3 uses **POST .../v3/lt/{model}/responses**; on v2 same as Express v2
- get_tax_calculation_response(description, include_reference=True, ...) -> str  # build prompt (ref + description), call LLM, return entire output

Each GenOS request logs one line to stderr: ``[GenOS] ...`` (set ``DEBUG_GENOS_CALLS=0`` to silence).

Before each GenOS call, reloads repo-root .env (override) so GENOS_* and INTUIT_* match the file.
Aliases: INTUIT_EXPERIENCE_ID -> same as GENOS_EXPERIENCE_ID. IAM ticket: **INTUIT_IAM_TICKET** (copied internally for genosclient). Auth: **INTUIT_AUTH_ID** (legacy **INTUIT_USER_ID**).
Initial load also reads cwd and optional 1040Extract/tests .env.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent
_extract_env = _root.parent / "tax-advisory-toolkit" / "tools" / "1040Extract" / "tests" / ".env"
_TAXRULES_PATH = _root / "taxrules.md"

_DEFAULT_SYSTEM_PROMPT = "You are a tax form and tax calculation expert. Respond with clear, accurate tax analysis and numbers."


def _genos_calls_logging_enabled() -> bool:
    return os.getenv("DEBUG_GENOS_CALLS", "1").strip().lower() not in ("0", "false", "no")


def _log_genos_call(message: str) -> None:
    """One line per GenOS outbound call (stderr)."""
    if not _genos_calls_logging_enabled():
        return
    print(f"[GenOS] {message}", file=sys.stderr)


def _sync_intuit_env_aliases_for_genosclient() -> None:
    """
    Set **INTUIT_IAM_TICKET** in .env. genosclient reads the ticket from os.environ under
    the name INTUIT_TICKET, so when IAM is set we assign os.environ["INTUIT_TICKET"] from it
    (implementation detail—not a separate env var for you to set).

    Use **INTUIT_AUTH_ID** for metadata auth_id; if unset, **INTUIT_USER_ID** is copied to
    INTUIT_AUTH_ID (legacy name).
    """
    iam = (os.getenv("INTUIT_IAM_TICKET") or "").strip()
    if iam:
        os.environ["INTUIT_TICKET"] = iam
    if not (os.getenv("INTUIT_AUTH_ID") or "").strip():
        legacy_user = (os.getenv("INTUIT_USER_ID") or "").strip()
        if legacy_user:
            os.environ["INTUIT_AUTH_ID"] = legacy_user


def _reload_dotenv_from_repo_root() -> None:
    """Load project-air/.env (repo root) with override so GenOS and Intuit vars match the file on disk."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_root / ".env", override=True)
        load_dotenv(Path.cwd() / ".env", override=True)
    except ImportError:
        pass
    except Exception:
        pass
    _sync_intuit_env_aliases_for_genosclient()


# Initial load (optional 1040Extract for other tools)
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
    load_dotenv(Path.cwd() / ".env")
    if _extract_env.exists():
        load_dotenv(_extract_env, override=True)
except ImportError:
    pass
except Exception:
    pass

_sync_intuit_env_aliases_for_genosclient()

# Optional: tax reference block (all years/statuses) for prompt
try:
    from calc_total_tax import get_tax_reference_text_all
except ImportError:
    get_tax_reference_text_all = None  # type: ignore[assignment]

def _get_genos_env() -> dict[str, str]:
    """Read GenOS settings from repo .env only (no hardcoded IDs in code). Reloads .env each call."""
    _reload_dotenv_from_repo_root()
    experience_id = (
        (os.getenv("GENOS_EXPERIENCE_ID") or os.getenv("INTUIT_EXPERIENCE_ID") or "").strip()
    )
    return {
        "experience_id": experience_id,
        "asset_alias": (os.getenv("GENOS_ASSET_ALIAS") or "").strip(),
        "env": (os.getenv("GENOS_ENV") or "").strip(),
        "model_id": (os.getenv("GENOS_MODEL_ID") or "").strip(),
    }


# Snapshot at import (for scripts that read these without calling GenOS)
_g = _get_genos_env()
GENOS_EXPERIENCE_ID = _g["experience_id"]
GENOS_ASSET_ALIAS = _g["asset_alias"]
GENOS_ENV = _g["env"]
GENOS_MODEL_ID = _g["model_id"]

try:
    from genosclient.genos_client import build_headers
    from genosclient import ApiClient, ExpressModeApi, ExpressModeV2RequestMessage
    from genosclient.api.llm_models import get_llm_model_names
    _GENOS_CLIENT_AVAILABLE = True
except ImportError:
    get_llm_model_names = None  # type: ignore[assignment]
    _GENOS_CLIENT_AVAILABLE = False


def _genos_available() -> bool:
    if not _GENOS_CLIENT_AVAILABLE:
        return False
    cfg = _get_genos_env()
    return bool(
        cfg["experience_id"]
        and cfg["asset_alias"]
        and cfg["env"]
        and cfg["model_id"]
    )


def _genos_env_requirements_message() -> str:
    """Non-secret hint listing missing GenOS variables expected in `.env`."""
    _reload_dotenv_from_repo_root()
    missing: list[str] = []
    if not (os.getenv("GENOS_EXPERIENCE_ID") or os.getenv("INTUIT_EXPERIENCE_ID") or "").strip():
        missing.append("GENOS_EXPERIENCE_ID (or INTUIT_EXPERIENCE_ID)")
    if not (os.getenv("GENOS_ASSET_ALIAS") or "").strip():
        missing.append("GENOS_ASSET_ALIAS")
    if not (os.getenv("GENOS_ENV") or "").strip():
        missing.append("GENOS_ENV")
    if not (os.getenv("GENOS_MODEL_ID") or "").strip():
        missing.append("GENOS_MODEL_ID")
    if not missing:
        return ""
    return "Missing in .env: " + ", ".join(missing)


def _genos_metadata() -> dict[str, Any]:
    cfg = _get_genos_env()
    metadata: dict[str, Any] = {
        "env": cfg["env"],
        "intuit_originating_assetalias": cfg["asset_alias"],
    }
    if os.getenv("INTUIT_APP_ID"):
        metadata["app_id"] = os.getenv("INTUIT_APP_ID")
    else:
        metadata["app_id"] = cfg["asset_alias"]
    app_secret = os.getenv("INTUIT_APP_SECRET")
    if app_secret:
        metadata["app_secret"] = app_secret
    auth_id = os.getenv("INTUIT_AUTH_ID") or os.getenv("INTUIT_USER_ID")
    if auth_id:
        metadata["auth_id"] = auth_id
    ticket = os.getenv("INTUIT_IAM_TICKET")
    if ticket:
        metadata["ticket"] = ticket
    return metadata


def get_genos_credentials_summary() -> str:
    """Return a one-line summary of which GenOS credential env vars are set (no secret values)."""
    cfg = _get_genos_env()
    app_id = "INTUIT_APP_ID" if os.getenv("INTUIT_APP_ID") else f"GENOS_ASSET_ALIAS ({cfg['asset_alias']})"
    parts = [
        f"experience_id={cfg['experience_id']}",
        f"asset_alias={cfg['asset_alias']}",
        f"app_id={app_id}",
    ]
    for name in ("INTUIT_APP_SECRET",):
        parts.append(f"{name}={('set' if os.getenv(name) else 'not set')}")
    auth_set = os.getenv("INTUIT_AUTH_ID") or os.getenv("INTUIT_USER_ID")
    parts.append(f"INTUIT_AUTH_ID={'set' if auth_set else 'not set'}")
    tick = os.getenv("INTUIT_IAM_TICKET")
    parts.append(f"INTUIT_IAM_TICKET={'set' if tick else 'not set'}")
    return "GenOS credentials: " + ", ".join(parts)


# GPT-5 models listed here use Express v2; other gpt-5* ids still auto-route to v3.
_GENOS_GPT5_V2_MODEL_IDS = frozenset(
    {
        "gpt-5-2025-08-07",
        "gpt-5-2025-08-07-oai",
    }
)
# Long tax write-ups need a high ceiling; 5000 was truncating mid-sentence.
_GENOS_MAX_OUTPUT_TOKENS = int(os.getenv("GENOS_MAX_OUTPUT_TOKENS", "32000"))
_GENOS_V3_BASE_URLS = {
    "e2e": "https://llmexecution-e2e.api.intuit.com/v3",
    "qal": "https://llmexecution-qal.api.intuit.com/v3",
    "prf": "https://llmexecution-prf.api.intuit.com/v3",
}


def _use_genos_v3() -> bool:
    _reload_dotenv_from_repo_root()
    return os.getenv("GENOS_USE_V3", "").strip().lower() in ("1", "true", "yes")


def _genos_model_requires_v3(model_id: str) -> bool:
    """Use Express v3 for most GPT-5; exceptions in _GENOS_GPT5_V2_MODEL_IDS stay on v2."""
    m = (model_id or "").strip().lower()
    if m.startswith("gpt-5"):
        if m in _GENOS_GPT5_V2_MODEL_IDS:
            return False
        return True
    return False


def get_resolved_genos_llm_line() -> str:
    """
    One line for CLI/logging: resolved model id, env source, GenOS tier, and v2 vs v3 path.
    Reloads .env first (same as GenOS calls).
    """
    _reload_dotenv_from_repo_root()
    cfg = _get_genos_env()
    model_id = cfg["model_id"]
    source = "GENOS_MODEL_ID from .env" if os.getenv("GENOS_MODEL_ID") else "unset (set GENOS_MODEL_ID in .env)"
    use_v3 = _use_genos_v3() or _genos_model_requires_v3(model_id)
    tier = "v3/chat-completions" if use_v3 else "v2 Express"
    return (
        f"LLM: model={model_id!r} ({source}), GenOS env={cfg['env']!r}, API={tier} "
        f"(tax & insights). Chat UI: ask_llm_chat() -> v3/lt/{{model}}/responses only."
    )


def _response_to_dict(obj: Any) -> Any:
    """Convert response object to JSON-serializable dict (Pydantic models, etc.)."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return {k: _response_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_response_to_dict(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _print_response_metadata(data: dict[str, Any] | Any, headers: dict[str, str] | None = None) -> None:
    """Print full API response (transaction_id, request_id, headers, body, etc.) to stderr."""
    out: dict[str, Any] = {}
    if headers:
        h = dict(headers)
        out["response_headers"] = {k: v for k, v in h.items() if k.lower().startswith(("x-", "intuit-"))}
    payload = _response_to_dict(data) if not isinstance(data, dict) else data
    if isinstance(payload, dict):
        # Deep copy and truncate long content in choices for readability (don't mutate original)
        payload = copy.deepcopy(payload)
        for key in ("choices", "llm_output"):
            val = payload.get(key)
            if isinstance(val, list) and val:
                for i, c in enumerate(val):
                    if isinstance(c, dict):
                        msg = c.get("message")
                        if isinstance(msg, dict) and "content" in msg and isinstance(msg["content"], str) and len(msg["content"]) > 500:
                            msg = dict(msg)
                            msg["content"] = msg["content"][:500] + f"... [truncated, total {len(msg['content'])} chars]"
                            c = dict(c)
                            c["message"] = msg
                            val = list(val)
                            val[i] = c
                payload[key] = val
    out["response_body"] = payload
    try:
        printed = json.dumps(out, indent=2, default=str)
        print("\n" + "=" * 60 + " API RESPONSE METADATA " + "=" * 60, file=sys.stderr)
        print(printed, file=sys.stderr)
        print("=" * 60 + " END RESPONSE METADATA " + "=" * 60 + "\n", file=sys.stderr)
    except Exception as e:
        print(f"[print_response_metadata] Could not serialize: {e}", file=sys.stderr)


def _genos_v3_temperature(model_id: str, requested: float = 0.0) -> float:
    """
    GenOS: gpt-5 family (incl. gpt-5.4, gpt-5-codex) only supports temperature=1 unless the model
    is gpt-5.1*, where other values work with reasoning_effort='none'. Sending temperature=0.1
    for gpt-5.4 etc. returns 400 UnsupportedParamsError.
    """
    m = (model_id or "").strip().lower()
    if m.startswith("gpt-5.1"):
        return float(requested)
    if m.startswith("gpt-5"):
        return 1.0
    return float(requested)


def _genos_v3_extra_body_params(model_id: str, temperature: float) -> dict[str, Any]:
    """Chat-completions extras (e.g. reasoning_effort) required for some OpenAI-style models on GenOS v3."""
    m = (model_id or "").strip().lower()
    if m.startswith("gpt-5.1") and temperature != 1.0:
        return {"reasoning_effort": "none"}
    return {}


def _responses_api_tools_from_env() -> list[dict[str, Any]] | None:
    """Optional JSON array for `tools` (e.g. web_search_preview). Omit if unset or invalid."""
    raw = (os.getenv("GENOS_RESPONSES_TOOLS") or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def _extract_text_from_responses_api_body(data: Any) -> str | None:
    """Best-effort extract assistant text from GenOS /responses JSON (shapes vary by gateway version)."""
    if isinstance(data, str) and data.strip():
        return data.strip()
    if not isinstance(data, dict):
        return None
    for key in ("output_text", "text", "response"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        c0 = choices[0]
        if isinstance(c0, dict):
            msg = c0.get("message") or {}
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    out = data.get("output")
    if isinstance(out, list):
        for item in out:
            if not isinstance(item, dict):
                continue
            cont = item.get("content")
            if isinstance(cont, list):
                for block in cont:
                    if isinstance(block, dict):
                        if block.get("type") == "output_text":
                            t = block.get("text")
                            if isinstance(t, str) and t.strip():
                                return t.strip()
                        if isinstance(block.get("text"), str) and block["text"].strip():
                            return str(block["text"]).strip()
            nested = _extract_text_from_responses_api_body(item)
            if nested:
                return nested
    llm = data.get("llm_output")
    if isinstance(llm, dict):
        nested = _extract_text_from_responses_api_body(llm)
        if nested:
            return nested
    return None


def _call_genos_v3_responses(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    system_prompt: str | None = None,
    *,
    max_completion_tokens: int | None = None,
) -> str | None:
    """
    GenOS v3 OpenAI-style Responses API: POST {base}/lt/{model_id}/responses
    Body: { "input": "<string>", "tools": [...] } — tools optional (see GENOS_RESPONSES_TOOLS).
    """
    if not _genos_available():
        return None
    try:
        import requests
    except ImportError:
        return None
    cfg = _get_genos_env()
    model_id = model or cfg["model_id"]
    base = _GENOS_V3_BASE_URLS.get(cfg["env"].lower(), _GENOS_V3_BASE_URLS["e2e"])
    url = f"{base}/lt/{model_id}/responses"
    headers = build_headers(_genos_metadata())
    headers["Content-Type"] = "application/json"
    headers["intuit_experience_id"] = cfg["experience_id"]
    system_content = system_prompt if system_prompt is not None else _DEFAULT_SYSTEM_PROMPT
    combined_input = (
        f"{system_content}\n\n---\n\n{prompt}" if system_content else prompt
    ).strip()
    payload: dict[str, Any] = {"input": combined_input}
    tools = _responses_api_tools_from_env()
    if tools:
        payload["tools"] = tools
    # Some deployments accept generation limits on responses; include only if env asks (optional extension).
    mt = max_completion_tokens if max_completion_tokens is not None else _GENOS_MAX_OUTPUT_TOKENS
    if mt and os.getenv("GENOS_RESPONSES_SEND_MAX_TOKENS", "").strip().lower() in ("1", "true", "yes"):
        payload["max_output_tokens"] = min(max(mt, 1), _GENOS_MAX_OUTPUT_TOKENS)
    temp = _genos_v3_temperature(model_id, temperature)
    if os.getenv("GENOS_RESPONSES_SEND_TEMPERATURE", "").strip().lower() in ("1", "true", "yes"):
        payload["temperature"] = temp
    try:
        _log_genos_call(f"POST {url} (responses API, chat only)")
        r = requests.post(url, json=payload, headers=headers, timeout=180)
        if not r.ok:
            try:
                body = r.json()
                _print_response_metadata(body, dict(r.headers))
                llm_out = body.get("llm_output") or {}
                cause = llm_out.get("cause") or llm_out.get("error_message") or body.get("cause") or r.text
            except Exception:
                body = {"raw_text": r.text[:2000] if r.text else None, "status_code": r.status_code}
                _print_response_metadata(body, dict(r.headers))
                cause = r.text or r.reason
            print(get_genos_credentials_summary(), file=sys.stderr)
            raise ValueError(f"GenOS v3 /responses returned {r.status_code}: {cause}")
        data = r.json()
        _print_response_metadata(data, dict(r.headers))
        text = _extract_text_from_responses_api_body(data)
        if text:
            return text
        return None
    except ValueError:
        raise
    except Exception as e:
        print(f"GenOS v3 /responses call failed: {e}", file=sys.stderr)
        raise ValueError(f"GenOS v3 /responses call failed: {e}") from e


def _call_genos_v3_chat_completions(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    system_prompt: str | None = None,
    *,
    max_completion_tokens: int | None = None,
) -> str | None:
    if not _genos_available():
        return None
    try:
        import requests
    except ImportError:
        return None
    cfg = _get_genos_env()
    model_id = model or cfg["model_id"]
    base = _GENOS_V3_BASE_URLS.get(cfg["env"].lower(), _GENOS_V3_BASE_URLS["e2e"])
    url = f"{base}/{model_id}/chat/completions"
    headers = build_headers(_genos_metadata())
    headers["Content-Type"] = "application/json"
    headers["intuit_experience_id"] = cfg["experience_id"]
    system_content = system_prompt if system_prompt is not None else _DEFAULT_SYSTEM_PROMPT
    temp = _genos_v3_temperature(model_id, temperature)
    mt = max_completion_tokens if max_completion_tokens is not None else _GENOS_MAX_OUTPUT_TOKENS
    if mt < 1:
        mt = 1
    if mt > _GENOS_MAX_OUTPUT_TOKENS:
        mt = _GENOS_MAX_OUTPUT_TOKENS
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ],
        "temperature": temp,
        "max_tokens": mt,
    }
    payload.update(_genos_v3_extra_body_params(model_id, temp))
    try:
        _log_genos_call(f"POST {url} (chat/completions, tax & insights)")
        r = requests.post(url, json=payload, headers=headers, timeout=120)
        if not r.ok:
            try:
                body = r.json()
                _print_response_metadata(body, dict(r.headers))
                llm_out = body.get("llm_output") or {}
                cause = llm_out.get("cause") or llm_out.get("error_message") or body.get("cause") or r.text
            except Exception:
                body = {"raw_text": r.text[:2000] if r.text else None, "status_code": r.status_code}
                _print_response_metadata(body, dict(r.headers))
                cause = r.text or r.reason
            print(get_genos_credentials_summary(), file=sys.stderr)
            raise ValueError(
                f"GenOS v3 returned {r.status_code}: {cause}"
            )
        data = r.json()
        _print_response_metadata(data, dict(r.headers))
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
            if isinstance(msg, dict):
                content = msg.get("content")
            else:
                content = getattr(msg, "content", None) if msg else None
            if content:
                return (content if isinstance(content, str) else str(content)).strip()
        return None
    except ValueError:
        raise
    except Exception as e:
        print(f"GenOS v3 call failed: {e}", file=sys.stderr)
        raise ValueError(f"GenOS v3 call failed: {e}") from e


def _call_genos_v3(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    system_prompt: str | None = None,
    *,
    max_completion_tokens: int | None = None,
    use_responses_api: bool = False,
) -> str | None:
    """v3 HTTP: chat/completions (default) or /responses when use_responses_api=True (chat only)."""
    if use_responses_api:
        return _call_genos_v3_responses(
            prompt,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
        )
    return _call_genos_v3_chat_completions(
        prompt,
        model=model,
        temperature=temperature,
        system_prompt=system_prompt,
        max_completion_tokens=max_completion_tokens,
    )


def _call_genos(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    system_prompt: str | None = None,
    *,
    max_completion_tokens: int | None = None,
    use_responses_api: bool = False,
) -> str | None:
    if not _genos_available():
        return None
    cfg = _get_genos_env()
    model_id = model or cfg["model_id"]
    # V3: env flag or GPT-5 except ids in _GENOS_GPT5_V2_MODEL_IDS (e.g. gpt-5-2025-08-07 on v2)
    if _use_genos_v3() or _genos_model_requires_v3(model_id):
        return _call_genos_v3(
            prompt,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            use_responses_api=use_responses_api,
        )
    if use_responses_api:
        _log_genos_call(
            f"Express v2 achat_completion_v2 model={model_id!r} (responses API not available on v2; using v2 chat)"
        )
    else:
        _log_genos_call(f"Express v2 achat_completion_v2 model={model_id!r} (tax & insights)")
    headers = build_headers(_genos_metadata())
    system_content = system_prompt if system_prompt is not None else _DEFAULT_SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt},
    ]
    model_params = {"temperature": 0, "max_tokens": _GENOS_MAX_OUTPUT_TOKENS}

    async def _request():
        async with ApiClient(is_async=True) as api_client:
            api_instance = ExpressModeApi(api_client)
            response = await api_instance.achat_completion_v2(
                model_id=model_id,
                intuit_experience_id=cfg["experience_id"],
                express_mode_v2_request_message=ExpressModeV2RequestMessage(
                    llm_input={
                        "messages": messages,
                        "model_parameters": model_params,
                    }
                ),
                _headers=headers,
            )
            _print_response_metadata(_response_to_dict(response))
            if hasattr(response, "llm_output") and hasattr(response.llm_output, "choices") and response.llm_output.choices:
                return response.llm_output.choices[0].message.content
            if hasattr(response, "choices") and response.choices:
                return response.choices[0].message.content
            if hasattr(response, "content"):
                return response.content
            return None

    try:
        return asyncio.run(_request())
    except Exception as e:
        print(f"GenOS call failed: {e}", file=sys.stderr)
        return None


def ask_llm(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.1,
    print_prompt: bool = False,
    system_prompt: str | None = None,
    max_completion_tokens: int | None = None,
    use_responses_api: bool = False,
) -> str:
    """
    Send a prompt to the LLM via GenOS. Tax, ITA insights, schema filler: **always** chat/completions on v3
    or Express v2 — set ``use_responses_api=False`` (default). For chat UI, use :func:`ask_llm_chat` instead.

    max_completion_tokens: when set, caps GenOS v3 `max_tokens` (defaults to GENOS_MAX_OUTPUT_TOKENS).
    """
    if print_prompt:
        print("\n" + "=" * 60 + " PROMPT SENT TO LLM " + "=" * 60, file=sys.stderr)
        print(prompt, file=sys.stderr)
        print("=" * 60 + " END PROMPT " + "=" * 60 + "\n", file=sys.stderr)
    if not _genos_available():
        hint = _genos_env_requirements_message()
        raise ValueError(
            "GenOS is not configured. "
            + (hint + " " if hint else "")
            + "Install genosclient and set all GenOS / Intuit variables in `.env` only (no hardcoded IDs in code)."
        )
    try:
        out = _call_genos(
            prompt,
            model=model or _get_genos_env()["model_id"],
            temperature=temperature,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
            use_responses_api=use_responses_api,
        )
        if out and out.strip():
            return out.strip()
    except ValueError:
        raise
    raise ValueError(
        "GenOS returned no result (see stderr for the API error). "
        "401 often means experience_id + GENOS_ASSET_ALIAS are not a registered pair in GenOS, "
        "or INTUIT_APP_* creds are wrong. 403 may mean model not whitelisted."
    )


def ask_llm_chat(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.1,
    print_prompt: bool = False,
    system_prompt: str | None = None,
    max_completion_tokens: int | None = None,
) -> str:
    """
    Chat UI / assistant only. On GenOS v3 uses **POST .../v3/lt/{model}/responses**; on v2 uses the same
    Express path as tax (there is no separate responses URL on v2).

    Pass **system_prompt** explicitly (e.g. :func:`get_tax_rules_system_prompt`) to match **Calculate Tax** behavior;
    if omitted, the generic default applies (not recommended for product chat).
    """
    return ask_llm(
        prompt,
        model=model,
        temperature=temperature,
        print_prompt=print_prompt,
        system_prompt=system_prompt,
        max_completion_tokens=max_completion_tokens,
        use_responses_api=True,
    )


def _get_tax_rules_system_prompt() -> str:
    if _TAXRULES_PATH.exists():
        try:
            return _TAXRULES_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return _DEFAULT_SYSTEM_PROMPT


def get_tax_rules_system_prompt() -> str:
    """
    Same system instructions as **Calculate Tax** (`get_tax_calculation_response`): contents of `taxrules.md`
    when present, else the default tax-expert line. Use for chat or any path that should match tax LLM behavior.
    """
    return _get_tax_rules_system_prompt()


# Shown to the model in the user prompt for Assistant chat (plain text; avoids LaTeX in UI).
_CHAT_PLAIN_TEXT_INSTRUCTION = (
    "\n\n**Output formatting:** Write all numbers and formulas in **plain text** only "
    "(e.g. `AGI = $150,060.71` or multi-line arithmetic). "
    "Do **not** use LaTeX or math delimiters such as `\\[`, `\\]`, `\\(`, `\\)`, `$$`, or `\\begin{...}`."
)


def build_chat_user_prompt(
    scenario_text: str,
    memory_items: list[dict[str, Any]],
    prior_messages: list[dict[str, Any]],
    user_message: str,
    *,
    include_reference: bool = True,
) -> str:
    """
    User-side prompt for Assistant chat: same **reference threshold block** as Calculate Tax when
    ``include_reference`` is True (``get_tax_reference_text_all()``), then scenario, memory, thread, and latest message.
    """
    parts: list[str] = []
    if include_reference and get_tax_reference_text_all is not None:
        parts.append(get_tax_reference_text_all())
        parts.append("\n\n---\n")
    parts.append("**Current scenario (tax situation text):**\n" + (scenario_text or "").strip())
    if memory_items:
        lines = [m.get("text", "").strip() for m in memory_items if (m.get("text") or "").strip()]
        if lines:
            parts.append("\n---\n**Notes the user asked you to remember:**\n" + "\n".join(f"- {x}" for x in lines))
    if prior_messages:
        parts.append("\n---\n**Conversation so far:**")
        for m in prior_messages:
            role = m.get("role", "")
            label = "User" if role == "user" else "Assistant"
            parts.append(f"{label}: {m.get('content', '')}")
    parts.append("\n---\n**Latest user message (reply to this):**\n" + (user_message or "").strip())
    parts.append(_CHAT_PLAIN_TEXT_INSTRUCTION)
    return "\n".join(parts)


def normalize_chat_assistant_reply(text: str) -> str:
    """
    Strip common LaTeX delimiters from model output so plain-text chat does not show stray ``\\[`` / ``\\]`` etc.
    """
    if not text:
        return text
    s = text
    for a, b in (("\\[", ""), ("\\]", ""), ("\\(", ""), ("\\)", ""), ("$$", "")):
        s = s.replace(a, b)
    return s


def get_supported_models() -> list[str]:
    """Return list of model names from GenOS only."""
    if not _GENOS_CLIENT_AVAILABLE or get_llm_model_names is None:
        return []
    try:
        return get_llm_model_names(metadata=_genos_metadata()) or []
    except Exception:
        return []


def genos_available() -> bool:
    return _genos_available()


def genos_has_credentials() -> bool:
    m = _genos_metadata()
    return bool(m.get("app_id") or m.get("app_secret") or m.get("auth_id") or m.get("ticket"))


def use_genos_v3() -> bool:
    return _use_genos_v3()


def get_tax_calculation_response(
    description: str,
    *,
    include_reference: bool = True,
    system_prompt: str | None = None,
    model: str | None = None,
    print_prompt: bool = False,
) -> str:
    """
    Single-shot: build prompt from description (optionally prepend tax reference block),
    send to LLM with tax rules as system prompt, return entire LLM output.

    description: The tax situation text (e.g. from tax_situations.txt).
    include_reference: If True, prepend get_tax_reference_text_all() so LLM sees brackets/deductions for all years and statuses.
    system_prompt: If None, uses taxrules.md content.
    """
    if include_reference and get_tax_reference_text_all is not None:
        ref = get_tax_reference_text_all()
        prompt = ref + "\n\n---\n\n" + description
    else:
        prompt = description
    sys_prompt = system_prompt if system_prompt is not None else get_tax_rules_system_prompt()
    return ask_llm(
        prompt,
        model=model,
        system_prompt=sys_prompt,
        print_prompt=print_prompt,
    )


def get_tax_calculation_response_with_strategies(
    description: str,
    strategies: list[dict[str, Any]],
    *,
    model: str | None = None,
    print_prompt: bool = False,
) -> str:
    """
    Compute tax after applying the given strategies to the scenario.
    Passes scenario + strategy descriptions (no extracted data model).
    strategies: list of {strategy_id, inputs, title?} from plan.
    """
    if get_tax_reference_text_all is not None:
        ref = get_tax_reference_text_all()
        prompt = ref + "\n\n---\n\n" + description
    else:
        prompt = description
    # Append strategy block - brief, LLM can reason from scenario + strategy params
    strategy_lines: list[str] = []
    for st in strategies:
        sid = st.get("strategy_id", "unknown")
        title = st.get("title") or sid
        inp = st.get("inputs") or {}
        parts = [f"- {sid} ({title}): {json.dumps(inp)}"]
        strategy_lines.append(" ".join(parts))
    strategy_block = (
        "\n\n---\n\n**Apply these strategies to the scenario above and compute the new tax liability.**\n"
        "Model the taxpayer's situation as if they have implemented these strategies. "
        "Show your work step by step and state the revised amounts (AGI, taxable income, tax, refund/owed).\n\n"
        "Strategies to apply:\n" + "\n".join(strategy_lines)
    )
    full_prompt = prompt + strategy_block
    sys_prompt = get_tax_rules_system_prompt()
    return ask_llm(
        full_prompt,
        model=model,
        system_prompt=sys_prompt,
        print_prompt=print_prompt,
    )
