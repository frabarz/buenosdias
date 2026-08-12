"""Clientes LLM: agente de conversación de HA y endpoints OpenAI-compatibles."""

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
    """Error al completar una petición LLM."""


class LLMClient(ABC):
    """Interfaz de un cliente LLM."""

    @abstractmethod
    async def async_complete(self, system: str, user: str) -> str:
        """Devuelve la respuesta del modelo para los prompts system/user."""


class HAConversationLLM(LLMClient):
    """Llama al agente de conversación de HA vía conversation.async_converse.

    Requiere HA >= 2025.2 (la firma de ``async_converse`` no tenía el
    parámetro ``extra_system_prompt`` antes de esa versión).
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
            msg = f"agente de conversación falló: {err}"
            raise LLMError(msg) from err

        speech: dict = (result.response.speech or {}).get("plain") or {}
        text = speech.get("speech", "")
        if not text:
            msg = "el agente de conversación no devolvió texto"
            raise LLMError(msg)
        return text


class OpenAICompatLLM(LLMClient):
    """LLM vía un endpoint /chat/completions compatible con OpenAI."""

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
            msg = f"endpoint OpenAI falló: {err}"
            raise LLMError(msg) from err

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as err:
            msg = f"respuesta OpenAI inválida: {data}"
            raise LLMError(msg) from err


class FallbackLLM(LLMClient):
    """Prueba el primario y, si falla, delega en el de respaldo."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self.primary = primary
        self.fallback = fallback

    async def async_complete(self, system: str, user: str) -> str:
        try:
            return await self.primary.async_complete(system, user)
        except LLMError as err:
            _LOGGER.warning("LLM primario falló, usando respaldo: %s", err)
            return await self.fallback.async_complete(system, user)


def build_llm(hass: Any, config: dict) -> LLMClient:
    """Construye el cliente LLM según la configuración, con fallback al otro modo."""
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
