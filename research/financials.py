"""Pull structured financials from Yahoo Finance via yfinance."""
from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd
import yfinance as yf

from .models import (
    CompanyProfile,
    EarningsData,
    EarningsRow,
    EarningsSurprise,
    MarketData,
)


def _num(v) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _first(info: dict, *keys):
    for k in keys:
        if k in info and info[k] not in (None, "", "None"):
            return info[k]
    return None


def fetch(ticker: str) -> Tuple[CompanyProfile, MarketData, EarningsData, Optional[pd.DataFrame], List[str]]:
    warnings: List[str] = []
    t = yf.Ticker(ticker)

    try:
        info = t.get_info() or {}
    except Exception as exc:  # noqa: BLE001
        info = {}
        warnings.append(f"Could not load company info for {ticker}: {exc}")

    profile = CompanyProfile(
        name=_first(info, "longName", "shortName", "displayName") or ticker,
        ticker=ticker.upper(),
        exchange=_first(info, "fullExchangeName", "exchange"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        summary=info.get("longBusinessSummary"),
        website=info.get("website"),
        country=info.get("country"),
        employees=_num(info.get("fullTimeEmployees")),
    )

    market = MarketData(
        price=_num(_first(info, "currentPrice", "regularMarketPrice", "previousClose")),
        currency=_first(info, "currency", "financialCurrency"),
        market_cap=_num(info.get("marketCap")),
        trailing_pe=_num(info.get("trailingPE")),
        forward_pe=_num(info.get("forwardPE")),
        profit_margin=_num(info.get("profitMargins")),
        revenue_growth=_num(info.get("revenueGrowth")),
        earnings_growth=_num(info.get("earningsGrowth")),
        fifty_two_high=_num(info.get("fiftyTwoWeekHigh")),
        fifty_two_low=_num(info.get("fiftyTwoWeekLow")),
        target_mean=_num(info.get("targetMeanPrice")),
        target_high=_num(info.get("targetHighPrice")),
        target_low=_num(info.get("targetLowPrice")),
        target_median=_num(info.get("targetMedianPrice")),
        num_analysts=_num(info.get("numberOfAnalystOpinions")),
        recommendation_key=info.get("recommendationKey"),
        recommendation_mean=_num(info.get("recommendationMean")),
    )

    earnings = _fetch_earnings(t, warnings)

    history = None
    try:
        history = t.history(period="1y", interval="1d")
        if history is not None and history.empty:
            history = None
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not load price history: {exc}")

    return profile, market, earnings, history, warnings


def _income_rows(df: Optional[pd.DataFrame], limit: int) -> List[EarningsRow]:
    rows: List[EarningsRow] = []
    if df is None or df.empty:
        return rows

    def grab(label_options):
        for label in label_options:
            if label in df.index:
                return df.loc[label]
        return None

    revenue = grab(["Total Revenue", "TotalRevenue", "OperatingRevenue"])
    net_income = grab(["Net Income", "NetIncome", "Net Income Common Stockholders"])
    cols = list(df.columns)[:limit]
    for col in cols:
        period = getattr(col, "date", lambda: col)()
        period = str(period)
        rows.append(
            EarningsRow(
                period=period,
                revenue=_num(revenue[col]) if revenue is not None else None,
                net_income=_num(net_income[col]) if net_income is not None else None,
            )
        )
    return rows


def _fetch_earnings(t: "yf.Ticker", warnings: List[str]) -> EarningsData:
    data = EarningsData()

    try:
        data.annual = _income_rows(t.income_stmt, limit=4)
    except Exception:
        pass
    try:
        data.quarterly = _income_rows(t.quarterly_income_stmt, limit=4)
    except Exception:
        pass

    try:
        ed = t.get_earnings_dates(limit=12)
        if ed is not None and not ed.empty:
            future = ed[ed.index > pd.Timestamp.now(tz=ed.index.tz)]
            if not future.empty:
                data.next_date = str(future.index.min().date())
            past = ed[ed.index <= pd.Timestamp.now(tz=ed.index.tz)]
            for idx, row in past.head(4).iterrows():
                data.surprises.append(
                    EarningsSurprise(
                        date=str(idx.date()),
                        eps_estimate=_num(row.get("EPS Estimate")),
                        eps_reported=_num(row.get("Reported EPS")),
                        surprise_pct=_num(row.get("Surprise(%)")),
                    )
                )
    except Exception:
        pass

    return data
