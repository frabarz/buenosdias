"""Context collection from RSS feeds (news and events)."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

from .const import (
    CONF_EXCLUDE,
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
    """Normalize a title to deduplicate repeated entries."""
    return re.sub(r"[\s\W_]+", "", (title or "").lower())


def _normalize_keyword(keyword: str) -> str:
    """Lowercase and strip accents so 'futbol' matches 'fútbol'."""
    decomposed = unicodedata.normalize("NFKD", (keyword or "").casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _matches_excludes(text: str, excludes: list[str]) -> bool:
    """Return True when the normalized text contains any exclude keyword."""
    if not excludes or not text:
        return False
    haystack = _normalize_keyword(text)
    return any(_normalize_keyword(kw) in haystack for kw in excludes)


def _entry_published(entry: Any) -> datetime | None:
    """Return the entry publication date (UTC), or None."""
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if not struct:
            continue
        try:
            return datetime(
                struct[0],
                struct[1],
                struct[2],
                struct[3],
                struct[4],
                struct[5],
                tzinfo=UTC,
            )
        except (TypeError, ValueError):
            continue
    return None


def _entry_brief(entry: Any, feed_title: str | None) -> dict:
    """Extract a serializable brief from an RSS entry."""
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
    """Parse a feed, filter by age and deduplicate by normalized title."""
    parsed: Any = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        msg = f"invalid feed: {parsed.get('bozo_exception')}"
        raise ValueError(msg)

    max_age_hours = feed.get(CONF_MAX_AGE_HOURS, DEFAULT_MAX_AGE_HOURS)
    max_items = feed.get(CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS)
    tags = feed.get(CONF_TAGS, [])
    excludes = feed.get(CONF_EXCLUDE, [])
    feed_title = parsed.feed.get("title") if parsed.feed else None
    now = datetime.now(UTC)

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
        summary = entry.get("summary") or entry.get("description") or ""
        if _matches_excludes(entry.get("title", ""), excludes) or _matches_excludes(
            summary, excludes
        ):
            continue
        seen.add(norm)
        brief = _entry_brief(entry, feed_title)
        brief["tags"] = tags
        items.append(brief)
        if len(items) >= max_items:
            break
    return items


async def _fetch_one(client: httpx.AsyncClient, feed: dict) -> list[dict]:
    """Download and parse a single feed."""
    response = await client.get(feed[CONF_URL])
    response.raise_for_status()
    return await asyncio.to_thread(parse_feed_content, response.content, feed)


async def async_fetch_feeds(
    hass: Any,
    feeds: list[dict],
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Collect the news and events sections from the configured feeds.

    A down or invalid feed does not abort the rest: a warning is logged and
    its section stays empty.
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
            _LOGGER.warning("Feed failed %s: %s", feed.get(CONF_URL), result)
            continue
        sections.setdefault(feed.get(CONF_KIND, KIND_NEWS), []).extend(result)
    return sections
