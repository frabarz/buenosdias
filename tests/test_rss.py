"""Tests of context collection from RSS feeds."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx

from custom_components.buenosdias import rss
from custom_components.buenosdias.const import (
    CONF_EXCLUDE,
    CONF_URL,
    KIND_EVENTS,
    KIND_NEWS,
)


def _rss_xml(items, title="My Feed"):
    entries = "\n".join(
        f"""
        <item>
          <title>{item['title']}</title>
          <link>https://example.org/{item['slug']}</link>
          <description>{item.get('summary', '')}</description>
          <pubDate>{item['pubdate']}</pubDate>
        </item>"""
        for item in items
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<rss version="2.0"><channel>'
        f"<title>{title}</title><link>https://example.org</link>"
        f"{entries}</channel></rss>"
    ).encode()


def _pubdate(dt):
    return format_datetime(dt, usegmt=True)


def _feed(url, **kwargs):
    feed = {CONF_URL: url}
    feed.update(kwargs)
    return feed


def _mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _run(coro):
    return asyncio.run(coro)


def _close(client):
    _run(client.aclose())


def test_async_fetch_feeds_creates_news_and_events_sections():
    now = datetime.now(timezone.utc)
    news_xml = _rss_xml(
        [
            {
                "title": "A bakery opens downtown",
                "slug": "bakery",
                "pubdate": _pubdate(now - timedelta(hours=1)),
                "summary": "Press release from the city council.",
            }
        ],
        title="News",
    )
    events_xml = _rss_xml(
        [
            {
                "title": "Concert at the main square",
                "slug": "concert",
                "pubdate": _pubdate(now - timedelta(hours=2)),
            }
        ],
        title="Agenda",
    )

    def handler(request):
        if "news" in str(request.url):
            return httpx.Response(200, content=news_xml)
        return httpx.Response(200, content=events_xml)

    client = _mock_client(handler)
    feeds = [
        _feed("https://example.org/news.xml", kind=KIND_NEWS, tags=["city"]),
        _feed("https://example.org/agenda.xml", kind=KIND_EVENTS),
    ]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    assert len(sections[KIND_NEWS]) == 1
    item = sections[KIND_NEWS][0]
    assert item["title"] == "A bakery opens downtown"
    assert item["summary"] == "Press release from the city council."
    assert item["link"] == "https://example.org/bakery"
    assert item["published"]
    assert item["source"] == "News"
    assert item["tags"] == ["city"]
    assert len(sections[KIND_EVENTS]) == 1
    assert sections[KIND_EVENTS][0]["title"] == "Concert at the main square"
    json.dumps(sections)  # must be serializable


def test_async_fetch_feeds_filters_by_age():
    now = datetime.now(timezone.utc)
    xml = _rss_xml(
        [
            {
                "title": "Recent story",
                "slug": "recent",
                "pubdate": _pubdate(now - timedelta(hours=2)),
            },
            {
                "title": "Very old story",
                "slug": "old",
                "pubdate": _pubdate(now - timedelta(days=10)),
            },
        ]
    )

    def handler(request):
        return httpx.Response(200, content=xml)

    client = _mock_client(handler)
    feeds = [_feed("https://example.org/feed.xml", max_age_hours=6)]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    titles = [item["title"] for item in sections[KIND_NEWS]]
    assert titles == ["Recent story"]


def test_parse_feed_content_dedup_and_limit():
    now = datetime.now(timezone.utc)
    xml = _rss_xml(
        [
            {
                "title": "Repeated Title.",
                "slug": "a",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
            {
                "title": "repeated title",
                "slug": "b",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
            {
                "title": "Third story",
                "slug": "c",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
        ]
    )
    feed = _feed("https://example.org/feed.xml", max_items=2)
    items = rss.parse_feed_content(xml, feed)
    assert [item["title"] for item in items] == ["Repeated Title.", "Third story"]


def test_parse_feed_content_filters_excluded_keywords():
    now = datetime.now(timezone.utc)
    xml = _rss_xml(
        [
            {
                "title": "Fútbol: el clásico terminó en empate",
                "slug": "a",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
            {
                "title": "Farándula: boda de una figura de la TV",
                "slug": "b",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
            {
                "title": "City council approves budget",
                "slug": "c",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
        ]
    )
    feed = _feed(
        "https://example.org/feed.xml",
        **{CONF_EXCLUDE: ["futbol", "farándula"]},
    )
    items = rss.parse_feed_content(xml, feed)
    assert [item["title"] for item in items] == ["City council approves budget"]


def test_parse_feed_content_matches_exclude_in_summary():
    now = datetime.now(timezone.utc)
    xml = _rss_xml(
        [
            {
                "title": "Youth league wraps up season",
                "slug": "a",
                "pubdate": _pubdate(now - timedelta(hours=1)),
                "summary": "Resultados del fútbol regional de la liga juvenil.",
            },
            {
                "title": "New park opens downtown",
                "slug": "b",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
        ]
    )
    feed = _feed(
        "https://example.org/feed.xml",
        **{CONF_EXCLUDE: ["futbol"]},
    )
    items = rss.parse_feed_content(xml, feed)
    assert [item["title"] for item in items] == ["New park opens downtown"]


def test_parse_feed_content_exclude_no_match_keeps_all():
    now = datetime.now(timezone.utc)
    xml = _rss_xml(
        [
            {
                "title": "Regional weather outlook",
                "slug": "a",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
        ]
    )
    feed = _feed(
        "https://example.org/feed.xml",
        **{CONF_EXCLUDE: ["cosmos"]},
    )
    items = rss.parse_feed_content(xml, feed)
    assert [item["title"] for item in items] == ["Regional weather outlook"]


def test_async_fetch_feeds_tolerates_down_feed(caplog):
    def handler(request):
        return httpx.Response(500)

    client = _mock_client(handler)
    feeds = [_feed("https://example.org/down.xml")]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    assert sections[KIND_NEWS] == []
    assert sections[KIND_EVENTS] == []
    assert "Feed failed" in caplog.text


def test_async_fetch_feeds_tolerates_invalid_xml():
    def handler(request):
        return httpx.Response(200, content=b"this is not xml")

    client = _mock_client(handler)
    feeds = [_feed("https://example.org/bad.xml")]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    assert sections[KIND_NEWS] == []


def test_async_fetch_feeds_without_feeds():
    sections = _run(rss.async_fetch_feeds(None, []))
    assert sections == {KIND_NEWS: [], KIND_EVENTS: []}
