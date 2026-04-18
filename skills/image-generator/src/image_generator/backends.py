"""Image generation backends for MAI-Image-2 and gpt-image-1.5."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import random
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image

from .auth import TokenCache

log = logging.getLogger(__name__)

# REST API versions
GPT_IMAGE_API_VERSION = "2025-04-01-preview"

# Limits
MAI_MIN_DIM = 768
MAI_MAX_TOTAL_PIXELS = 1024 * 1024  # 1,048,576
GPT_IMAGE_ALLOWED_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}

# Retry policy
MAX_ATTEMPTS = 8
BACKOFF_BASE = 2.0
BACKOFF_MAX = 60.0
RETRY_AFTER_CAP = 90.0  # never sleep longer than this on a 429


class GenerationError(RuntimeError):
    """Non-retriable backend error (4xx other than 408/429)."""


class RetryableError(RuntimeError):
    """Retriable backend error (timeouts, 5xx, 408)."""


class RateLimitError(RetryableError):
    """HTTP 429 — retried with Retry-After when available."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def _parse_size(size: str) -> tuple[int, int]:
    try:
        w, h = size.lower().split("x")
        return int(w), int(h)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid size '{size}', expected WxH like 1024x1024") from exc


def _clamp_mai_size(size: str) -> tuple[int, int]:
    w, h = _parse_size(size)
    w = max(w, MAI_MIN_DIM)
    h = max(h, MAI_MIN_DIM)
    if w * h > MAI_MAX_TOTAL_PIXELS:
        scale = (MAI_MAX_TOTAL_PIXELS / (w * h)) ** 0.5
        w = max(MAI_MIN_DIM, int(w * scale) // 8 * 8)
        h = max(MAI_MIN_DIM, int(h * scale) // 8 * 8)
    return w, h


def _normalize_gpt_size(size: str) -> str:
    size = size.lower()
    if size in GPT_IMAGE_ALLOWED_SIZES:
        return size
    w, h = _parse_size(size)
    if w == h:
        return "1024x1024"
    return "1536x1024" if w > h else "1024x1536"


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return min(float(value), RETRY_AFTER_CAP)
    except ValueError:
        return None


def _classify(resp: httpx.Response) -> Exception:
    text = resp.text[:500]
    if resp.status_code == 429:
        return RateLimitError(
            f"429 rate-limited: {text}",
            retry_after=_parse_retry_after(resp.headers.get("Retry-After")),
        )
    if resp.status_code in (408, 500, 502, 503, 504):
        return RetryableError(f"{resp.status_code}: {text}")
    return GenerationError(f"{resp.status_code}: {text}")


async def _post_with_retry(
    *,
    client: httpx.AsyncClient,
    request_fn,
    label: str,
) -> httpx.Response:
    """Run ``request_fn(headers) -> coroutine[Response]`` with adaptive retries.

    ``request_fn`` is a callable taking the auth headers dict and returning the
    awaitable httpx response — this lets us refresh the bearer token on each
    attempt.
    """
    last_exc: Optional[BaseException] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp: httpx.Response = await request_fn()
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            sleep_for = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** (attempt - 1)))
            sleep_for *= 0.5 + random.random()  # jitter
            log.warning(
                "%s transport error (attempt %d/%d): %s — sleeping %.1fs",
                label, attempt, MAX_ATTEMPTS, exc, sleep_for,
            )
            await asyncio.sleep(sleep_for)
            continue

        if resp.status_code < 400:
            return resp

        exc = _classify(resp)
        last_exc = exc
        if isinstance(exc, GenerationError):
            raise exc
        if attempt == MAX_ATTEMPTS:
            raise exc

        if isinstance(exc, RateLimitError) and exc.retry_after is not None:
            sleep_for = exc.retry_after + random.uniform(0.2, 1.5)
        else:
            sleep_for = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** (attempt - 1)))
            sleep_for *= 0.5 + random.random()
        log.warning(
            "%s %s (attempt %d/%d) — sleeping %.1fs",
            label, exc, attempt, MAX_ATTEMPTS, sleep_for,
        )
        await asyncio.sleep(sleep_for)

    assert last_exc is not None
    raise last_exc


# --------------------------- MAI-Image-2 -------------------------------------

async def generate_mai_image(
    *,
    endpoint: str,
    deployment: str,
    token_cache: TokenCache,
    prompt: str,
    size: str,
    client: httpx.AsyncClient,
) -> bytes:
    width, height = _clamp_mai_size(size)
    url = f"{endpoint.rstrip('/')}/mai/v1/images/generations"
    body = {"model": deployment, "prompt": prompt, "width": width, "height": height}

    async def _do() -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {token_cache.get_token()}",
            "Content-Type": "application/json",
        }
        return await client.post(url, headers=headers, json=body, timeout=300)

    resp = await _post_with_retry(client=client, request_fn=_do, label=f"MAI[{deployment}]")
    return _extract_b64(resp.json())


# --------------------------- gpt-image-1.5 -----------------------------------

async def generate_gpt_image(
    *,
    endpoint: str,
    deployment: str,
    token_cache: TokenCache,
    prompt: str,
    size: str,
    quality: str,
    input_image_path: Optional[Path],
    client: httpx.AsyncClient,
) -> bytes:
    norm_size = _normalize_gpt_size(size)
    base = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/images"
    params = f"?api-version={GPT_IMAGE_API_VERSION}"
    image_bytes = input_image_path.read_bytes() if input_image_path else None
    image_name = input_image_path.name if input_image_path else None

    async def _do() -> httpx.Response:
        headers = {"Authorization": f"Bearer {token_cache.get_token()}"}
        if image_bytes is not None:
            url = f"{base}/edits{params}"
            files = {"image": (image_name, image_bytes, "image/png")}
            form = {
                "prompt": prompt,
                "size": norm_size,
                "quality": quality,
                "n": "1",
                "model": deployment,
            }
            return await client.post(url, headers=headers, data=form, files=files, timeout=300)
        url = f"{base}/generations{params}"
        headers["Content-Type"] = "application/json"
        body = {
            "prompt": prompt,
            "model": deployment,
            "size": norm_size,
            "quality": quality,
            "n": 1,
        }
        return await client.post(url, headers=headers, json=body, timeout=300)

    resp = await _post_with_retry(
        client=client, request_fn=_do, label=f"gpt-image[{deployment}]"
    )
    return _extract_b64(resp.json())


# --------------------------- Helpers -----------------------------------------

def _extract_b64(data: dict) -> bytes:
    """Extract PNG bytes from various Foundry response shapes."""
    # gpt-image: { "data": [{"b64_json": "..."}] }
    if isinstance(data, dict) and "data" in data:
        item = data["data"][0]
        if "b64_json" in item:
            return base64.b64decode(item["b64_json"])
        if "url" in item:
            raise GenerationError("URL responses not supported; expected b64_json")
    # MAI: { "image": "<b64>" } or similar
    for key in ("image", "b64_json", "image_b64"):
        if isinstance(data, dict) and key in data and isinstance(data[key], str):
            return base64.b64decode(data[key])
    # MAI may also nest in data list
    raise GenerationError(f"Unexpected response shape: {list(data)[:6]}")


def prepare_input_image(
    src: Path, *, max_dim: int = 1536, dst: Optional[Path] = None
) -> Path:
    """Resize the input image so the longest edge <= max_dim and re-save as PNG.

    gpt-image-1.5 /images/edits accepts PNG/JPEG up to 25 MB; resizing keeps
    upload fast and avoids out-of-bound dimensions. Returned path is what
    callers should pass to :func:`generate_gpt_image`.
    """
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    scale = min(1.0, max_dim / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    out = dst or src.with_suffix(".prepared.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    out.write_bytes(buf.getvalue())
    return out
