"""Typed containers for the research pipeline output."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class CompanyProfile:
    name: str
    ticker: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    summary: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    employees: Optional[int] = None


@dataclass
class MarketData:
    price: Optional[float] = None
    currency: Optional[str] = None
    market_cap: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    profit_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    fifty_two_high: Optional[float] = None
    fifty_two_low: Optional[float] = None
    # Analyst coverage
    target_mean: Optional[float] = None
    target_high: Optional[float] = None
    target_low: Optional[float] = None
    target_median: Optional[float] = None
    num_analysts: Optional[int] = None
    recommendation_key: Optional[str] = None
    recommendation_mean: Optional[float] = None

    @property
    def upside_pct(self) -> Optional[float]:
        if self.price and self.target_mean:
            return (self.target_mean - self.price) / self.price * 100.0
        return None


@dataclass
class EarningsRow:
    period: str
    revenue: Optional[float] = None
    net_income: Optional[float] = None


@dataclass
class EarningsSurprise:
    date: str
    eps_estimate: Optional[float] = None
    eps_reported: Optional[float] = None
    surprise_pct: Optional[float] = None


@dataclass
class EarningsData:
    next_date: Optional[str] = None
    annual: List[EarningsRow] = field(default_factory=list)
    quarterly: List[EarningsRow] = field(default_factory=list)
    surprises: List[EarningsSurprise] = field(default_factory=list)


@dataclass
class NewsItem:
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None


@dataclass
class WebsiteInfo:
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    products: List[str] = field(default_factory=list)
    about_text: Optional[str] = None


@dataclass
class Signal:
    label: str
    verdict: str  # "positive" | "neutral" | "negative" | "unknown"
    detail: str


@dataclass
class Scorecard:
    signals: List[Signal] = field(default_factory=list)
    score: Optional[float] = None  # 0..100
    headline: str = ""


@dataclass
class ResearchReport:
    query: str
    profile: CompanyProfile
    market: MarketData
    earnings: EarningsData
    website: Optional[WebsiteInfo] = None
    news: List[NewsItem] = field(default_factory=list)
    scorecard: Optional[Scorecard] = None
    warnings: List[str] = field(default_factory=list)
    price_history: Optional[Any] = None  # pandas DataFrame of 1y daily OHLC
