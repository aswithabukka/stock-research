"""Plotly figure builders. All charts are deterministic — drawn from the
structured data, so the numbers are always exactly what the APIs returned."""
from __future__ import annotations

from typing import List, Optional

import plotly.graph_objects as go

from .models import EarningsData, MarketData, Scorecard

GREEN = "#16a34a"
AMBER = "#d97706"
RED = "#dc2626"
BLUE = "#0ea5e9"
GREY = "#94a3b8"

VERDICT_COLOR = {"positive": GREEN, "neutral": AMBER, "negative": RED, "unknown": GREY}


def _empty(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=GREY))
    fig.update_layout(height=160, xaxis=dict(visible=False), yaxis=dict(visible=False),
                      margin=dict(l=10, r=10, t=10, b=10))
    return fig


def _layout(fig: go.Figure, height: int = 280, title: Optional[str] = None) -> go.Figure:
    fig.update_layout(
        height=height,
        title=title,
        margin=dict(l=10, r=10, t=40 if title else 16, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
    )
    return fig


def score_gauge(score: Optional[float], title: str = "Composite score") -> go.Figure:
    if score is None:
        return _empty("No score")
    color = GREEN if score >= 66 else AMBER if score >= 40 else RED
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "/100"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 40], "color": "#fee2e2"},
                {"range": [40, 66], "color": "#fef3c7"},
                {"range": [66, 100], "color": "#dcfce7"},
            ],
        },
    ))
    return _layout(fig, height=240, title=title)


def confidence_gauge(value: Optional[float], title: str = "Agent confidence") -> go.Figure:
    if value is None:
        return _empty("No confidence score")
    return score_gauge(value, title=title)


def recommendation_gauge(rec_mean: Optional[float], title: Optional[str] = "Analyst consensus") -> go.Figure:
    """1 = strong buy (green) ... 5 = sell (red)."""
    if rec_mean is None:
        return _empty("No analyst rating")
    color = GREEN if rec_mean <= 2 else AMBER if rec_mean <= 3 else RED
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=rec_mean,
        number={"valueformat": ".1f"},
        gauge={
            "axis": {"range": [1, 5], "tickvals": [1, 2, 3, 4, 5],
                     "ticktext": ["Strong buy", "Buy", "Hold", "Sell", "Strong sell"]},
            "bar": {"color": color},
            "steps": [
                {"range": [1, 2], "color": "#dcfce7"},
                {"range": [2, 3], "color": "#ecfccb"},
                {"range": [3, 4], "color": "#fef3c7"},
                {"range": [4, 5], "color": "#fee2e2"},
            ],
        },
    ))
    return _layout(fig, height=240, title=title)


def target_chart(m: MarketData, title: Optional[str] = "Analyst price targets") -> go.Figure:
    """Low / mean / median / high price targets vs the current price."""
    pts = [("Low", m.target_low), ("Mean", m.target_mean),
           ("Median", m.target_median), ("High", m.target_high)]
    pts = [(lbl, v) for lbl, v in pts if v is not None]
    if not pts or m.price is None:
        return _empty("No analyst price targets")

    labels = [p[0] for p in pts]
    vals = [p[1] for p in pts]
    colors = [GREEN if v >= m.price else RED for v in vals]

    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color=colors,
        text=[f"{v:,.0f}" for v in vals], textposition="outside",
    ))
    fig.add_vline(x=m.price, line_dash="dash", line_color=BLUE,
                  annotation_text=f"Price {m.price:,.0f}", annotation_position="top")
    fig.update_layout(xaxis_title=f"Price ({m.currency or ''})")
    return _layout(fig, height=280, title=title)


def price_history_chart(history, hi: Optional[float], lo: Optional[float],
                        title: Optional[str] = "Price — last 12 months") -> go.Figure:
    if history is None or getattr(history, "empty", True):
        return _empty("No price history")
    close = history["Close"]
    fig = go.Figure(go.Scatter(x=close.index, y=close.values, mode="lines",
                               line=dict(color=BLUE, width=2), name="Close"))
    if hi:
        fig.add_hline(y=hi, line_dash="dot", line_color=GREEN,
                      annotation_text=f"52w high {hi:,.0f}", annotation_position="right")
    if lo:
        fig.add_hline(y=lo, line_dash="dot", line_color=RED,
                      annotation_text=f"52w low {lo:,.0f}", annotation_position="right")
    fig.update_layout(yaxis_title="Close", xaxis_title=None, showlegend=False)
    return _layout(fig, height=300, title=title)


def _b(v: Optional[float]) -> Optional[float]:
    return None if v is None else v / 1e9


def revenue_income_chart(e: EarningsData, title: Optional[str] = "Revenue & net income (annual)") -> go.Figure:
    rows = list(reversed(e.annual)) if e.annual else []
    if not rows:
        return _empty("No annual financials")
    periods = [r.period[:4] for r in rows]
    fig = go.Figure()
    fig.add_bar(name="Revenue ($B)", x=periods, y=[_b(r.revenue) for r in rows], marker_color=BLUE)
    fig.add_bar(name="Net income ($B)", x=periods, y=[_b(r.net_income) for r in rows], marker_color=GREEN)
    fig.update_layout(barmode="group", yaxis_title="$ Billions")
    return _layout(fig, height=300, title=title)


def eps_surprise_chart(e: EarningsData, title: Optional[str] = "Earnings: estimate vs reported") -> go.Figure:
    rows = [s for s in reversed(e.surprises) if s.eps_estimate is not None or s.eps_reported is not None]
    if not rows:
        return _empty("No EPS history")
    dates = [s.date for s in rows]
    fig = go.Figure()
    fig.add_bar(name="Estimated EPS", x=dates, y=[s.eps_estimate for s in rows], marker_color=GREY)
    fig.add_bar(name="Reported EPS", x=dates, y=[s.eps_reported for s in rows], marker_color=BLUE)
    fig.update_layout(barmode="group", yaxis_title="EPS")
    return _layout(fig, height=300, title=title)


def segments_donut(segments: List[dict]) -> Optional[go.Figure]:
    """segments: [{'name': str, 'pct': number}] from the agent."""
    clean = [(s.get("name"), s.get("pct")) for s in segments
             if s.get("name") and isinstance(s.get("pct"), (int, float))]
    if not clean:
        return None
    fig = go.Figure(go.Pie(
        labels=[c[0] for c in clean],
        values=[c[1] for c in clean],
        hole=0.55,
        sort=True,
        direction="clockwise",
        textinfo="percent",
        textposition="inside",
        insidetextorientation="horizontal",
        marker=dict(line=dict(color="white", width=1)),
    ))
    # No plotly title (it collided with slice labels) — the app prints the
    # heading above the chart. Legend sits below with room to breathe.
    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=10, b=60),
        legend=dict(orientation="h", yanchor="top", y=-0.05,
                    xanchor="center", x=0.5),
        template="plotly_white",
        showlegend=True,
    )
    return fig
