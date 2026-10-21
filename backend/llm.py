"""Shared DeepSeek client, using its OpenAI-compatible API."""
import os

from openai import OpenAI

import config

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
        _client = OpenAI(
            api_key=api_key,
            base_url=config.DEEPSEEK_BASE_URL,
            timeout=config.DEEPSEEK_TIMEOUT_SECONDS,
        )
    return _client


def reset_client() -> None:
    global _client
    if _client is not None:
        _client.close()
    _client = None
