"""Stock research pipeline: website/name -> ticker -> full research report."""
from __future__ import annotations

from typing import Optional

from . import analysis, financials, news, resolver, website
from .models import ResearchReport


def run_research(raw_input: str, manual_ticker: Optional[str] = None, with_news: bool = True) -> ResearchReport:
    warnings = []

    if manual_ticker:
        ticker = manual_ticker.strip().upper()
    else:
        ticker, _candidates, res_warnings = resolver.resolve(raw_input)
        warnings.extend(res_warnings)
        if not ticker:
            raise ValueError(res_warnings[0] if res_warnings else "Could not resolve a ticker.")

    profile, market, earnings, history, fin_warnings = financials.fetch(ticker)
    warnings.extend(fin_warnings)

    site = None
    site_url = profile.website or (raw_input if resolver.is_url(raw_input) else None)
    if site_url:
        site = website.scrape(site_url)

    news_items = []
    if with_news:
        news_items = news.fetch_news(profile.name, ticker)

    scorecard = analysis.build_scorecard(market)

    return ResearchReport(
        query=raw_input,
        profile=profile,
        market=market,
        earnings=earnings,
        website=site,
        news=news_items,
        scorecard=scorecard,
        warnings=warnings,
        price_history=history,
    )


__all__ = ["run_research", "ResearchReport", "analysis", "financials", "news", "resolver", "website"]
