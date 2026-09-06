"""
Kapsel Native AI Client.
Powered by the official 'openai' Python SDK for high-performance,
streamlined communication with OpenAI-compatible endpoints (DeepSeek, Ollama, Gemini, OpenAI, etc.).
All comments and descriptions are in English.
"""

import sys
from typing import Any, Dict, List, Optional
from rich.console import Console

try:
    from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APIConnectionError
    HAS_OPENAI_LIB = True
except ImportError:
    HAS_OPENAI_LIB = False


class AiClient:
    """Lightweight client using the OpenAI Python package."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        timeout: float = 35.0,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key or "none"
        self.model = model
        self.timeout = timeout

        if not HAS_OPENAI_LIB:
            raise RuntimeError(
                "The 'openai' Python library is required. Please run: pip install openai>=1.0.0"
            )

        self._client = OpenAI(
            base_url=self.api_base,
            api_key=self.api_key,
            timeout=self.timeout,
        )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        stream: bool = False,
        console: Optional[Console] = None,
    ) -> str:
        """
        Executes a chat completion request.
        If stream=True, prints tokens in real-time to stdout.
        Returns the complete response text.
        """
        try:
            if stream:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore
                    temperature=temperature,
                    stream=True,
                )
                full_chunks = []
                for chunk in response:
                    content = chunk.choices[0].delta.content if chunk.choices else ""
                    if content:
                        sys.stdout.write(content)
                        sys.stdout.flush()
                        full_chunks.append(content)
                return "".join(full_chunks)
            else:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore
                    temperature=temperature,
                    stream=False,
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
                return ""

        except AuthenticationError as e:
            raise RuntimeError(f"Authentication Failed (Invalid API Key): {e.message}")
        except RateLimitError as e:
            raise RuntimeError(f"API Rate Limit Exceeded or Quota Depleted: {e.message}")
        except APIConnectionError as e:
            raise RuntimeError(f"Cannot connect to AI endpoint ({self.api_base}): {e.message}")
        except APIError as e:
            raise RuntimeError(f"API Error ({e.code}): {e.message}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with AI: {e}")
