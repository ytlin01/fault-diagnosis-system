"""Provider abstraction for controlled generation adapters.

TASK-013 only needs a contract surface. Route B/C executors are evidence and
candidate paths, so they do not depend on provider calls for correctness.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    system_prompt: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    provider_type: str
    model: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class BaseProvider(Protocol):
    provider_type: str

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate text from an already-approved, serving-safe request."""


@dataclass(frozen=True)
class StubProvider:
    provider_type: str = "stub"
    model: str = "stub"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            text=request.prompt,
            provider_type=self.provider_type,
            model=self.model,
            metadata={"mode": "echo"},
        )


@dataclass(frozen=True)
class OllamaProvider:
    model: str = "llama3.1"
    endpoint: str = "http://localhost:11434"
    timeout_seconds: int = 30
    provider_type: str = "ollama"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        import httpx

        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "stream": False,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        # Bypass system proxy (e.g. Clash/V2Ray) — proxy cannot reach loopback.
        transport = httpx.HTTPTransport(proxy=None)
        with httpx.Client(transport=transport, timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.endpoint.rstrip('/')}/api/generate",
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        return ProviderResponse(
            text=str(data.get("response", "")),
            provider_type=self.provider_type,
            model=self.model,
            metadata={"endpoint": self.endpoint, "done": data.get("done")},
        )


@dataclass(frozen=True)
class CompanyApiProvider:
    """Adapter contract for the company provider.

    The real protocol is intentionally not guessed here. A caller must inject a
    client object with a `generate(payload)` method once the approved protocol,
    endpoint, and credential loading path are known.
    """

    model: str = ""
    client: Any | None = None
    provider_type: str = "company_api"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self.client is None:
            raise NotImplementedError(
                "company_api provider requires an approved injected client; "
                "TASK-013 does not hard-code protocol, endpoint, or credentials."
            )
        payload = {
            "prompt": request.prompt,
            "system_prompt": request.system_prompt,
            "metadata": dict(request.metadata),
            "model": self.model,
        }
        result = self.client.generate(payload)
        if isinstance(result, ProviderResponse):
            return result
        if isinstance(result, Mapping):
            return ProviderResponse(
                text=str(result.get("text", "")),
                provider_type=self.provider_type,
                model=str(result.get("model") or self.model or ""),
                metadata=dict(result.get("metadata", {})) if isinstance(result.get("metadata"), Mapping) else {},
            )
        return ProviderResponse(text=str(result), provider_type=self.provider_type, model=self.model)


def build_provider(config: Mapping[str, Any] | None = None) -> BaseProvider:
    config = dict(config or {})
    provider_type = str(os.getenv("FAULTDX_PROVIDER_TYPE") or config.get("type") or "stub").strip().lower()
    if provider_type == "stub":
        return StubProvider()
    if provider_type == "ollama":
        ollama_config = config.get("ollama", {}) if isinstance(config.get("ollama"), Mapping) else {}
        return OllamaProvider(
            model=str(os.getenv("FAULTDX_OLLAMA_MODEL") or ollama_config.get("model") or "llama3.1"),
            endpoint=str(os.getenv("FAULTDX_OLLAMA_ENDPOINT") or ollama_config.get("endpoint") or "http://localhost:11434"),
            timeout_seconds=int(os.getenv("FAULTDX_OLLAMA_TIMEOUT") or config.get("timeout_seconds") or 120),
        )
    if provider_type == "company_api":
        company_config = config.get("company_api", {}) if isinstance(config.get("company_api"), Mapping) else {}
        return CompanyApiProvider(
            model=str(os.getenv("FAULTDX_COMPANY_MODEL_NAME") or company_config.get("model") or ""),
        )
    raise ValueError(f"Unsupported provider type: {provider_type}")
