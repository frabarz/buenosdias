"""Tests de la recolección de contexto desde feeds RSS."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx

from custom_components.buenosdias import rss
from custom_components.buenosdias.const import (
    CONF_TAGS,
    CONF_URL,
    KIND_EVENTS,
    KIND_NEWS,
)


def _rss_xml(items, title="Mi Feed"):
    entries = "\n".join(
        f"""
        <item>
          <title>{item['title']}</title>
          <link>https://ejemplo.org/{item['slug']}</link>
          <description>{item.get('summary', '')}</description>
          <pubDate>{item['pubdate']}</pubDate>
        </item>"""
        for item in items
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<rss version="2.0"><channel>'
        f"<title>{title}</title><link>https://ejemplo.org</link>"
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


def test_async_fetch_feeds_crea_secciones_news_y_events():
    now = datetime.now(timezone.utc)
    news_xml = _rss_xml(
        [
            {
                "title": "Abre una panadería en el centro",
                "slug": "panaderia",
                "pubdate": _pubdate(now - timedelta(hours=1)),
                "summary": "Nota de prensa del ayuntamiento.",
            }
        ],
        title="Noticias",
    )
    events_xml = _rss_xml(
        [
            {
                "title": "Concierto en la plaza mayor",
                "slug": "concierto",
                "pubdate": _pubdate(now - timedelta(hours=2)),
            }
        ],
        title="Agenda",
    )

    def handler(request):
        if "noticias" in str(request.url):
            return httpx.Response(200, content=news_xml)
        return httpx.Response(200, content=events_xml)

    client = _mock_client(handler)
    feeds = [
        _feed("https://ejemplo.org/noticias.xml", kind=KIND_NEWS, tags=["ciudad"]),
        _feed("https://ejemplo.org/agenda.xml", kind=KIND_EVENTS),
    ]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    assert len(sections[KIND_NEWS]) == 1
    item = sections[KIND_NEWS][0]
    assert item["title"] == "Abre una panadería en el centro"
    assert item["summary"] == "Nota de prensa del ayuntamiento."
    assert item["link"] == "https://ejemplo.org/panaderia"
    assert item["published"]
    assert item["source"] == "Noticias"
    assert item["tags"] == ["ciudad"]
    assert len(sections[KIND_EVENTS]) == 1
    assert sections[KIND_EVENTS][0]["title"] == "Concierto en la plaza mayor"
    json.dumps(sections)  # debe ser serializable


def test_async_fetch_feeds_filtra_por_antiguedad():
    now = datetime.now(timezone.utc)
    xml = _rss_xml(
        [
            {
                "title": "Noticia reciente",
                "slug": "reciente",
                "pubdate": _pubdate(now - timedelta(hours=2)),
            },
            {
                "title": "Noticia muy antigua",
                "slug": "antigua",
                "pubdate": _pubdate(now - timedelta(days=10)),
            },
        ]
    )

    def handler(request):
        return httpx.Response(200, content=xml)

    client = _mock_client(handler)
    feeds = [_feed("https://ejemplo.org/feed.xml", max_age_hours=6)]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    titles = [item["title"] for item in sections[KIND_NEWS]]
    assert titles == ["Noticia reciente"]


def test_parse_feed_content_dedup_y_limite():
    now = datetime.now(timezone.utc)
    xml = _rss_xml(
        [
            {
                "title": "Título Repetido.",
                "slug": "a",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
            {
                "title": "título repetido",
                "slug": "b",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
            {
                "title": "Tercera noticia",
                "slug": "c",
                "pubdate": _pubdate(now - timedelta(hours=1)),
            },
        ]
    )
    feed = _feed("https://ejemplo.org/feed.xml", max_items=2)
    items = rss.parse_feed_content(xml, feed)
    assert [item["title"] for item in items] == ["Título Repetido.", "Tercera noticia"]


def test_async_fetch_feeds_tolera_feed_caido(caplog):
    def handler(request):
        return httpx.Response(500)

    client = _mock_client(handler)
    feeds = [_feed("https://ejemplo.org/roto.xml")]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    assert sections[KIND_NEWS] == []
    assert sections[KIND_EVENTS] == []
    assert "Feed caído" in caplog.text


def test_async_fetch_feeds_tolera_xml_invalido():
    def handler(request):
        return httpx.Response(200, content=b"esto no es xml")

    client = _mock_client(handler)
    feeds = [_feed("https://ejemplo.org/mal.xml")]
    sections = _run(rss.async_fetch_feeds(None, feeds, client=client))
    _close(client)

    assert sections[KIND_NEWS] == []


def test_async_fetch_feeds_sin_feeds():
    sections = _run(rss.async_fetch_feeds(None, []))
    assert sections == {KIND_NEWS: [], KIND_EVENTS: []}
