"""Build a shareable PDF of the research + agent analysis (pure-Python, fpdf2).

Designed for a team to read and make a buy/no-buy call: snapshot, verdict,
revenue mix, sector trends, bull/bear, analyst targets, scorecard, and the full
written analysis.
"""
from __future__ import annotations

import html as _html
from datetime import date
from typing import List, Optional

import markdown as _md
from fpdf import FPDF

from .models import EarningsData, MarketData, ResearchReport, Scorecard

VERDICT_COLOR = {"buy": "#16a34a", "hold": "#d97706", "avoid": "#dc2626"}
IMPACT_COLOR = {"positive": "#16a34a", "neutral": "#d97706", "negative": "#dc2626"}
IMPACT_WORD = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
EARN_COLOR = {"beat": "#16a34a", "met": "#d97706", "missed": "#dc2626"}
EARN_WORD = {"beat": "Over-delivered", "met": "In line", "missed": "Under-delivered"}

# Replace common non-latin-1 glyphs so the core PDF font never errors.
_REPL = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "•": "-",
    " ": " ", "→": "->", "↑": "(up)", "↓": "(down)",
    "▲": "^", "▼": "v", "✅": "", "⚠": "!", "–": "-",
}


def _sanitize(s: str) -> str:
    for k, v in _REPL.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "ignore").decode("latin-1")


def esc(s) -> str:
    if s is None:
        return ""
    return _html.escape(str(s))


def _money(v) -> str:
    if v is None:
        return "-"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(v) >= div:
            return f"{v / div:.2f}{unit}"
    return f"{v:,.0f}"


def _pct(v, scale=1.0) -> str:
    return "-" if v is None else f"{v * scale:.1f}%"


def _num(v, fmt="{:.2f}") -> str:
    return "-" if v is None else fmt.format(v)


def _row(cells: List[str], header: bool = False, widths: Optional[List[str]] = None) -> str:
    tag = "th" if header else "td"
    out = []
    for i, c in enumerate(cells):
        attrs = ' bgcolor="#e2e8f0"' if header else ""
        if widths and i < len(widths):
            attrs += f' width="{widths[i]}"'
        out.append(f"<{tag}{attrs}>{c}</{tag}>")
    return "<tr>" + "".join(out) + "</tr>"


def _table(rows: List[str]) -> str:
    return '<table border="0" width="100%">' + "".join(rows) + "</table>"


def _ul(items: List[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in items if x) + "</ul>"


def _snapshot(m: MarketData) -> str:
    up = m.upside_pct
    rows = [
        _row(["Metric", "Value"], header=True, widths=["50%", "50%"]),
        _row(["Price", f"{_num(m.price)} {esc(m.currency or '')}"]),
        _row(["Market cap", _money(m.market_cap)]),
        _row(["Forward P/E", _num(m.forward_pe, "{:.1f}")]),
        _row(["Trailing P/E", _num(m.trailing_pe, "{:.1f}")]),
        _row(["Target upside", f"{up:.1f}%" if up is not None else "-"]),
        _row(["Consensus", esc((m.recommendation_key or "-").replace("_", " ").title())]),
        _row(["Revenue growth", _pct(m.revenue_growth, 100)]),
        _row(["Profit margin", _pct(m.profit_margin, 100)]),
    ]
    return _table(rows)


def _targets(m: MarketData) -> str:
    rows = [
        _row(["Low", "Mean", "Median", "High", "# Analysts"], header=True, widths=["20%"] * 5),
        _row([_num(m.target_low), _num(m.target_mean), _num(m.target_median),
              _num(m.target_high), _num(m.num_analysts, "{:.0f}")]),
    ]
    return _table(rows)


def _segments(segs: List[dict]) -> str:
    rows = [_row(["Segment", "Share"], header=True, widths=["70%", "30%"])]
    for s in segs:
        pct = s.get("pct")
        rows.append(_row([esc(s.get("name")), f"{pct:.0f}%" if isinstance(pct, (int, float)) else "-"]))
    return _table(rows)


def _trends(trends: List[dict]) -> str:
    rows = [_row(["Trend", "Impact", "Note"], header=True, widths=["28%", "15%", "57%"])]
    for t in trends:
        imp = str(t.get("impact", "")).lower()
        color = IMPACT_COLOR.get(imp, "#0f172a")
        word = IMPACT_WORD.get(imp, esc(t.get("impact")))
        rows.append(_row([esc(t.get("name")), f"<font color='{color}'>{word}</font>", esc(t.get("note"))]))
    return _table(rows)


def _earnings_reviews(reviews: List[dict]) -> str:
    """Promised-vs-delivered review of the last few earnings reports."""
    out: List[str] = []
    for rv in reviews:
        verdict = str(rv.get("verdict", "")).lower()
        color = EARN_COLOR.get(verdict, "#0f172a")
        word = EARN_WORD.get(verdict, esc(rv.get("verdict")))
        out.append(
            f"<b>{esc(rv.get('period', 'Earnings report'))}</b> - "
            f"<font color='{color}'>{word}</font>"
        )
        if rv.get("note"):
            out.append(f"<br>{esc(rv.get('note'))}")
        segs = rv.get("segments") or []
        if segs:
            rows = [_row(["Segment", "How it did"], header=True, widths=["35%", "65%"])]
            for sg in segs:
                rows.append(_row([esc(sg.get("name")), esc(sg.get("result"))]))
            out.append(_table(rows))
        rows = [
            _row(["Promised (prior guidance)", "Delivered (actual)"], header=True, widths=["50%", "50%"]),
            _row([esc(rv.get("promised") or "-"), esc(rv.get("delivered") or "-")]),
        ]
        out.append(_table(rows))
        out.append("<br>")
    return "".join(out)


def _scorecard(sc: Scorecard) -> str:
    rows = [_row(["Signal", "Verdict", "Detail"], header=True, widths=["28%", "17%", "55%"])]
    for sig in sc.signals:
        color = IMPACT_COLOR.get(sig.verdict, "#0f172a")
        rows.append(_row([esc(sig.label),
                          f"<font color='{color}'>{esc(sig.verdict.title())}</font>",
                          esc(sig.detail)]))
    return _table(rows)


def build_pdf(report: ResearchReport, agent_result: Optional[dict] = None) -> bytes:
    p, m, e, sc = report.profile, report.market, report.earnings, report.scorecard
    s = (agent_result or {}).get("structured") or {}
    detail = (agent_result or {}).get("text") or ""

    parts: List[str] = []
    parts.append(f"<h1>{esc(p.name)} ({esc(p.ticker)})</h1>")
    sub = " - ".join(x for x in [p.exchange, p.sector, p.industry, p.country] if x)
    parts.append(f"<font color='#64748b'>{esc(sub)}</font><br>")
    parts.append(f"<font color='#64748b'>Generated {date.today().isoformat()} - research only, not financial advice.</font>")

    if s.get("verdict"):
        color = VERDICT_COLOR.get(str(s["verdict"]).lower(), "#0f172a")
        conf = s.get("confidence")
        suffix = f" ({conf}/100 confidence)" if isinstance(conf, (int, float)) else ""
        parts.append(f"<h2><font color='{color}'>Verdict: {esc(s['verdict'])}{suffix}</font></h2>")
        if s.get("one_liner"):
            parts.append(f"<b>{esc(s['one_liner'])}</b>")

    parts.append("<h3>Snapshot</h3>")
    parts.append(_snapshot(m))

    wtd = s.get("what_they_do") or p.summary
    if wtd:
        parts.append(f"<h3>What they do</h3>{esc(wtd)}")

    if s.get("revenue_segments"):
        parts.append("<h3>Revenue mix (est.)</h3>")
        parts.append(_segments(s["revenue_segments"]))

    if s.get("trends"):
        parts.append("<h3>Sector &amp; macro trends</h3>")
        parts.append(_trends(s["trends"]))

    ap = s.get("ai_positioning") or {}
    if ap.get("stance"):
        parts.append(f"<h3>AI positioning</h3><b>{esc(ap['stance']).title()}</b> - {esc(ap.get('note',''))}")

    if s.get("bull"):
        parts.append("<h3>Bull case</h3>")
        parts.append(_ul(s["bull"]))
    if s.get("bear"):
        parts.append("<h3>Bear case</h3>")
        parts.append(_ul(s["bear"]))

    if s.get("earnings_reviews"):
        parts.append("<h3>Earnings: promised vs. delivered (last few reports)</h3>")
        parts.append(_earnings_reviews(s["earnings_reviews"]))

    if s.get("analyst_note"):
        parts.append(f"<h3>Latest analyst view</h3>{esc(s['analyst_note'])}")
    if s.get("key_risks"):
        parts.append("<h3>Key risks before next earnings</h3>")
        parts.append(_ul(s["key_risks"]))

    parts.append("<h3>Analyst price targets</h3>")
    parts.append(_targets(m))

    if sc and sc.signals:
        parts.append(f"<h3>Heuristic scorecard ({sc.score}/100)</h3>")
        parts.append(_scorecard(sc))

    if detail:
        parts.append("<h2>Full written analysis</h2>")
        parts.append(_md.markdown(detail, extensions=["tables", "sane_lists"]))

    html_doc = _sanitize("".join(parts))

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.write_html(html_doc)
    out = pdf.output()
    return bytes(out)
