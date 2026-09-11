"""Real, live smoke test proving the Z.AI GLM coding-plan endpoint is
reachable and authenticated from this repo -- no mock HTTP client, no
canned response. `Z_AI_API_KEY` lives in `~/.env` (not necessarily the
process environment), so it is read directly from there once at import
time; honest skip (not a silent mock substitution) if the key is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import pytest

ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
ZAI_MODEL = "glm-4.5-flash"


def _read_zai_key() -> str | None:
    if key := os.environ.get("Z_AI_API_KEY"):
        return key.strip()
    env_path = Path.home() / ".env"
    if not env_path.exists():
        return None
    match = re.search(r"^Z_AI_API_KEY=(.+)$", env_path.read_text(), re.MULTILINE)
    return match.group(1).strip() if match else None


_ZAI_KEY = _read_zai_key()

pytestmark = pytest.mark.skipif(
    _ZAI_KEY is None, reason="no Z_AI_API_KEY in ~/.env or the environment"
)


def test_zai_glm_coding_endpoint_answers_a_real_live_chat_completion():
    """Real HTTP POST to Z.AI's OpenAI-compatible chat/completions route --
    real auth, real model inference, real response parsed and asserted on."""
    response = httpx.post(
        f"{ZAI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {_ZAI_KEY}"},
        json={
            "model": ZAI_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply with exactly the word 'pong' and nothing else.",
                }
            ],
            "max_tokens": 4096,
        },
        timeout=60.0,
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert "choices" in body and len(body["choices"]) == 1
    content = body["choices"][0]["message"]["content"]
    assert isinstance(content, str)
    assert "pong" in content.lower()
