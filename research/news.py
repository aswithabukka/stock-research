"""Free, key-less news/web search via DuckDuckGo, plus Yahoo's own news feed."""
from __future__ import annotations

from typing import List

import requests

from .models import NewsItem

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _ddgs():
    """The package was renamed duckduckgo_search -> ddgs; support both."""
    try:
        from ddgs import DDGS  # type: ignore

        return DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS  # type: ignore

            return DDGS
        except Exception:
            return None


def ddg_news(company: str, max_results: int = 8) -> List[NewsItem]:
    DDGS = _ddgs()
    if DDGS is None or not company:
        return []
    items: List[NewsItem] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(f"{company} stock", max_results=max_results):
                items.append(
                    NewsItem(
                        title=r.get("title") or "",
                        url=r.get("url"),
                        source=r.get("source"),
                        date=str(r.get("date") or ""),
                        snippet=(r.get("body") or "")[:300],
                    )
                )
    except Exception:
        pass
    return items


def yahoo_news(ticker: str, max_results: int = 8) -> List[NewsItem]:
    """Yahoo Finance attaches a news feed to each ticker; no key required."""
    try:
        import yfinance as yf

        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    items: List[NewsItem] = []
    for r in raw[:max_results]:
        content = r.get("content", r) if isinstance(r, dict) else {}
        title = content.get("title") or r.get("title") or ""
        url = None
        if isinstance(content.get("canonicalUrl"), dict):
            url = content["canonicalUrl"].get("url")
        url = url or r.get("link")
        provider = content.get("provider", {})
        source = provider.get("displayName") if isinstance(provider, dict) else r.get("publisher")
        if title:
            items.append(
                NewsItem(
                    title=title,
                    url=url,
                    source=source,
                    date=str(content.get("pubDate") or ""),
                    snippet=(content.get("summary") or "")[:300],
                )
            )
    return items


def fetch_news(company: str, ticker: str, max_results: int = 8) -> List[NewsItem]:
    items = yahoo_news(ticker, max_results)
    if len(items) < max_results:
        seen = {i.title.lower() for i in items}
        for n in ddg_news(company, max_results):
            if n.title.lower() not in seen:
                items.append(n)
                seen.add(n.title.lower())
    return items[:max_results]
