"""Recolección de contexto desde feeds RSS (noticias y eventos)."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from .const import (
    CONF_KIND,
    CONF_MAX_AGE_HOURS,
    CONF_MAX_ITEMS,
    CONF_TAGS,
    CONF_URL,
    KIND_EVENTS,
    KIND_NEWS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_AGE_HOURS = 72
DEFAULT_MAX_ITEMS = 5
DEFAULT_TIMEOUT = 10.0
USER_AGENT = "buenosdias/0.1"
SUMMARY_MAX_LEN = 500


def _normalize_title(title: str) -> str:
    """Normaliza un título para deduplicar entradas repetidas."""
    return re.sub(r"[\s\W_]+", "", (title or "").lower())


def _entry_published(entry: Any) -> datetime | None:
    """Devuelve la fecha de publicación (UTC) de una entrada, o None."""
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if not struct:
            continue
        try:
            return datetime(
                struct[0], struct[1], struct[2], struct[3], struct[4], struct[5],
                tzinfo=timezone.utc,
            )
        except (TypeError, ValueError):
            continue
    return None


def _entry_brief(entry: Any, feed_title: str | None) -> dict:
    """Extrae un brief serializable de una entrada RSS."""
    published = _entry_published(entry)
    summary = entry.get("summary") or entry.get("description") or ""
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    return {
        "title": entry.get("title", ""),
        "summary": summary[:SUMMARY_MAX_LEN],
        "link": entry.get("link", ""),
        "published": published.isoformat(timespec="seconds") if published else None,
        "source": feed_title,
    }


def parse_feed_content(content: bytes, feed: dict) -> list[dict]:
    """Parsea un feed, filtra por antigüedad y deduplica por título normalizado."""
    parsed: Any = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"feed inválido: {parsed.get('bozo_exception')}")

    max_age_hours = feed.get(CONF_MAX_AGE_HOURS, DEFAULT_MAX_AGE_HOURS)
    max_items = feed.get(CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS)
    tags = feed.get(CONF_TAGS, [])
    feed_title = parsed.feed.get("title") if parsed.feed else None
    now = datetime.now(timezone.utc)

    seen: set[str] = set()
    items: list[dict] = []
    for entry in parsed.entries:
        norm = _normalize_title(entry.get("title"))
        if not norm or norm in seen:
            continue
        published = _entry_published(entry)
        if published is not None:
            age_hours = (now - published).total_seconds() / 3600.0
            if age_hours < 0 or age_hours > max_age_hours:
                continue
        seen.add(norm)
        brief = _entry_brief(entry, feed_title)
        brief["tags"] = tags
        items.append(brief)
        if len(items) >= max_items:
            break
    return items


async def _fetch_one(client: httpx.AsyncClient, feed: dict) -> list[dict]:
    """Descarga y parsea un único feed."""
    response = await client.get(feed[CONF_URL])
    response.raise_for_status()
    return await asyncio.to_thread(parse_feed_content, response.content, feed)


async def async_fetch_feeds(
    hass: Any, feeds: list[dict], client: httpx.AsyncClient | None = None
) -> dict:
    """Recolecta las secciones news y events desde los feeds configurados.

    Un feed caído o inválido no aborta el resto: se registra un warning y
    su sección queda vacía.
    """
    sections: dict[str, list[dict]] = {KIND_NEWS: [], KIND_EVENTS: []}
    if not feeds:
        return sections

    own_client = client is None
    session = client or httpx.AsyncClient(
        timeout=httpx.Timeout(DEFAULT_TIMEOUT),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )
    try:
        results = await asyncio.gather(
            *[_fetch_one(session, feed) for feed in feeds],
            return_exceptions=True,
        )
    finally:
        if own_client:
            await session.aclose()

    for feed, result in zip(feeds, results):
        if isinstance(result, BaseException):
            _LOGGER.warning("Feed caído %s: %s", feed.get(CONF_URL), result)
            continue
        sections.setdefault(feed.get(CONF_KIND, KIND_NEWS), []).extend(result)
    return sections
