"""Config flow for the buenosdias integration."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import httpx
import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import httpx_client
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .config_schema import DATE_RE, WEEKDAY_VALUES
from .const import (
    CONF_AGENT,
    CONF_BASE_URL,
    CONF_CALENDAR,
    CONF_CONFIRM_REMOVE,
    CONF_ENTITY_ID,
    CONF_EXCLUDE,
    CONF_FEEDS,
    CONF_FERIADOS,
    CONF_HOLIDAY_CALENDAR,
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

_LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3"
CONNECTION_TIMEOUT = 10.0

_LLM_MODES: list[SelectOptionDict] = [
    SelectOptionDict(
        label="Home Assistant conversation agent",
        value=MODE_HA_CONVERSATION,
    ),
    SelectOptionDict(
        label="OpenAI-compatible endpoint",
        value=MODE_OPENAI_COMPATIBLE,
    ),
]

STEP_USER_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODE, default=MODE_HA_CONVERSATION): SelectSelector(
            SelectSelectorConfig(
                options=_LLM_MODES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="llm_mode",
            ),
        ),
    },
)

STEP_USER_AGENT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AGENT): EntitySelector(
            EntitySelectorConfig(domain="conversation"),
        ),
    },
)

STEP_USER_OPENAI_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL),
        ),
        vol.Optional(CONF_MODEL): TextSelector(),
        vol.Optional(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD),
        ),
    },
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD),
        ),
    },
)

_DAYS: list[SelectOptionDict] = [
    SelectOptionDict(label=day.capitalize(), value=day) for day in WEEKDAY_VALUES
]

_KINDS: list[SelectOptionDict] = [
    SelectOptionDict(label="News", value=KIND_NEWS),
    SelectOptionDict(label="Events", value=KIND_EVENTS),
]

STEP_LLM_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAX_CHARS): NumberSelector(
            NumberSelectorConfig(
                min=100,
                max=20000,
                step=100,
                mode=NumberSelectorMode.BOX,
            ),
        ),
    },
)

STEP_TTS_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain="tts"),
        ),
        vol.Required(CONF_MEDIA_PLAYER): EntitySelector(
            EntitySelectorConfig(domain="media_player"),
        ),
        vol.Optional(CONF_LANGUAGE, default="es-ES"): TextSelector(),
        vol.Optional(CONF_VOLUME, default=0.6): NumberSelector(
            NumberSelectorConfig(min=0, max=1, step=0.05, mode=NumberSelectorMode.BOX),
        ),
        vol.Optional(CONF_RESTORE_VOLUME, default=True): BooleanSelector(),
    },
)

STEP_SOURCES_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_WEATHER, default=[]): EntitySelector(
            EntitySelectorConfig(domain="weather", multiple=True),
        ),
        vol.Optional(CONF_CALENDAR, default=[]): EntitySelector(
            EntitySelectorConfig(domain="calendar", multiple=True),
        ),
        vol.Optional(CONF_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain="sensor", multiple=True),
        ),
    },
)

STEP_SCHEDULE_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TIME): TimeSelector(),
        vol.Optional(CONF_TIME_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="sensor"),
        ),
        vol.Optional(CONF_SKIP_DAYS, default=[]): SelectSelector(
            SelectSelectorConfig(
                options=_DAYS,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="weekday",
            ),
        ),
        vol.Optional(CONF_FERIADOS, default=""): TextSelector(
            TextSelectorConfig(multiline=True),
        ),
        vol.Optional(CONF_HOLIDAY_CALENDAR): EntitySelector(
            EntitySelectorConfig(domain="calendar"),
        ),
        vol.Optional(CONF_SKIP_IF_EMITTED, default=True): BooleanSelector(),
    },
)

STEP_PERSONA_OPTIONS_SCHEMA = vol.Schema(
    {vol.Optional(CONF_PERSONA, default=""): TextSelector()},
)

STEP_RSS_FEED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL),
        ),
        vol.Optional(CONF_KIND, default=KIND_NEWS): SelectSelector(
            SelectSelectorConfig(
                options=_KINDS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="feed_kind",
            ),
        ),
        vol.Optional(CONF_MAX_AGE_HOURS, default=72): NumberSelector(
            NumberSelectorConfig(min=1, max=8760, step=1, mode=NumberSelectorMode.BOX),
        ),
        vol.Optional(CONF_MAX_ITEMS, default=5): NumberSelector(
            NumberSelectorConfig(min=1, max=50, step=1, mode=NumberSelectorMode.BOX),
        ),
        vol.Optional(CONF_TAGS, default=""): TextSelector(),
        vol.Optional(CONF_EXCLUDE, default=""): TextSelector(
            TextSelectorConfig(multiline=True),
        ),
    },
)

STEP_RSS_EDIT_SCHEMA = STEP_RSS_FEED_SCHEMA.extend(
    {vol.Optional(CONF_CONFIRM_REMOVE, default=False): BooleanSelector()},
)


async def _async_validate_connection(
    hass: HomeAssistant,
    base_url: str,
    api_key: str | None,
) -> str | None:
    """Probe an OpenAI-compatible endpoint and return an error key or None."""
    url = f"{base_url.rstrip('/')}/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        client = httpx_client.get_async_client(hass, verify_ssl=True)
        response = await client.get(
            url,
            headers=headers,
            timeout=httpx.Timeout(CONNECTION_TIMEOUT),
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as err:
        if err.response.status_code in (401, 403):
            return "invalid_auth"
        _LOGGER.warning(
            "OpenAI-compatible endpoint %s returned status %s",
            base_url,
            err.response.status_code,
        )
        return "cannot_connect"
    except (httpx.RequestError, TimeoutError):
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error validating %s", base_url)
        return "unknown"
    return None


def _build_llm(
    mode: str,
    *,
    agent: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Build the llm connection section from validated user input."""
    llm: dict[str, Any] = {CONF_MODE: mode}
    if mode == MODE_HA_CONVERSATION:
        if agent:
            llm[CONF_AGENT] = agent
        return llm

    openai: dict[str, Any] = {
        CONF_BASE_URL: (base_url or "").strip(),
        CONF_MODEL: (model or DEFAULT_MODEL).strip(),
    }
    if api_key:
        openai[CONF_API_KEY] = api_key.strip()
    llm[CONF_OPENAI] = openai
    return llm


class BuenosdiasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for buenosdias."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry,
    ) -> BuenosdiasOptionsFlowHandler:
        """Get the options flow for this handler."""
        return BuenosdiasOptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step: choose the LLM connection mode."""
        if user_input is not None:
            mode = user_input[CONF_MODE]
            if mode == MODE_HA_CONVERSATION:
                return await self.async_step_user_agent()
            return await self.async_step_user_openai()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_MODE_SCHEMA,
                {CONF_MODE: self._current_llm().get(CONF_MODE)},
            ),
        )

    async def async_step_user_agent(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the conversation agent step."""
        if user_input is not None:
            agent = (user_input.get(CONF_AGENT) or "").strip()
            return await self._finish_llm(_build_llm(MODE_HA_CONVERSATION, agent=agent))
        return self.async_show_form(
            step_id="user_agent",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_AGENT_SCHEMA,
                {CONF_AGENT: self._current_llm().get(CONF_AGENT)},
            ),
        )

    async def async_step_user_openai(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the OpenAI-compatible endpoint step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = (user_input.get(CONF_BASE_URL) or "").strip()
            model = (user_input.get(CONF_MODEL) or "").strip()
            api_key = (user_input.get(CONF_API_KEY) or "").strip()

            if not base_url:
                errors[CONF_BASE_URL] = "missing_base_url"
            else:
                try:
                    cv.url(base_url)
                except vol.Invalid:
                    errors[CONF_BASE_URL] = "invalid_url"
                if not errors:
                    if not api_key and self.source == SOURCE_RECONFIGURE:
                        api_key = (
                            self._current_llm()
                            .get(CONF_OPENAI, {})
                            .get(CONF_API_KEY, "")
                        )
                    error = await _async_validate_connection(
                        self.hass,
                        base_url,
                        api_key,
                    )
                    if error:
                        errors["base"] = error

            if not errors:
                return await self._finish_llm(
                    _build_llm(
                        MODE_OPENAI_COMPATIBLE,
                        base_url=base_url,
                        model=model,
                        api_key=api_key,
                    ),
                )

        openai = self._current_llm().get(CONF_OPENAI, {})
        return self.async_show_form(
            step_id="user_openai",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_OPENAI_SCHEMA,
                {
                    CONF_BASE_URL: openai.get(CONF_BASE_URL),
                    CONF_MODEL: openai.get(CONF_MODEL),
                },
            ),
            description_placeholders={
                "base_url_example": openai.get(CONF_BASE_URL)
                or "http://localhost:11434/v1",
            },
            errors=errors,
        )

    async def _finish_llm(self, llm: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the entry with the validated llm connection."""
        await self.async_set_unique_id(DOMAIN)
        entry_data = {CONF_LLM: llm}
        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=entry_data,
            )
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=entry_data,
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Buenos Días", data=entry_data)

    async def async_step_import(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Import a YAML configuration into a config entry."""
        if user_input is None:
            return self.async_abort(reason="no_config")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        yaml_llm = dict(user_input.get(CONF_LLM, {}))
        data_llm: dict[str, Any] = {}
        for key in (CONF_MODE, CONF_AGENT, CONF_OPENAI):
            if key in yaml_llm:
                data_llm[key] = yaml_llm.pop(key)

        options: dict[str, Any] = {}
        if yaml_llm:
            options[CONF_LLM] = yaml_llm
        options[CONF_TTS] = user_input.get(CONF_TTS, {})
        options[CONF_SOURCES] = user_input.get(CONF_SOURCES, {})
        options[CONF_SCHEDULE] = user_input.get(CONF_SCHEDULE, {})
        options[CONF_PERSONA] = user_input.get(CONF_PERSONA, "")

        return self.async_create_entry(
            title="Buenos Días",
            data={CONF_LLM: data_llm},
            options=options,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Reconfigure the LLM connection of an existing entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_mismatch()
        return await self.async_step_user(user_input)

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored API key is invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Dialog that asks for a new API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self._get_reauth_entry()
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            base_url = (
                entry.data.get(CONF_LLM, {}).get(CONF_OPENAI, {}).get(CONF_BASE_URL, "")
            )
            error = await _async_validate_connection(self.hass, base_url, api_key)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_mismatch()
                data_updates = {
                    CONF_LLM: {
                        **entry.data.get(CONF_LLM, {}),
                        CONF_OPENAI: {
                            **entry.data.get(CONF_LLM, {}).get(CONF_OPENAI, {}),
                            CONF_API_KEY: api_key,
                        },
                    },
                }
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data_updates,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    def _current_llm(self) -> Mapping[str, Any]:
        """Return the stored llm connection of the entry being reconfigured."""
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
        elif self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
        else:
            return {}
        return entry.data.get(CONF_LLM, {})


def _parse_tags(raw: Any) -> list[str]:
    """Split a free-text tags field into a list."""
    if not raw:
        return []
    return [
        part.strip()
        for part in str(raw).replace(",", "\n").splitlines()
        if part.strip()
    ]


def _normalize_time(value: Any) -> str | None:
    """Normalize a time value to 'HH:MM', dropping any seconds."""
    if not value:
        return None
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        return None
    return f"{parts[0]}:{parts[1]}"


def _feed_from_user_input(
    user_input: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    """Build an RSS feed dict from validated user input, or its errors."""
    errors: dict[str, str] = {}
    url = (user_input.get(CONF_URL) or "").strip()
    if not url:
        errors[CONF_URL] = "invalid_feed_url"
    else:
        try:
            cv.url(url)
        except vol.Invalid:
            errors[CONF_URL] = "invalid_feed_url"
    if errors:
        return None, errors
    return (
        {
            CONF_URL: url,
            CONF_KIND: user_input.get(CONF_KIND, KIND_NEWS),
            CONF_MAX_AGE_HOURS: int(user_input.get(CONF_MAX_AGE_HOURS, 72)),
            CONF_MAX_ITEMS: int(user_input.get(CONF_MAX_ITEMS, 5)),
            CONF_TAGS: _parse_tags(user_input.get(CONF_TAGS)),
            CONF_EXCLUDE: _parse_tags(user_input.get(CONF_EXCLUDE)),
        },
        None,
    )


class BuenosdiasOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle buenosdias options (behavioral settings, no credentials)."""

    VERSION = 1

    def __init__(self, config_entry):
        """Initialize the options flow."""
        super().__init__(config_entry)
        self._feed_index: int | None = None

    # ---------- helpers ----------

    def _current_options(self) -> dict[str, Any]:
        return dict(self.options)

    def _current_feeds(self) -> list[dict[str, Any]]:
        return (
            self.config_entry.options.get(CONF_SOURCES, {})
            .get(CONF_RSS, {})
            .get(CONF_FEEDS, [])
        )

    def _replace_options(self, options: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=options)

    def _set_feeds(self, options: dict[str, Any], feeds: list[dict[str, Any]]) -> None:
        sources = dict(options.get(CONF_SOURCES, {}))
        rss = dict(sources.get(CONF_RSS, {}))
        rss[CONF_FEEDS] = feeds
        sources[CONF_RSS] = rss
        options[CONF_SOURCES] = sources

    def _install_feed_steps(self) -> None:
        """Register one menu step per existing feed so indices map correctly."""
        for i in range(len(self._current_feeds())):
            if hasattr(self, f"async_step_feed_{i}"):
                continue
            idx = i

            async def _step(
                user_input: dict[str, Any] | None = None,
                _idx: int = idx,
            ) -> ConfigFlowResult:
                return await self.async_step_rss_edit(user_input, _idx)

            setattr(self, f"async_step_feed_{idx}", _step)

    # ---------- main menu ----------

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose which part of the configuration to edit."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "llm",
                "tts",
                "sources",
                "rss_feeds",
                "schedule",
                "persona",
            ],
        )

    # ---------- llm ----------

    async def async_step_llm(self, user_input=None):
        """Edit the script length; connection settings live in Reconfigure."""
        if user_input is not None:
            options = self._current_options()
            options.setdefault(CONF_LLM, {})
            options[CONF_LLM][CONF_MAX_CHARS] = int(user_input[CONF_MAX_CHARS])
            return self._replace_options(options)

        llm = self._current_options().get(CONF_LLM, {})
        suggested = {CONF_MAX_CHARS: llm.get(CONF_MAX_CHARS, 2000)}
        return self.async_show_form(
            step_id="llm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_LLM_OPTIONS_SCHEMA,
                suggested,
            ),
        )

    # ---------- tts ----------

    async def async_step_tts(self, user_input=None):
        """Edit the TTS engine and media player."""
        if user_input is not None:
            options = self._current_options()
            options[CONF_TTS] = {
                CONF_ENTITY_ID: user_input[CONF_ENTITY_ID],
                CONF_MEDIA_PLAYER: user_input[CONF_MEDIA_PLAYER],
                CONF_LANGUAGE: user_input.get(CONF_LANGUAGE, "es-ES"),
                CONF_VOLUME: float(user_input.get(CONF_VOLUME, 0.6)),
                CONF_RESTORE_VOLUME: bool(user_input.get(CONF_RESTORE_VOLUME, True)),
            }
            return self._replace_options(options)

        return self.async_show_form(
            step_id="tts",
            data_schema=self.add_suggested_values_to_schema(
                STEP_TTS_OPTIONS_SCHEMA,
                self._current_options().get(CONF_TTS, {}),
            ),
        )

    # ---------- sources ----------

    async def async_step_sources(self, user_input=None):
        """Edit the weather, calendar and sensor sources."""
        current_sources = self._current_options().get(CONF_SOURCES, {})
        if user_input is not None:
            options = self._current_options()
            options[CONF_SOURCES] = {
                CONF_WEATHER: user_input.get(CONF_WEATHER) or [],
                CONF_CALENDAR: user_input.get(CONF_CALENDAR) or [],
                CONF_SENSORS: user_input.get(CONF_SENSORS) or [],
                CONF_RSS: current_sources.get(CONF_RSS, {}),
            }
            return self._replace_options(options)

        return self.async_show_form(
            step_id="sources",
            data_schema=self.add_suggested_values_to_schema(
                STEP_SOURCES_OPTIONS_SCHEMA,
                current_sources,
            ),
        )

    # ---------- rss feeds ----------

    async def async_step_rss_feeds(self, user_input=None):
        """List the existing feeds and the option to add a new one."""
        self._install_feed_steps()
        menu: dict[str, str] = {"rss_add": "Add a feed"}
        for i, feed in enumerate(self._current_feeds()):
            menu[f"feed_{i}"] = feed.get(CONF_URL) or f"Feed {i + 1}"
        return self.async_show_menu(step_id="rss_feeds", menu_options=menu)

    async def async_step_rss_add(self, user_input=None):
        """Add a new feed (news or events)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            feed, errors = _feed_from_user_input(user_input)
            if feed is not None:
                options = self._current_options()
                feeds = list(self._current_feeds())
                feeds.append(feed)
                self._set_feeds(options, feeds)
                return self._replace_options(options)
        return self.async_show_form(
            step_id="rss_add",
            data_schema=STEP_RSS_FEED_SCHEMA,
            errors=errors,
        )

    async def async_step_rss_edit(
        self,
        user_input: dict[str, Any] | None = None,
        index: int | None = None,
    ):
        """Edit or remove an existing feed."""
        self._feed_index = index if index is not None else self._feed_index
        errors: dict[str, str] = {}
        feeds = self._current_feeds()
        feed_index = self._feed_index or 0
        if not 0 <= feed_index < len(feeds):
            errors["base"] = "invalid_feed_index"
        if user_input is not None and not errors:
            if user_input.get(CONF_CONFIRM_REMOVE):
                new_feeds = list(feeds)
                new_feeds.pop(feed_index)
                options = self._current_options()
                self._set_feeds(options, new_feeds)
                return self._replace_options(options)
            feed, errors = _feed_from_user_input(user_input)
            if feed is not None:
                new_feeds = list(feeds)
                new_feeds[feed_index] = feed
                options = self._current_options()
                self._set_feeds(options, new_feeds)
                return self._replace_options(options)
        if errors:
            return self.async_show_form(
                step_id="rss_edit",
                data_schema=STEP_RSS_EDIT_SCHEMA,
                errors=errors,
            )
        feed = feeds[feed_index]
        suggested = {
            CONF_URL: feed.get(CONF_URL, ""),
            CONF_KIND: feed.get(CONF_KIND, KIND_NEWS),
            CONF_MAX_AGE_HOURS: feed.get(CONF_MAX_AGE_HOURS, 72),
            CONF_MAX_ITEMS: feed.get(CONF_MAX_ITEMS, 5),
            CONF_TAGS: ", ".join(feed.get(CONF_TAGS, [])),
            CONF_EXCLUDE: ", ".join(feed.get(CONF_EXCLUDE, [])),
        }
        return self.async_show_form(
            step_id="rss_edit",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RSS_EDIT_SCHEMA,
                suggested,
            ),
        )

    # ---------- schedule ----------

    async def async_step_schedule(self, user_input=None):
        """Edit the alarm schedule."""
        errors: dict[str, str] = {}
        if user_input is not None:
            raw = (user_input.get(CONF_FERIADOS) or "").strip()
            feriados = [line.strip() for line in raw.splitlines() if line.strip()]
            if any(not re.fullmatch(DATE_RE, day) for day in feriados):
                errors[CONF_FERIADOS] = "invalid_date"
            else:
                options = self._current_options()
                options[CONF_SCHEDULE] = {
                    CONF_TIME: _normalize_time(user_input.get(CONF_TIME)),
                    CONF_TIME_ENTITY: user_input.get(CONF_TIME_ENTITY) or "",
                    CONF_SKIP_DAYS: user_input.get(CONF_SKIP_DAYS) or [],
                    CONF_FERIADOS: feriados,
                    CONF_HOLIDAY_CALENDAR: user_input.get(CONF_HOLIDAY_CALENDAR) or "",
                    CONF_SKIP_IF_EMITTED: bool(
                        user_input.get(CONF_SKIP_IF_EMITTED, True),
                    ),
                }
                return self._replace_options(options)

        schedule = self._current_options().get(CONF_SCHEDULE, {})
        suggested = {
            CONF_TIME: _normalize_time(schedule.get(CONF_TIME)),
            CONF_TIME_ENTITY: schedule.get(CONF_TIME_ENTITY),
            CONF_SKIP_DAYS: schedule.get(CONF_SKIP_DAYS, []),
            CONF_FERIADOS: "\n".join(schedule.get(CONF_FERIADOS, [])),
            CONF_HOLIDAY_CALENDAR: schedule.get(CONF_HOLIDAY_CALENDAR),
            CONF_SKIP_IF_EMITTED: bool(schedule.get(CONF_SKIP_IF_EMITTED, True)),
        }
        return self.async_show_form(
            step_id="schedule",
            data_schema=self.add_suggested_values_to_schema(
                STEP_SCHEDULE_OPTIONS_SCHEMA,
                suggested,
            ),
            errors=errors,
        )

    # ---------- persona ----------

    async def async_step_persona(self, user_input=None):
        """Edit the persona that controls the script style."""
        if user_input is not None:
            options = self._current_options()
            options[CONF_PERSONA] = (user_input.get(CONF_PERSONA) or "").strip()
            return self._replace_options(options)
        suggested = {CONF_PERSONA: self._current_options().get(CONF_PERSONA, "")}
        return self.async_show_form(
            step_id="persona",
            data_schema=self.add_suggested_values_to_schema(
                STEP_PERSONA_OPTIONS_SCHEMA,
                suggested,
            ),
        )
