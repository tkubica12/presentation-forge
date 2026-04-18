"""Generate prompt variations using a Foundry chat-completion model.

Uses the Azure OpenAI chat completions REST endpoint (Entra ID).
"""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx

from .auth import TokenCache

CHAT_API_VERSION = "2025-04-01-preview"

SYSTEM_TEMPLATE = """You are an expert prompt engineer for state-of-the-art \
text-to-image diffusion models. You will be given:
- COMMON_REQUIREMENTS: directives every prompt must satisfy.
- STYLE_HINT: baseline photographic style guidance.
- IMAGE_NAME and IMAGE_DESCRIPTION: the subject of this batch.
- VARIATION_GUIDANCE (optional): user instructions on how variations should \
differ from each other.

Generate exactly {n} distinct, fully-formed image generation prompts that:
1. Strictly include and respect the COMMON_REQUIREMENTS.
2. Stay faithful to the IMAGE_DESCRIPTION subject.
3. Differ meaningfully from each other along the axes given in \
VARIATION_GUIDANCE; if no guidance is given, vary lighting, camera angle, \
lens, mood, background and surrounding props.
4. Are written as one rich English paragraph each (60-120 words), \
self-contained, no numbering, no markdown.
5. End with concise technical photography qualifiers \
(camera body, lens focal length, aperture, ISO, shutter, lighting setup) \
appropriate for a photorealistic result.

Output MUST be a JSON array of {n} strings and nothing else.
"""


def build_system_prompt(n: int) -> str:
    return SYSTEM_TEMPLATE.format(n=n)


def build_user_prompt(
    *,
    common_requirements: str,
    style_hint: str,
    image_name: str,
    image_description: str,
    variation_guidance: Optional[str],
) -> str:
    parts = [
        f"COMMON_REQUIREMENTS:\n{common_requirements.strip()}",
        f"STYLE_HINT:\n{style_hint.strip()}",
        f"IMAGE_NAME: {image_name}",
        f"IMAGE_DESCRIPTION:\n{image_description.strip()}",
    ]
    if variation_guidance:
        parts.append(f"VARIATION_GUIDANCE:\n{variation_guidance.strip()}")
    else:
        parts.append("VARIATION_GUIDANCE: (none — use sensible defaults)")
    return "\n\n".join(parts)


def _extract_json_array(text: str) -> list[str]:
    text = text.strip()
    # Strip markdown fences if model added them
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first [...] block
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError(f"Could not parse JSON array from model output: {text[:300]}")
        data = json.loads(match.group(0))
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise ValueError("Model output was not a JSON array of strings")
    return data


async def generate_variations(
    *,
    endpoint: str,
    deployment: str,
    token_cache: TokenCache,
    common_requirements: str,
    style_hint: str,
    image_name: str,
    image_description: str,
    variation_guidance: Optional[str],
    count: int,
    client: httpx.AsyncClient,
) -> list[str]:
    """Call chat completions and return ``count`` prompt variations."""
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={CHAT_API_VERSION}"
    )
    body = {
        "messages": [
            {"role": "system", "content": build_system_prompt(count)},
            {
                "role": "user",
                "content": build_user_prompt(
                    common_requirements=common_requirements,
                    style_hint=style_hint,
                    image_name=image_name,
                    image_description=image_description,
                    variation_guidance=variation_guidance,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    # When response_format is json_object the model needs an object root, so we
    # ask for {"prompts": [...]} instead and unwrap.
    body["messages"][0]["content"] += (
        '\n\nReturn JSON object: {"prompts": [<string>, ...]}.'
    )
    headers = {
        "Authorization": f"Bearer {token_cache.get_token()}",
        "Content-Type": "application/json",
    }
    resp = await client.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    obj = json.loads(content)
    prompts = obj.get("prompts") if isinstance(obj, dict) else None
    if prompts is None:
        prompts = _extract_json_array(content)
    if len(prompts) < count:
        # Pad by repeating last prompt (rare); avoid silent failure
        while len(prompts) < count:
            prompts.append(prompts[-1])
    return [str(p).strip() for p in prompts[:count]]
