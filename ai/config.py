"""
Kapsel AI Configuration Manager.
Manages AI provider configurations, dynamic /models endpoint probing, and static fallback.
Loads and saves AI configuration from ~/.kapsel/ai/config.yaml.
All comments and docstrings are in English.
"""

import json
from pathlib import Path
import ssl
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import yaml

from kapsel.storage.config import get_kapsel_dir


def get_ai_config_dir() -> Path:
    """Returns directory path for AI configuration."""
    cfg_dir = get_kapsel_dir() / "ai"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def get_ai_config_file() -> Path:
    """Returns configuration file path (~/.kapsel/ai/config.yaml)."""
    return get_ai_config_dir() / "config.yaml"


DEFAULT_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "openai",
        "name": "OpenAI (Official API)",
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-5.6-sol",
        "models": [
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
        ],
        "requires_key": True,
        "key_prompt": "Enter OpenAI API Key (sk-...): ",
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude (Official API)",
        "api_base": "https://api.anthropic.com",
        "model": "claude-opus-5",
        "models": [
            "claude-opus-5",
            "claude-sonnet-5",
            "claude-fable-5",
            "claude-opus-4-8",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
        "requires_key": True,
        "key_prompt": "Enter Anthropic API Key (sk-ant-...): ",
    },
    {
        "id": "gemini",
        "name": "Google Gemini (Official API)",
        "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-3.8-flash",
        "models": [
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
        ],
        "requires_key": True,
        "key_prompt": "Enter Google AI Studio API Key (AIzaSy...): ",
    },
    {
        "id": "xai",
        "name": "xAI Grok (Official API)",
        "api_base": "https://api.x.ai/v1",
        "model": "grok-4.6",
        "models": [
            "grok-4.6",
            "grok-4.5",
            "grok-4.3",
            "grok-4.20",
        ],
        "requires_key": True,
        "key_prompt": "Enter xAI API Key: ",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek (Official API)",
        "api_base": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
        "models": [
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "deepseek-v4-flash-vision-exp",
        ],
        "requires_key": True,
        "key_prompt": "Enter DeepSeek API Key (sk-...): ",
    },
    {
        "id": "mistral",
        "name": "Mistral AI (Official API)",
        "api_base": "https://api.mistral.ai/v1",
        "model": "mistral-medium-3-5",
        "models": [
            "mistral-medium-3-5",
            "mistral-large-3",
            "mistral-small-2603",
        ],
        "requires_key": True,
        "key_prompt": "Enter Mistral API Key: ",
    },
    {
        "id": "cohere",
        "name": "Cohere (Official API)",
        "api_base": "https://api.cohere.com/v2",
        "model": "command-a-plus-05-2026",
        "models": [
            "command-a-plus-05-2026",
            "command-a-03-2025",
            "command-a-reasoning-08-2025",
            "command-a-vision-07-2025",
            "command-a-translate-08-2025",
            "command-r7b-12-2024",
        ],
        "requires_key": True,
        "key_prompt": "Enter Cohere API Key: ",
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow (Multi-Model Cloud)",
        "api_base": "https://api.siliconflow.com/v1",
        "model": "deepseek-ai/DeepSeek-V4-Pro-0813",
        "models": [
            "deepseek-ai/DeepSeek-V4-Pro-0813",
            "deepseek-ai/DeepSeek-V4-Flash",
            "Qwen/Qwen3.5-397B-A17B",
            "Qwen/Qwen3.5-122B-A10B",
            "Qwen/Qwen3.5-35B-A3B",
            "zai-org/GLM-5.3",
        ],
        "requires_key": True,
        "key_prompt": "Enter SiliconFlow API Key: ",
    },
    {
        "id": "ollama",
        "name": "Ollama (Local LLM - Free & Offline, No Key Needed)",
        "api_base": "http://localhost:11434/v1",
        "model": "qwen3.5:27b",
        "models": [
            "qwen3.5:27b",
            "qwen3.5:35b",
            "qwen3.5:122b",
            "gemma4:31b",
            "gemma4:26b",
            "gemma4:12b",
            "minimax-m2.7",
            "glm-4.7-flash",
        ],
        "requires_key": False,
        "key_prompt": "",
    },
    {
        "id": "custom",
        "name": "Custom OpenAI-Compatible (OneAPI / NewAPI / vLLM)",
        "api_base": "",
        "model": "gpt-5.6-sol",
        "models": [],
        "requires_key": True,
        "key_prompt": "Enter API Key: ",
    },
]


def get_provider(provider_id: str) -> Optional[Dict[str, Any]]:
    """Returns provider dictionary by ID, or None if not found."""
    for prov in DEFAULT_PROVIDERS:
        if prov["id"].lower() == provider_id.lower():
            return prov
    return None


def fetch_dynamic_models(
    api_base: str,
    api_key: str = "",
    provider_id: str = "",
    timeout: float = 3.5,
) -> List[str]:
    """
    Dynamically probes the endpoint for available models using standard /models endpoint.
    Supports OpenAI standard schema (data[].id), Cohere/Ollama (models[].name), and Anthropic.
    Returns a list of discovered model identifiers, or empty list on network or parse failure.
    """
    if not api_base:
        return []

    clean_base = api_base.strip().rstrip("/")
    if not clean_base.startswith(("http://", "https://")):
        return []

    # Determine probe URL
    if clean_base.endswith("/models"):
        models_url = clean_base
    elif provider_id.lower() == "anthropic" and not clean_base.endswith("/v1"):
        models_url = f"{clean_base}/v1/models"
    else:
        models_url = f"{clean_base}/models"

    headers: Dict[str, str] = {
        "User-Agent": "Kapsel-AI/0.1.2",
        "Accept": "application/json",
    }
    if api_key:
        if provider_id.lower() == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(models_url, headers=headers, method="GET")
        open_kwargs: Dict[str, Any] = {"timeout": timeout}
        if models_url.startswith("https://"):
            try:
                open_kwargs["context"] = ssl.create_default_context()
            except Exception:
                pass

        with urllib.request.urlopen(req, **open_kwargs) as response:
            status = getattr(response, "status", getattr(response, "code", 200))
            if status not in (200, 201):
                return []
            raw_body = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw_body)

        model_items: List[Any] = []
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                model_items = data["data"]
            elif "models" in data and isinstance(data["models"], list):
                model_items = data["models"]
        elif isinstance(data, list):
            model_items = data

        results: List[str] = []
        for item in model_items:
            if isinstance(item, dict):
                mid = item.get("id") or item.get("name") or item.get("model")
                if mid and isinstance(mid, str):
                    results.append(mid)
            elif isinstance(item, str) and item:
                results.append(item)

        # De-duplicate while preserving discovery order
        seen = set()
        deduped: List[str] = []
        for m in results:
            if m not in seen:
                seen.add(m)
                deduped.append(m)
        return deduped

    except Exception:
        return []


def get_provider_models(
    provider_id: str,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 3.5,
) -> List[str]:
    """
    Returns available models using: Official API + Dynamic /models Probe + Static Fallback.
    Attempts to probe live models from the endpoint; falls back cleanly to the static list if probing fails.
    """
    provider = get_provider(provider_id)
    fallback: List[str] = list(provider.get("models", [])) if provider else []

    target_base = (api_base or (provider.get("api_base") if provider else "") or "").strip()
    target_key = (api_key if api_key is not None else "") or ""

    # Attempt dynamic probe if endpoint is available
    if target_base:
        dynamic = fetch_dynamic_models(
            api_base=target_base,
            api_key=target_key,
            provider_id=provider_id,
            timeout=timeout,
        )
        if dynamic:
            return dynamic

    # Static fallback
    if fallback:
        return fallback

    if provider and provider.get("model"):
        return [provider["model"]]

    return []


def load_ai_config() -> Optional[Dict[str, Any]]:
    """Loads configuration from disk or returns None if uninitialized."""
    cfg_path = get_ai_config_file()
    if not cfg_path.is_file():
        return None
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and data.get("api_base"):
                return data
    except Exception:
        pass
    return None


def save_ai_config(cfg: Dict[str, Any]) -> None:
    """Saves configuration dictionary to disk."""
    cfg_path = get_ai_config_file()
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
