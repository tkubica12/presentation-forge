"""Authentication helpers for Microsoft Foundry endpoints.

We exclusively use Microsoft Entra ID via DefaultAzureCredential. The same
credential works for both APIs because both accept the
``https://cognitiveservices.azure.com/.default`` scope.

Set up auth locally with ``az login`` before running. In Azure-hosted
environments DefaultAzureCredential will pick up Managed Identity / workload
identity automatically.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from azure.identity import DefaultAzureCredential

SCOPE = "https://cognitiveservices.azure.com/.default"


class TokenCache:
    """Thread-safe bearer-token cache with a small expiry margin."""

    def __init__(self, credential: Optional[DefaultAzureCredential] = None) -> None:
        self._credential = credential or DefaultAzureCredential()
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_on: float = 0.0

    def get_token(self) -> str:
        now = time.time()
        # refresh 60s before expiry
        if self._token and now < self._expires_on - 60:
            return self._token
        with self._lock:
            if self._token and now < self._expires_on - 60:
                return self._token
            tok = self._credential.get_token(SCOPE)
            self._token = tok.token
            self._expires_on = float(tok.expires_on)
            return self._token
