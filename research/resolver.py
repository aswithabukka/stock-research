"""Resolve a company website (or raw name/ticker) into a stock ticker symbol."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Common multi-word company suffixes / noise to strip from a domain guess.
_NOISE = {"inc", "corp", "corporation", "company", "co", "ltd", "group", "holdings", "the"}


def normalize_input(raw: str) -> str:
    return (raw or "").strip()


def looks_like_ticker(raw: str) -> bool:
    """A short all-caps alnum token with no dots/spaces is probably a ticker."""
    raw = raw.strip()
    return bool(re.fullmatch(r"[A-Za-z]{1,5}([.\-][A-Za-z]{1,3})?", raw)) and "." not in raw.split("/")[0][:0]


def domain_to_name(raw: str) -> str:
    """nvidia.com -> nvidia ; https://www.apple.com/ -> apple"""
    raw = raw.strip()
    if "://" not in raw and "." in raw and " " not in raw:
        raw = "https://" + raw
    host = urlparse(raw).netloc or raw
    host = host.lower().split(":")[0]
    host = re.sub(r"^www\.", "", host)
    # take the second-level domain label
    label = host.split(".")[0] if "." in host else host
    label = re.sub(r"[^a-z0-9 ]", " ", label)
    parts = [p for p in label.split() if p and p not in _NOISE]
    return " ".join(parts) or label


def is_url(raw: str) -> bool:
    raw = raw.strip()
    return ("://" in raw) or bool(re.match(r"^[\w-]+(\.[\w-]+)+", raw))


def yahoo_search(query: str, limit: int = 8) -> List[dict]:
    """Use yfinance's Search (handles Yahoo's cookie/crumb so we avoid 429s)."""
    try:
        import yfinance as yf

        return yf.Search(query, max_results=limit).quotes or []
    except Exception:
        return []


def _pick_equity(quotes: List[dict]) -> Optional[dict]:
    equities = [q for q in quotes if q.get("quoteType") == "EQUITY" and q.get("symbol")]
    if not equities:
        equities = [q for q in quotes if q.get("symbol")]
    if not equities:
        return None
    # Prefer US primary listings (no exchange suffix) when present.
    equities.sort(key=lambda q: ("." in (q.get("symbol") or ""), -float(q.get("score") or 0)))
    return equities[0]


def resolve(raw: str) -> Tuple[Optional[str], List[dict], List[str]]:
    """Return (best_ticker, candidate_quotes, warnings)."""
    warnings: List[str] = []
    raw = normalize_input(raw)
    if not raw:
        return None, [], ["Empty input."]

    # Does the input look like a bare ticker symbol (short, all-caps-able token)?
    ticker_like = (
        not is_url(raw)
        and looks_like_ticker(raw)
        and raw.upper() == raw.replace(".", "").replace("-", "").upper()
    )

    # Always search Yahoo for the best REAL symbol — names like "Apple", "Tesla",
    # "Meta", "Visa" look like tickers but must resolve to AAPL/TSLA/META/V.
    term = domain_to_name(raw) if is_url(raw) else raw
    quotes = yahoo_search(term)
    if not quotes and term != raw:
        quotes = yahoo_search(raw)  # retry with the original if a domain label was odd

    # If it looks like a ticker AND Yahoo confirms that exact symbol exists, trust it.
    if ticker_like:
        match = next((q for q in quotes if (q.get("symbol") or "").upper() == raw.upper()), None)
        if match:
            return match["symbol"], quotes, warnings

    # Otherwise take the best-matching real equity from the search (AAPL for "Apple").
    best = _pick_equity(quotes)
    if not best:
        # Last resort: only if it genuinely looked like a ticker, try it as-is.
        if ticker_like:
            return raw.upper(), quotes, warnings
        warnings.append(
            f"Could not auto-resolve a ticker from '{raw}'. "
            "Enter the ticker symbol manually (e.g. AAPL)."
        )
        return None, quotes, warnings

    if "." in (best.get("symbol") or ""):
        warnings.append(
            f"Resolved to a non-US listing ({best['symbol']}). "
            "If you meant the US listing, enter the ticker manually."
        )
    return best["symbol"], quotes, warnings
