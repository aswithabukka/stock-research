"""Rule-based scorecard + a Markdown brief you can hand to Claude Code."""
from __future__ import annotations

from typing import List, Optional

from .models import (
    MarketData,
    ResearchReport,
    Scorecard,
    Signal,
)

# Map verdicts to a 0..1 contribution for the composite score.
_VERDICT_VALUE = {"positive": 1.0, "neutral": 0.5, "negative": 0.0}


def _fmt_pct(v: Optional[float], scale: float = 1.0) -> str:
    if v is None:
        return "n/a"
    return f"{v * scale:.1f}%"


def _fmt_money(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(v) >= div:
            return f"{v / div:.2f}{unit}"
    return f"{v:,.0f}"


def build_scorecard(market: MarketData) -> Scorecard:
    signals: List[Signal] = []

    # Analyst price-target upside.
    up = market.upside_pct
    if up is None:
        signals.append(Signal("Analyst upside", "unknown", "No price target coverage."))
    elif up >= 15:
        signals.append(Signal("Analyst upside", "positive", f"{up:.0f}% to mean target."))
    elif up >= 0:
        signals.append(Signal("Analyst upside", "neutral", f"{up:.0f}% to mean target."))
    else:
        signals.append(Signal("Analyst upside", "negative", f"{up:.0f}% (trading above target)."))

    # Recommendation mean (1=strong buy ... 5=sell).
    rm = market.recommendation_mean
    if rm is None:
        signals.append(Signal("Analyst rating", "unknown", "No consensus rating."))
    elif rm <= 2.0:
        signals.append(Signal("Analyst rating", "positive", f"Consensus buy ({rm:.1f}/5)."))
    elif rm <= 3.0:
        signals.append(Signal("Analyst rating", "neutral", f"Consensus hold ({rm:.1f}/5)."))
    else:
        signals.append(Signal("Analyst rating", "negative", f"Leaning sell ({rm:.1f}/5)."))

    # Revenue growth.
    rg = market.revenue_growth
    if rg is None:
        signals.append(Signal("Revenue growth", "unknown", "Not reported."))
    elif rg >= 0.15:
        signals.append(Signal("Revenue growth", "positive", f"{_fmt_pct(rg,100)} YoY."))
    elif rg >= 0.0:
        signals.append(Signal("Revenue growth", "neutral", f"{_fmt_pct(rg,100)} YoY."))
    else:
        signals.append(Signal("Revenue growth", "negative", f"{_fmt_pct(rg,100)} YoY (shrinking)."))

    # Profitability.
    pm = market.profit_margin
    if pm is None:
        signals.append(Signal("Profitability", "unknown", "Margin not reported."))
    elif pm >= 0.10:
        signals.append(Signal("Profitability", "positive", f"{_fmt_pct(pm,100)} net margin."))
    elif pm > 0:
        signals.append(Signal("Profitability", "neutral", f"{_fmt_pct(pm,100)} net margin."))
    else:
        signals.append(Signal("Profitability", "negative", "Unprofitable (negative margin)."))

    # Valuation via forward P/E.
    fpe = market.forward_pe
    if fpe is None:
        signals.append(Signal("Valuation (fwd P/E)", "unknown", "No forward P/E."))
    elif fpe <= 0:
        signals.append(Signal("Valuation (fwd P/E)", "negative", "Negative earnings."))
    elif fpe <= 25:
        signals.append(Signal("Valuation (fwd P/E)", "positive", f"{fpe:.0f}x forward earnings."))
    elif fpe <= 40:
        signals.append(Signal("Valuation (fwd P/E)", "neutral", f"{fpe:.0f}x forward earnings."))
    else:
        signals.append(Signal("Valuation (fwd P/E)", "negative", f"{fpe:.0f}x (rich)."))

    known = [s for s in signals if s.verdict != "unknown"]
    score = None
    if known:
        score = round(sum(_VERDICT_VALUE[s.verdict] for s in known) / len(known) * 100)

    if score is None:
        headline = "Not enough data for a signal."
    elif score >= 66:
        headline = "Signals lean constructive."
    elif score >= 40:
        headline = "Mixed signals — no clear edge."
    else:
        headline = "Signals lean cautious."

    return Scorecard(signals=signals, score=score, headline=headline)


def build_brief(report: ResearchReport) -> str:
    """A self-contained Markdown dossier for qualitative analysis in Claude Code."""
    p, m, e = report.profile, report.market, report.earnings
    lines: List[str] = []
    lines.append(f"# Research brief: {p.name} ({p.ticker})")
    lines.append("")
    lines.append("## Profile")
    lines.append(f"- Exchange: {p.exchange or 'n/a'}")
    lines.append(f"- Sector / Industry: {p.sector or 'n/a'} / {p.industry or 'n/a'}")
    lines.append(f"- Country: {p.country or 'n/a'}")
    lines.append(f"- Employees: {p.employees and int(p.employees) or 'n/a'}")
    lines.append(f"- Website: {p.website or 'n/a'}")
    if p.summary:
        lines.append(f"\n**Business summary:** {p.summary}")

    lines.append("\n## Market & valuation")
    lines.append(f"- Price: {m.price} {m.currency or ''}")
    lines.append(f"- Market cap: {_fmt_money(m.market_cap)}")
    lines.append(f"- Trailing P/E: {m.trailing_pe} | Forward P/E: {m.forward_pe}")
    lines.append(f"- Profit margin: {_fmt_pct(m.profit_margin,100)} | Revenue growth: {_fmt_pct(m.revenue_growth,100)}")
    lines.append(f"- 52wk range: {m.fifty_two_low} – {m.fifty_two_high}")

    lines.append("\n## Analyst coverage")
    lines.append(f"- Mean target: {m.target_mean} (high {m.target_high} / low {m.target_low})")
    up = m.upside_pct
    lines.append(f"- Implied upside to mean: {up:.1f}%" if up is not None else "- Implied upside: n/a")
    lines.append(f"- Consensus: {m.recommendation_key or 'n/a'} (mean {m.recommendation_mean}, n={m.num_analysts})")

    lines.append("\n## Earnings")
    lines.append(f"- Next earnings date: {e.next_date or 'n/a'}")
    if e.annual:
        lines.append("- Annual (most recent first):")
        for r in e.annual:
            lines.append(f"  - {r.period}: revenue {_fmt_money(r.revenue)}, net income {_fmt_money(r.net_income)}")
    if e.surprises:
        lines.append("- Recent EPS surprises:")
        for s in e.surprises:
            lines.append(
                f"  - {s.date}: est {s.eps_estimate}, reported {s.eps_reported}, surprise {s.surprise_pct}%"
            )

    if report.website and (report.website.products or report.website.about_text):
        lines.append("\n## From the company website")
        if report.website.description:
            lines.append(f"- Tagline: {report.website.description}")
        if report.website.products:
            lines.append(f"- Product/solution links: {', '.join(report.website.products)}")
        if report.website.about_text:
            lines.append(f"- Homepage blurb: {report.website.about_text}")

    if report.news:
        lines.append("\n## Recent news")
        for n in report.news[:8]:
            lines.append(f"- {n.title} ({n.source or '?'}, {n.date or '?'}) {n.url or ''}")

    if report.scorecard:
        lines.append("\n## Heuristic scorecard")
        lines.append(f"- Composite: {report.scorecard.score}/100 — {report.scorecard.headline}")
        for s in report.scorecard.signals:
            lines.append(f"  - {s.label}: **{s.verdict}** — {s.detail}")

    lines.append("\n---")
    lines.append(
        "## Questions for Claude Code\n"
        "Using the data above plus your own knowledge, please assess:\n"
        "1. What does this company actually do and how does it make money (revenue segments)?\n"
        "2. Which sector/themes is it tied to, and which macro trends (e.g. datacenter/AI capex, "
        "interest rates) would move the stock?\n"
        "3. Where does it stand on AI — is AI a tailwind, a threat, or irrelevant to its model?\n"
        "4. What are the main bull and bear arguments right now?\n"
        "5. Given valuation, growth, and analyst targets, is this a reasonable entry — and what "
        "are the key risks to watch before the next earnings date?\n"
    )
    return "\n".join(lines)
