"""Lightweight scrape of a company website to learn what it does and sells."""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import WebsiteInfo

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_PRODUCT_HINT = re.compile(r"(product|solution|platform|service|offering)", re.I)


def _ensure_scheme(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    return url


def scrape(url: str) -> Optional[WebsiteInfo]:
    if not url:
        return None
    url = _ensure_scheme(url)
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=12)
        resp.raise_for_status()
    except Exception:
        return WebsiteInfo(url=url, title=None, description="(could not fetch site)")

    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else None

    description = None
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            description = tag["content"].strip()
            break

    products = _extract_products(soup, url)
    about_text = _extract_about_text(soup)

    return WebsiteInfo(
        url=url,
        title=title,
        description=description,
        products=products,
        about_text=about_text,
    )


def _extract_products(soup: BeautifulSoup, base_url: str) -> List[str]:
    host = urlparse(base_url).netloc
    found: List[str] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = a["href"]
        if not text or len(text) > 60:
            continue
        target = urljoin(base_url, href)
        if urlparse(target).netloc and urlparse(target).netloc != host:
            continue
        if _PRODUCT_HINT.search(href) or _PRODUCT_HINT.search(text):
            key = text.lower()
            if key not in seen:
                seen.add(key)
                found.append(text)
        if len(found) >= 12:
            break
    return found


def _extract_about_text(soup: BeautifulSoup) -> Optional[str]:
    # Grab the first few meaningful paragraphs as a rough "what they do" blurb.
    chunks: List[str] = []
    for p in soup.find_all(["h1", "h2", "p"]):
        text = " ".join(p.get_text(" ", strip=True).split())
        if len(text) >= 40:
            chunks.append(text)
        if len(chunks) >= 6:
            break
    if not chunks:
        return None
    return " ".join(chunks)[:1200]
