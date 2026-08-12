"""LLM clients: HA conversation agent and OpenAI-compatible endpoints."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from homeassistant.core import Context

from .const import (
    CONF_AGENT,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_LLM,
    CONF_MODE,
    CONF_MODEL,
    CONF_OPENAI,
    MODE_HA_CONVERSATION,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0
CHAT_COMPLETIONS_PATH = "/chat/completions"


class LLMError(Exception):
    """Error completing an LLM request."""


class LLMClient(ABC):
    """Interface of an LLM client."""

    @abstractmethod
    async def async_complete(self, system: str, user: str) -> str:
        """Return the model response for the system/user prompts."""


class HAConversationLLM(LLMClient):
    """Calls HA's conversation agent via conversation.async_converse.

    Requires HA >= 2025.2 (the ``async_converse`` signature had no
    ``extra_system_prompt`` parameter before that version).
    """

    def __init__(self, hass: Any, agent: str = "") -> None:
        self._hass = hass
        self._agent = agent or None

    async def async_complete(self, system: str, user: str) -> str:
        from homeassistant.components import conversation

        config = getattr(self._hass, "config", None)
        language = getattr(config, "language", None) if config is not None else None
        try:
            result = await conversation.async_converse(
                hass=self._hass,
                text=user,
                conversation_id=None,
                context=Context(),
                language=language,
                agent_id=self._agent,
                extra_system_prompt=system,  # type: ignore[call-arg]
            )
        except Exception as err:
            msg = f"conversation agent failed: {err}"
            raise LLMError(msg) from err

        speech: dict = (result.response.speech or {}).get("plain") or {}
        text = speech.get("speech", "")
        if not text:
            msg = "conversation agent returned no text"
            raise LLMError(msg)
        return text


class OpenAICompatLLM(LLMClient):
    """LLM via an OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._transport = transport

    async def async_complete(self, system: str, user: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        url = f"{self._base_url}{CHAT_COMPLETIONS_PATH}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(DEFAULT_TIMEOUT),
                transport=self._transport,
            ) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as err:
            msg = f"OpenAI endpoint failed: {err}"
            raise LLMError(msg) from err

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as err:
            msg = f"invalid OpenAI response: {data}"
            raise LLMError(msg) from err


class FallbackLLM(LLMClient):
    """Tries the primary and, on failure, delegates to the fallback."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self.primary = primary
        self.fallback = fallback

    async def async_complete(self, system: str, user: str) -> str:
        try:
            return await self.primary.async_complete(system, user)
        except LLMError as err:
            _LOGGER.warning("Primary LLM failed, using fallback: %s", err)
            return await self.fallback.async_complete(system, user)


def build_llm(hass: Any, config: dict) -> LLMClient:
    """Build the LLM client from the configuration, falling back to the other mode."""
    llm_cfg = config.get(CONF_LLM, {})
    openai_cfg = llm_cfg.get(CONF_OPENAI, {})
    ha_llm = HAConversationLLM(hass, llm_cfg.get(CONF_AGENT, ""))
    openai_llm = OpenAICompatLLM(
        base_url=openai_cfg.get(CONF_BASE_URL, ""),
        api_key=openai_cfg.get(CONF_API_KEY, ""),
        model=openai_cfg.get(CONF_MODEL, ""),
    )
    if llm_cfg.get(CONF_MODE, MODE_HA_CONVERSATION) == MODE_HA_CONVERSATION:
        return FallbackLLM(ha_llm, openai_llm)
    return FallbackLLM(openai_llm, ha_llm)
