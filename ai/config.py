"""
Kapsel AI Configuration Manager.
Manages AI provider configurations, dynamic /models endpoint probing, and static fallback.
Loads and saves AI configuration from ~/.kapsel/ai/config.yaml.
All comments and docstrings are in English.
"""

import json
from pathlib import Path
import ssl
from typing import Any, Dict, List, Optional, Tuple
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
        "id": "deepseek",
        "name": "DeepSeek (Official API)",
        "api_base": "https://api.deepseek.com",
        "requires_key": True,
        "key_prompt": "Enter DeepSeek API Key (sk-...): ",
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow (硅基流动 Multi-Model)",
        "api_base": "https://api.siliconflow.com/v1",
        "requires_key": True,
        "key_prompt": "Enter SiliconFlow API Key (sk-...): ",
    },
    {
        "id": "openai",
        "name": "OpenAI (Official API)",
        "api_base": "https://api.openai.com/v1",
        "requires_key": True,
        "key_prompt": "Enter OpenAI API Key (sk-...): ",
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude (Official API)",
        "api_base": "https://api.anthropic.com",
        "requires_key": True,
        "key_prompt": "Enter Anthropic API Key (sk-ant-...): ",
    },
    {
        "id": "gemini",
        "name": "Google Gemini (Official API)",
        "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "requires_key": True,
        "key_prompt": "Enter Google AI Studio API Key (AIzaSy...): ",
    },
    {
        "id": "qwen",
        "name": "Alibaba Qwen / DashScope (阿里云百炼)",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "requires_key": True,
        "key_prompt": "Enter DashScope API Key (sk-...): ",
    },
    {
        "id": "zhipu",
        "name": "Zhipu AI / GLM (智谱清言)",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "requires_key": True,
        "key_prompt": "Enter Zhipu API Key: ",
    },
    {
        "id": "moonshot",
        "name": "Moonshot AI / Kimi (月之暗面)",
        "api_base": "https://api.moonshot.cn/v1",
        "requires_key": True,
        "key_prompt": "Enter Moonshot API Key (sk-...): ",
    },
    {
        "id": "minimax",
        "name": "MiniMax (名之梦 / 海螺)",
        "api_base": "https://api.minimax.chat/v1",
        "requires_key": True,
        "key_prompt": "Enter MiniMax API Key: ",
    },
    {
        "id": "xai",
        "name": "xAI Grok (Official API)",
        "api_base": "https://api.x.ai/v1",
        "requires_key": True,
        "key_prompt": "Enter xAI API Key: ",
    },
    {
        "id": "groq",
        "name": "Groq Cloud (Ultra-Fast LPU)",
        "api_base": "https://api.groq.com/openai/v1",
        "requires_key": True,
        "key_prompt": "Enter Groq API Key (gsk_...): ",
    },
    {
        "id": "mistral",
        "name": "Mistral AI (Official API)",
        "api_base": "https://api.mistral.ai/v1",
        "requires_key": True,
        "key_prompt": "Enter Mistral API Key: ",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (Unified Gateway)",
        "api_base": "https://openrouter.ai/api/v1",
        "requires_key": True,
        "key_prompt": "Enter OpenRouter API Key (sk-or-...): ",
    },
    {
        "id": "together",
        "name": "Together AI (Cloud Inference)",
        "api_base": "https://api.together.xyz/v1",
        "requires_key": True,
        "key_prompt": "Enter Together API Key: ",
    },
    {
        "id": "deepinfra",
        "name": "DeepInfra (Serverless Inference)",
        "api_base": "https://api.deepinfra.com/v1/openai",
        "requires_key": True,
        "key_prompt": "Enter DeepInfra API Key: ",
    },
    {
        "id": "cohere",
        "name": "Cohere (Official API)",
        "api_base": "https://api.cohere.com/v2",
        "requires_key": True,
        "key_prompt": "Enter Cohere API Key: ",
    },
    {
        "id": "ollama",
        "name": "Ollama (Local LLM - Free & Offline)",
        "api_base": "http://localhost:11434/v1",
        "requires_key": False,
        "key_prompt": "",
    },
    {
        "id": "lmstudio",
        "name": "LM Studio (Local OpenAI API)",
        "api_base": "http://localhost:1234/v1",
        "requires_key": False,
        "key_prompt": "",
    },
    {
        "id": "custom",
        "name": "Custom OpenAI-Compatible (OneAPI/vLLM)",
        "api_base": "",
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
    timeout: float = 6.0,
) -> Tuple[List[str], Optional[str]]:
    """
    Dynamically probes the endpoint for available models using standard /models endpoint.
    Supports OpenAI standard schema (data[].id), Cohere/Ollama (models[].name), and Anthropic.
    Returns (discovered_models, error_message). On failure, returns ([], error_message).
    """
    if not api_base:
        return [], "No API Base URL provided."

    clean_base = api_base.strip().rstrip("/")
    if not clean_base.startswith(("http://", "https://")):
        return [], f"Invalid URL scheme in '{api_base}'. URL must begin with http:// or https://"

    # Determine probe URL
    if clean_base.endswith("/models"):
        models_url = clean_base
    elif provider_id.lower() == "anthropic" and not clean_base.endswith("/v1"):
        models_url = f"{clean_base}/v1/models"
    else:
        models_url = f"{clean_base}/models"

    headers: Dict[str, str] = {
        "User-Agent": "Kapsel-AI/0.1.5",
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
                return [], f"HTTP status {status} from {models_url}"
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

        if not deduped:
            return [], f"Endpoint responded, but returned zero model entries."

        return deduped, None

    except urllib.error.HTTPError as e:
        if e.code == 401:
            err_msg = "HTTP 401 Unauthorized (Invalid API Key or unauthorized access)"
        elif e.code == 403:
            err_msg = "HTTP 403 Forbidden (Check model access permissions or account balance)"
        elif e.code == 404:
            err_msg = f"HTTP 404 Not Found (Endpoint '{models_url}' does not exist)"
        else:
            err_msg = f"HTTP {e.code}: {e.reason} ({models_url})"
        return [], err_msg
    except urllib.error.URLError as e:
        return [], f"Network connection failed: {e.reason} ({models_url})"
    except TimeoutError:
        return [], f"Connection timed out after {timeout}s ({models_url})"
    except Exception as e:
        return [], f"{type(e).__name__}: {e} ({models_url})"


def get_provider_models(
    provider_id: str,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 6.0,
) -> Tuple[List[str], Optional[str]]:
    """
    Dynamically probes provider endpoint for available models.
    Zero static preset models are used. Returns (models, error_message).
    If the API call fails, error_message is populated instead of falling back to default models.
    """
    provider = get_provider(provider_id)
    target_base = (api_base or (provider.get("api_base") if provider else "") or "").strip()
    target_key = (api_key if api_key is not None else "") or ""

    if not target_base:
        return [], "No API Base URL configured."

    return fetch_dynamic_models(
        api_base=target_base,
        api_key=target_key,
        provider_id=provider_id,
        timeout=timeout,
    )


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
