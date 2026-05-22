"""
Nvidia NIM key rotation client.
Manages multiple API keys and automatically rotates on rate-limit or failure.
"""
import os
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("scholarsleuth.client")

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "openai/gpt-oss-120b"

_api_keys = []
_keys_str = os.getenv("NVIDIA_API_KEYS", "")
if _keys_str:
    _api_keys = [k.strip() for k in _keys_str.split(",") if k.strip() and not k.strip().startswith("your_")]

if not _api_keys:
    _single_key = os.getenv("NVIDIA_API_KEY", "")
    if _single_key and not _single_key.startswith("your_"):
        _api_keys = [_single_key]

nim_clients = [AsyncOpenAI(api_key=key, base_url=NIM_BASE_URL) for key in _api_keys]
current_key_index = 0

if nim_clients:
    logger.info(f"Nvidia NIM key rotation initialized with {len(nim_clients)} key(s).")
else:
    logger.warning("No valid Nvidia NIM API keys found. LLM Sampling will fall back to Mock responses.")


async def call_nim(messages: list[dict], temperature: float = 0.7, max_tokens: int = 1024) -> str:
    """
    Call Nvidia NIM with automatic key rotation.
    Returns the generated text string.
    Raises RuntimeError if all keys fail.
    """
    global current_key_index

    if not nim_clients:
        return None  # Signals caller to use mock fallback

    num_keys = len(nim_clients)
    last_exception = None

    for attempt in range(num_keys):
        idx = (current_key_index + attempt) % num_keys
        client = nim_clients[idx]
        logger.info(f"Dispatching prompt to NIM model {NIM_MODEL} using key index {idx} (attempt {attempt + 1}/{num_keys})")

        try:
            response = await client.chat.completions.create(
                model=NIM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            current_key_index = idx
            llm_text = response.choices[0].message.content
            logger.info("Successfully received response from Nvidia NIM.")
            return llm_text
        except Exception as e:
            logger.warning(f"Nvidia NIM key at index {idx} failed: {e}. Rotating...")
            last_exception = e

    logger.error("All configured Nvidia NIM keys failed.")
    if last_exception:
        raise last_exception
    raise RuntimeError("No Nvidia NIM API key succeeded.")
