#!/usr/bin/env python3
"""
Simple GenOS test client — same pattern as expert-agent-svc/app/call_genos.py.
Uses only env + intuit_originating_assetalias (no app_id/app_secret in code),
so genosclient uses "test creds" like in the working demo.

Set GENOS_USE_V3=1 in .env to use the v3 API (GPT-5 models use v3).
Otherwise uses Express v2 with gpt-4o-2024-08-06.
"""

import asyncio
import os
from pathlib import Path

# Load .env from this directory
_root = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
    load_dotenv(Path.cwd() / ".env")
except ImportError:
    pass

# Same defaults as expert-agent-svc/app/call_genos.py (override via .env)
# Fintax advisory pair. Proconnect demo: 436421a4-9c43-4e5d-a52d-1338914a8a60 + Intuit.protax.proconnect.ptgpmxddemo
EXPERIENCE_ID = os.getenv("GENOS_EXPERIENCE_ID", "75be454b-adb9-4bb3-af7f-3275e04908c8")
METADATA = {
    "env": os.getenv("GENOS_ENV", "e2e"),
    "intuit_originating_assetalias": os.getenv("GENOS_ASSET_ALIAS", "Intuit.incometax.triage.agenticita"),
}
# v2: use v2-supported model. v3: use GENOS_MODEL_ID (e.g. gpt-5.4-2026-03-05).
USE_V3 = os.getenv("GENOS_USE_V3", "").strip().lower() in ("1", "true", "yes")
MODEL_ID_V2 = "gpt-4o-2024-08-06"
MODEL_ID = os.getenv("GENOS_MODEL_ID", "gpt-5.4-2026-03-05") if USE_V3 else MODEL_ID_V2


def _call_genos_v3(system_prompt: str, user_prompt: str):
    """Call GenOS v3 API (OpenAI-style). Returns object with .llm_output.choices[0].message.content for compatibility."""
    import requests
    base = "https://llmexecution-e2e.api.intuit.com/v3"
    if os.getenv("GENOS_ENV", "e2e").lower() == "qal":
        base = "https://llmexecution-qal.api.intuit.com/v3"
    elif os.getenv("GENOS_ENV", "e2e").lower() == "prf":
        base = "https://llmexecution-prf.api.intuit.com/v3"
    url = f"{base}/{MODEL_ID}/chat/completions"
    from genosclient.genos_client import build_headers
    headers = build_headers(METADATA)
    headers["Content-Type"] = "application/json"
    r = requests.post(
        url,
        json={
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": 5000,
        },
        headers=headers,
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    content = ""
    if choices:
        msg = choices[0].get("message")
        if isinstance(msg, dict):
            content = msg.get("content") or ""

    class Message:
        def __init__(self, content):
            self.content = content

    class Choice:
        def __init__(self, content):
            self.message = Message(content)

    class Output:
        def __init__(self, content):
            self.choices = [Choice(content)]

    class Response:
        def __init__(self, content):
            self.llm_output = Output(content)

    return Response(content)


def call_genos(system_prompt: str, user_prompt: str):
    """Same signature as expert-agent-svc/app/call_genos.py. Uses v3 if GENOS_USE_V3=1."""
    if USE_V3:
        return _call_genos_v3(system_prompt, user_prompt)
    from genosclient.genos_client import build_headers
    from genosclient import ApiClient, ExpressModeApi, ExpressModeV2RequestMessage

    async def _call_genos_async(system_prompt, user_prompt):
        headers = build_headers(METADATA)
        async with ApiClient(is_async=True) as api_client:
            api_instance = ExpressModeApi(api_client)
            response = await api_instance.achat_completion_v2(
                model_id=MODEL_ID_V2,
                intuit_experience_id=EXPERIENCE_ID,
                express_mode_v2_request_message=ExpressModeV2RequestMessage(
                    llm_input={
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "model_parameters": {"temperature": 0, "max_tokens": 5000},
                    }
                ),
                _headers=headers,
            )
            return response

    return asyncio.run(_call_genos_async(system_prompt, user_prompt))


def main():
    system_prompt = "You are a helpful assistant."
    user_prompt = "Hello, GenOS! Reply in one short sentence."
    print("Calling GenOS (same as expert-agent-svc/app/call_genos.py)...")
    try:
        response = call_genos(system_prompt, user_prompt)
        if hasattr(response, "llm_output") and hasattr(response.llm_output, "choices") and response.llm_output.choices:
            text = response.llm_output.choices[0].message.content
            print("Response:", text)
        elif hasattr(response, "choices") and response.choices:
            print("Response:", response.choices[0].message.content)
        else:
            print("Response (raw):", response)
    except Exception as e:
        print("Error:", e)
        print("Tip: Run from the same network as expert-agent-svc, or set INTUIT_APP_ID and INTUIT_APP_SECRET in .env.")


if __name__ == "__main__":
    main()
