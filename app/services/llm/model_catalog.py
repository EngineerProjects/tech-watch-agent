from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config.settings import Settings, get_settings
from app.services.llm.providers import LLMProviders, get_provider_config


@dataclass(frozen=True)
class ModelCatalogItem:
    id: str
    label: str
    description: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    dimensions: int | None = None
    capabilities: list[str] = field(default_factory=list)
    recommended_role: str | None = None
    source: str = "curated"
    available: bool | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "dimensions": self.dimensions,
            "capabilities": list(self.capabilities),
            "recommended_role": self.recommended_role,
            "source": self.source,
            "available": self.available,
            "family": self.family,
            "parameter_size": self.parameter_size,
            "quantization": self.quantization,
            "size_bytes": self.size_bytes,
        }


_PROVIDER_LABELS = {
    LLMProviders.OPENAI: "OpenAI",
    LLMProviders.OPENROUTER: "OpenRouter",
    LLMProviders.OLLAMA: "Ollama",
    LLMProviders.ZAI: "Z.ai",
}

_CURATED_CHAT_MODELS: dict[str, list[ModelCatalogItem]] = {
    LLMProviders.OPENAI: [
        ModelCatalogItem(
            id="gpt-4.1",
            label="GPT-4.1",
            description="Flagship non-reasoning model for strong coding, instruction following, and long-context tasks.",
            context_window=1_047_576,
            max_output_tokens=32_768,
            capabilities=["chat", "tools", "vision"],
            recommended_role="quality",
        ),
        ModelCatalogItem(
            id="gpt-4.1-mini",
            label="GPT-4.1 mini",
            description="Balanced default for agents: fast, affordable, strong tool calling, long context.",
            context_window=1_047_576,
            max_output_tokens=32_768,
            capabilities=["chat", "tools", "vision"],
            recommended_role="default",
        ),
        ModelCatalogItem(
            id="gpt-4.1-nano",
            label="GPT-4.1 nano",
            description="Fastest and cheapest GPT-4.1 family member for lightweight tasks and routing fallbacks.",
            context_window=1_047_576,
            max_output_tokens=32_768,
            capabilities=["chat", "tools"],
            recommended_role="fast",
        ),
    ],
    LLMProviders.OPENROUTER: [
        ModelCatalogItem(
            id="openai/gpt-4.1-mini",
            label="OpenAI GPT-4.1 mini",
            description="Reliable default on OpenRouter with long context and strong tool calling.",
            context_window=1_000_000,
            max_output_tokens=32_768,
            capabilities=["chat", "tools", "vision"],
            recommended_role="default",
        ),
        ModelCatalogItem(
            id="google/gemini-2.5-flash",
            label="Google Gemini 2.5 Flash",
            description="Reasoning-heavy workhorse with good coding/math performance and 1M context.",
            context_window=1_000_000,
            capabilities=["chat", "thinking", "tools"],
            recommended_role="reasoning",
        ),
        ModelCatalogItem(
            id="anthropic/claude-sonnet-4",
            label="Anthropic Claude Sonnet 4",
            description="High-quality coding and agent model with strong controllability and execution reliability.",
            context_window=1_000_000,
            capabilities=["chat", "tools"],
            recommended_role="quality",
        ),
    ],
    LLMProviders.ZAI: [
        ModelCatalogItem(
            id="glm-5.1",
            label="GLM-5.1",
            description="Latest Z.ai flagship for long-horizon engineering and autonomous agent execution.",
            context_window=200_000,
            max_output_tokens=128_000,
            capabilities=["chat", "thinking", "tools", "structured-output"],
            recommended_role="quality",
        ),
        ModelCatalogItem(
            id="glm-4.7",
            label="GLM-4.7",
            description="Balanced default for coding, agent tasks, UI generation, and high-frequency collaboration.",
            context_window=200_000,
            max_output_tokens=128_000,
            capabilities=["chat", "thinking", "tools", "structured-output"],
            recommended_role="default",
        ),
        ModelCatalogItem(
            id="glm-4.5",
            label="GLM-4.5",
            description="Earlier strong agent-oriented model with 128K context and robust browsing/tool workflows.",
            context_window=128_000,
            max_output_tokens=96_000,
            capabilities=["chat", "thinking", "tools", "structured-output"],
            recommended_role="fallback",
        ),
    ],
}

_CURATED_EMBEDDING_MODELS: dict[str, list[ModelCatalogItem]] = {
    LLMProviders.OPENAI: [
        ModelCatalogItem(
            id="text-embedding-3-small",
            label="text-embedding-3-small",
            description="Default embedding model with good quality/cost tradeoff.",
            dimensions=1536,
            capabilities=["embeddings"],
            recommended_role="default",
        ),
        ModelCatalogItem(
            id="text-embedding-3-large",
            label="text-embedding-3-large",
            description="Highest quality OpenAI embedding model.",
            dimensions=3072,
            capabilities=["embeddings"],
            recommended_role="quality",
        ),
        ModelCatalogItem(
            id="text-embedding-ada-002",
            label="text-embedding-ada-002",
            description="Legacy compatibility embedding model.",
            capabilities=["embeddings"],
            recommended_role="legacy",
        ),
    ],
    LLMProviders.OPENROUTER: [
        ModelCatalogItem(
            id="openai/text-embedding-3-small",
            label="OpenAI text-embedding-3-small",
            description="Safe default on OpenRouter when you want OpenAI-compatible embeddings via one gateway.",
            context_window=8192,
            dimensions=1536,
            capabilities=["embeddings"],
            recommended_role="default",
        ),
        ModelCatalogItem(
            id="google/gemini-embedding-001",
            label="Google Gemini Embedding 001",
            description="Strong multilingual embedding option available on OpenRouter.",
            context_window=20_000,
            capabilities=["embeddings"],
            recommended_role="quality",
        ),
    ],
    LLMProviders.ZAI: [
        ModelCatalogItem(
            id="embedding-2",
            label="embedding-2",
            description="Current Z.ai embedding model supported by the runtime.",
            capabilities=["embeddings"],
            recommended_role="default",
        ),
    ],
}


def _provider_label(name: str) -> str:
    return _PROVIDER_LABELS.get(name, name.capitalize())


def _normalize_ollama_base_url(base_url: str | None) -> str:
    raw = (base_url or "http://localhost:11434/v1").rstrip("/")
    if raw.endswith("/v1"):
        raw = raw[:-3]
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api"


def _is_embedding_model(name: str, capabilities: list[str], families: list[str]) -> bool:
    text = " ".join([name.lower(), *[item.lower() for item in capabilities], *[item.lower() for item in families]])
    markers = ["embed", "embedding", "minilm", "bge"]
    return any(marker in text for marker in markers)


def _extract_context_window(model_info: dict[str, Any], parameters_text: str | None) -> int | None:
    for key, value in (model_info or {}).items():
        if isinstance(key, str) and key.endswith(".context_length") and isinstance(value, int):
            return value
    if parameters_text:
        for line in parameters_text.splitlines():
            line = line.strip()
            if line.startswith("num_ctx"):
                parts = line.split()
                if len(parts) == 2 and parts[1].isdigit():
                    return int(parts[1])
    return None


def discover_ollama_catalog(base_url: str | None = None, timeout: float = 6.0) -> dict[str, Any]:
    api_url = _normalize_ollama_base_url(base_url)
    chat_models: list[ModelCatalogItem] = []
    embedding_models: list[ModelCatalogItem] = []

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{api_url}/tags")
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("models", []) or []:
                name = item.get("name") or item.get("model")
                if not name:
                    continue

                details = item.get("details") or {}
                capabilities: list[str] = []
                model_info: dict[str, Any] = {}
                parameters_text: str | None = None
                try:
                    show = client.post(f"{api_url}/show", json={"model": name, "verbose": False})
                    show.raise_for_status()
                    show_payload = show.json()
                    capabilities = [str(cap).lower() for cap in show_payload.get("capabilities", []) or []]
                    model_info = show_payload.get("model_info") or {}
                    parameters_text = show_payload.get("parameters")
                except Exception:
                    capabilities = []
                    model_info = {}
                    parameters_text = None

                family = details.get("family")
                families = [str(fam) for fam in details.get("families") or []]
                context_window = _extract_context_window(model_info, parameters_text)
                catalog_item = ModelCatalogItem(
                    id=name,
                    label=name,
                    description="Auto-discovered from the local Ollama instance.",
                    context_window=context_window,
                    capabilities=capabilities or (["embeddings"] if _is_embedding_model(name, [], families) else ["chat"]),
                    source="ollama-discovered",
                    available=True,
                    family=family,
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                    size_bytes=item.get("size"),
                )

                if _is_embedding_model(name, capabilities, families):
                    embedding_models.append(catalog_item)
                else:
                    chat_models.append(catalog_item)
    except Exception as exc:
        return {
            "chat_models": [],
            "embedding_models": [],
            "error": str(exc),
        }

    return {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
        "error": None,
    }


def _merge_models(curated: list[ModelCatalogItem], discovered: list[ModelCatalogItem]) -> list[ModelCatalogItem]:
    merged: dict[str, ModelCatalogItem] = {item.id: item for item in curated}
    for item in discovered:
        merged[item.id] = item
    return list(merged.values())


def build_provider_catalogs(settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    catalogs: list[dict[str, Any]] = []

    ollama_config = get_provider_config(LLMProviders.OLLAMA)
    ollama_base_url = (
        settings.llm_base_url
        if settings.llm_provider == LLMProviders.OLLAMA and settings.llm_base_url
        else (ollama_config.base_url if ollama_config else None)
    )
    ollama_discovery = discover_ollama_catalog(ollama_base_url) if ollama_base_url else {"chat_models": [], "embedding_models": [], "error": None}

    for provider_name in [LLMProviders.OPENROUTER, LLMProviders.OPENAI, LLMProviders.OLLAMA, LLMProviders.ZAI]:
        config = get_provider_config(provider_name)
        if config is None:
            continue

        base_url = settings.llm_base_url if provider_name == settings.llm_provider and settings.llm_base_url else config.base_url
        chat_models = list(_CURATED_CHAT_MODELS.get(provider_name, []))
        embedding_models = list(_CURATED_EMBEDDING_MODELS.get(provider_name, []))
        discovery_error = None
        default_model = config.default_model

        if provider_name == LLMProviders.OLLAMA:
            discovered_chat = ollama_discovery.get("chat_models", []) or []
            discovered_embeddings = ollama_discovery.get("embedding_models", []) or []
            discovery_error = ollama_discovery.get("error")
            chat_models = discovered_chat
            embedding_models = discovered_embeddings
            default_model = chat_models[0].id if chat_models else ""

        catalogs.append(
            {
                "name": provider_name,
                "label": _provider_label(provider_name),
                "base_url": base_url,
                "default_model": default_model,
                "requires_api_key": config.requires_api_key,
                "supports_dynamic_discovery": provider_name == LLMProviders.OLLAMA,
                "discovery_error": discovery_error,
                "chat_models": [item.to_dict() for item in chat_models],
                "embedding_models": [item.to_dict() for item in embedding_models],
            }
        )

    return catalogs
