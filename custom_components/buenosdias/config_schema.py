"""Esquema de configuración de buenosdias."""

from __future__ import annotations

import voluptuous as vol

from .const import (
    CONF_AGENT,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CALENDAR,
    CONF_ENTITY_ID,
    CONF_FEEDS,
    CONF_FERIADOS,
    CONF_KIND,
    CONF_LANGUAGE,
    CONF_LLM,
    CONF_MAX_AGE_HOURS,
    CONF_MAX_CHARS,
    CONF_MAX_ITEMS,
    CONF_MEDIA_PLAYER,
    CONF_MODE,
    CONF_MODEL,
    CONF_OPENAI,
    CONF_PERSONA,
    CONF_RESTORE_VOLUME,
    CONF_RSS,
    CONF_SCHEDULE,
    CONF_SENSORS,
    CONF_SKIP_DAYS,
    CONF_SKIP_IF_EMITTED,
    CONF_SOURCES,
    CONF_TAGS,
    CONF_TIME,
    CONF_TIME_ENTITY,
    CONF_TTS,
    CONF_URL,
    CONF_VOLUME,
    CONF_WEATHER,
    DOMAIN,
    KIND_EVENTS,
    KIND_NEWS,
    MODE_HA_CONVERSATION,
    MODE_OPENAI_COMPATIBLE,
)

TIME_RE = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
DATE_RE = r"^\d{4}-\d{2}-\d{2}$"
WEEKDAY_VALUES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _entity_list() -> vol.All:
    return vol.All([vol.All(str, vol.Length(min=1))])


OPENAI_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BASE_URL, default="http://localhost:11434/v1"): vol.All(
            str, vol.Length(min=1)
        ),
        vol.Optional(CONF_API_KEY, default=""): str,
        vol.Optional(CONF_MODEL, default="llama3"): vol.All(str, vol.Length(min=1)),
    },
    extra=vol.ALLOW_EXTRA,
)

LLM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MODE, default=MODE_HA_CONVERSATION): vol.In(
            [MODE_HA_CONVERSATION, MODE_OPENAI_COMPATIBLE]
        ),
        vol.Optional(CONF_AGENT, default=""): str,
        vol.Optional(CONF_MAX_CHARS, default=2000): vol.All(
            vol.Coerce(int), vol.Range(min=100, max=20000)
        ),
        vol.Optional(CONF_OPENAI, default={}): vol.All(dict, OPENAI_SCHEMA),
    },
    extra=vol.ALLOW_EXTRA,
)

TTS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTITY_ID, default=""): str,
        vol.Optional(CONF_MEDIA_PLAYER, default=""): str,
        vol.Optional(CONF_LANGUAGE, default="es-ES"): vol.All(
            str, vol.Length(min=2)
        ),
        vol.Optional(CONF_VOLUME, default=0.6): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=1.0)
        ),
        vol.Optional(CONF_RESTORE_VOLUME, default=True): bool,
    },
    extra=vol.ALLOW_EXTRA,
)

KIND_VALUES = [KIND_NEWS, KIND_EVENTS]

RSS_FEED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONF_KIND, default=KIND_NEWS): vol.In(KIND_VALUES),
        vol.Optional(CONF_MAX_AGE_HOURS, default=72): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_MAX_ITEMS, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=50)
        ),
        vol.Optional(CONF_TAGS, default=[]): vol.All(
            [vol.All(str, vol.Length(min=1))]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

RSS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FEEDS, default=[]): vol.All(
            [vol.All(dict, RSS_FEED_SCHEMA)]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SOURCES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_WEATHER, default=[]): _entity_list(),
        vol.Optional(CONF_CALENDAR, default=[]): _entity_list(),
        vol.Optional(CONF_SENSORS, default=[]): _entity_list(),
        vol.Optional(CONF_RSS, default={}): vol.All(dict, RSS_SCHEMA),
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TIME, default="07:00"): vol.Match(TIME_RE),
        vol.Optional(CONF_TIME_ENTITY, default=""): vol.All(
            str, vol.Length(min=0)
        ),
        vol.Optional(CONF_SKIP_DAYS, default=[]): vol.All(
            [vol.In(WEEKDAY_VALUES)]
        ),
        vol.Optional(CONF_FERIADOS, default=[]): vol.All([vol.Match(DATE_RE)]),
        vol.Optional(CONF_SKIP_IF_EMITTED, default=True): bool,
    },
    extra=vol.ALLOW_EXTRA,
)

BUENOSDIAS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LLM, default={}): vol.All(dict, LLM_SCHEMA),
        vol.Optional(CONF_TTS, default={}): vol.All(dict, TTS_SCHEMA),
        vol.Optional(CONF_SOURCES, default={}): vol.All(dict, SOURCES_SCHEMA),
        vol.Optional(CONF_SCHEDULE, default={}): vol.All(dict, SCHEDULE_SCHEMA),
        vol.Optional(CONF_PERSONA, default=""): str,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): BUENOSDIAS_SCHEMA}, extra=vol.ALLOW_EXTRA
)
