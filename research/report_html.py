"""Build a shareable, self-contained HTML report that mirrors the app.

Unlike the flat PDF, this embeds the SAME interactive Plotly charts you see in
the dashboard (gauges, price-target bars, price history, revenue/EPS bars,
revenue-mix donut) plus the verdict, promised-vs-delivered earnings review,
bull/bear, and the full written analysis — laid out in the same five sections.

One file, opens in any browser, no internet needed (Plotly is inlined).
"""
from __future__ import annotations

import html as _html
from datetime import date
from typing import List, Optional

import markdown as _md
import plotly.io as pio
from plotly.offline import get_plotlyjs

from . import viz
from .models import ResearchReport

VERDICT_COLOR = {"buy": "#16a34a", "hold": "#d97706", "avoid": "#dc2626"}
IMPACT = {"positive": ("#16a34a", "▲ Positive"), "neutral": ("#d97706", "→ Neutral"),
          "negative": ("#dc2626", "▼ Negative")}
EARN = {"beat": ("#16a34a", "Over-delivered"), "met": ("#d97706", "In line"),
        "missed": ("#dc2626", "Under-delivered")}
STANCE = {"tailwind": ("#16a34a", "Tailwind"), "threat": ("#dc2626", "Threat"),
          "neutral": ("#d97706", "Neutral")}

_PLOTLY_JS: Optional[str] = None


def _plotlyjs() -> str:
    global _PLOTLY_JS
    if _PLOTLY_JS is None:
        _PLOTLY_JS = get_plotlyjs()
    return _PLOTLY_JS


def esc(v) -> str:
    return "" if v is None else _html.escape(str(v))


def _money(v) -> str:
    if v is None:
        return "—"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(v) >= div:
            return f"{v / div:.2f}{unit}"
    return f"{v:,.0f}"


def _pct(v, scale=1.0) -> str:
    return "—" if v is None else f"{v * scale:.1f}%"


def _num(v, fmt="{:.2f}") -> str:
    return "—" if v is None else fmt.format(v)


def _fig(fig) -> str:
    """Render a Plotly figure as an embeddable div (lib included once globally)."""
    if fig is None:
        return ""
    return pio.to_html(fig, include_plotlyjs=False, full_html=False,
                       default_width="100%", config={"displayModeBar": False})


def _kpi(label: str, value: str) -> str:
    return f'<div class="kpi"><div class="kpi-label">{esc(label)}</div><div class="kpi-value">{value}</div></div>'


def build_html(report: ResearchReport, agent_result: Optional[dict] = None) -> str:
    p, m, e, sc = report.profile, report.market, report.earnings, report.scorecard
    s = (agent_result or {}).get("structured") or {}
    detail = (agent_result or {}).get("text") or ""

    H: List[str] = []

    # ---- Header + KPIs ----
    meta = " · ".join(x for x in [p.exchange, p.sector, p.industry, p.country] if x)
    H.append(f'<header><h1>{esc(p.name)} <span class="ticker">{esc(p.ticker)}</span></h1>')
    if meta:
        H.append(f'<div class="meta">{esc(meta)}</div>')
    H.append(f'<div class="meta">Generated {date.today().isoformat()} · research only, not financial advice.</div>')
    up = m.upside_pct
    H.append('<div class="kpis">')
    H.append(_kpi("Price", f"{_num(m.price)} {esc(m.currency or '')}"))
    H.append(_kpi("Market cap", _money(m.market_cap)))
    H.append(_kpi("Fwd P/E", _num(m.forward_pe, "{:.1f}")))
    H.append(_kpi("Target upside", f"{up:.1f}%" if up is not None else "—"))
    H.append(_kpi("Consensus", esc((m.recommendation_key or "—").replace("_", " ").title())))
    H.append('</div>')

    # ---- Verdict banner ----
    verdict = (s.get("verdict") or "").strip()
    if verdict:
        color = VERDICT_COLOR.get(verdict.lower(), "#334155")
        conf = s.get("confidence")
        cf = f' · {conf}/100 confidence' if isinstance(conf, (int, float)) else ""
        H.append(f'<div class="verdict" style="border-color:{color}">'
                 f'<span class="vbadge" style="background:{color}">Verdict: {esc(verdict)}{cf}</span>'
                 f'<p>{esc(s.get("one_liner") or "")}</p></div>')
    H.append('</header>')

    # ---- Section: Overview ----
    H.append('<section><h2>📊 Overview</h2>')
    if sc:
        H.append('<div class="grid2">')
        H.append(f'<div class="chart">{_fig(viz.score_gauge(sc.score))}</div>')
        H.append(f'<div class="chart">{_fig(viz.recommendation_gauge(m.recommendation_mean))}</div>')
        H.append('</div>')
        if sc.headline:
            H.append(f'<p class="headline">{esc(sc.headline)}</p>')
        if sc.signals:
            H.append('<div class="chips">')
            for sig in sc.signals:
                c, _ = IMPACT.get(sig.verdict, ("#64748b", ""))
                H.append(f'<div class="chip"><span class="dot" style="background:{c}"></span>'
                         f'<b>{esc(sig.label)}</b><br><small>{esc(sig.detail)}</small></div>')
            H.append('</div>')
    H.append('<div class="grid2">')
    H.append(f'<div class="chart">{_fig(viz.target_chart(m))}</div>')
    H.append(f'<div class="chart">{_fig(viz.price_history_chart(report.price_history, m.fifty_two_high, m.fifty_two_low))}</div>')
    H.append('</div>')
    if p.summary:
        H.append(f'<details><summary>Business summary</summary><p>{esc(p.summary)}</p></details>')
    H.append('</section>')

    # ---- Section: Financials ----
    H.append('<section><h2>💰 Financials</h2><div class="grid2">')
    H.append(f'<div class="chart">{_fig(viz.revenue_income_chart(e))}</div>')
    H.append(f'<div class="chart">{_fig(viz.eps_surprise_chart(e))}</div>')
    H.append('</div>')
    H.append('<table><tr><th>Target low</th><th>Mean</th><th>Median</th><th>High</th><th># Analysts</th></tr>'
             f'<tr><td>{_num(m.target_low)}</td><td>{_num(m.target_mean)}</td><td>{_num(m.target_median)}</td>'
             f'<td>{_num(m.target_high)}</td><td>{_num(m.num_analysts, "{:.0f}")}</td></tr></table>')
    H.append('<table><tr><th>Profit margin</th><th>Revenue growth</th><th>Trailing P/E</th><th>52w range</th></tr>'
             f'<tr><td>{_pct(m.profit_margin, 100)}</td><td>{_pct(m.revenue_growth, 100)}</td>'
             f'<td>{_num(m.trailing_pe, "{:.1f}")}</td>'
             f'<td>{_num(m.fifty_two_low, "{:.0f}")}–{_num(m.fifty_two_high, "{:.0f}")}</td></tr></table>')
    if e.annual:
        H.append('<h3>Annual results</h3><table><tr><th>Period</th><th>Revenue</th><th>Net income</th></tr>')
        for r in e.annual:
            H.append(f'<tr><td>{esc(r.period[:10])}</td><td>{_money(r.revenue)}</td><td>{_money(r.net_income)}</td></tr>')
        H.append('</table>')
    H.append('</section>')

    # ---- Section: Earnings (promised vs delivered) ----
    H.append('<section><h2>📅 Earnings</h2>')
    H.append(f'<p><b>Next earnings date:</b> {esc(e.next_date) or "—"}</p>')
    if e.surprises:
        H.append('<h3>Beat / miss history</h3><table><tr><th>Date</th><th>Est EPS</th><th>Reported</th><th>Surprise %</th></tr>')
        for sp in e.surprises:
            H.append(f'<tr><td>{esc(sp.date)}</td><td>{_num(sp.eps_estimate)}</td>'
                     f'<td>{_num(sp.eps_reported)}</td><td>{_num(sp.surprise_pct, "{:.1f}")}</td></tr>')
        H.append('</table>')
    reviews = s.get("earnings_reviews") or []
    if reviews:
        H.append('<h3>What they promised vs. delivered</h3>')
        for rv in reviews:
            c, word = EARN.get(str(rv.get("verdict")).lower(), ("#64748b", "—"))
            H.append(f'<div class="erow"><div class="ehead"><b>{esc(rv.get("period", "Earnings report"))}</b>'
                     f'<span class="ebadge" style="background:{c}">{word}</span></div>')
            if rv.get("note"):
                H.append(f'<p class="enote">{esc(rv.get("note"))}</p>')
            segs = rv.get("segments") or []
            if segs:
                H.append('<table><tr><th>Segment</th><th>How it did</th></tr>')
                for sg in segs:
                    H.append(f'<tr><td>{esc(sg.get("name"))}</td><td>{esc(sg.get("result"))}</td></tr>')
                H.append('</table>')
            H.append('<div class="grid2 pd">'
                     f'<div class="pd-box"><div class="pd-h">🎯 Promised (prior guidance)</div><p>{esc(rv.get("promised") or "—")}</p></div>'
                     f'<div class="pd-box"><div class="pd-h">📦 Delivered (actual)</div><p>{esc(rv.get("delivered") or "—")}</p></div></div>')
            H.append('</div>')
    else:
        H.append('<p class="muted">Run the agent for the promised-vs-delivered review of the last 2-3 reports.</p>')
    H.append('</section>')

    # ---- Section: AI Analysis ----
    H.append('<section><h2>🤖 AI Analysis</h2>')
    if s:
        if s.get("what_they_do"):
            H.append(f'<p><b>What they do:</b> {esc(s["what_they_do"])}</p>')
        H.append('<div class="grid2">')
        donut = viz.segments_donut(s.get("revenue_segments") or [])
        if donut is not None:
            H.append(f'<div class="chart"><h3>Revenue mix (est.)</h3>{_fig(donut)}</div>')
        conf = s.get("confidence")
        if isinstance(conf, (int, float)):
            H.append(f'<div class="chart">{_fig(viz.confidence_gauge(conf))}</div>')
        H.append('</div>')
        trends = s.get("trends") or []
        if trends:
            H.append('<h3>Sector &amp; macro trends</h3><table><tr><th>Trend</th><th>Impact</th><th>Note</th></tr>')
            for tr in trends:
                c, word = IMPACT.get(str(tr.get("impact")).lower(), ("#64748b", esc(tr.get("impact"))))
                H.append(f'<tr><td>{esc(tr.get("name"))}</td>'
                         f'<td><span style="color:{c};font-weight:600">{word}</span></td><td>{esc(tr.get("note"))}</td></tr>')
            H.append('</table>')
        ap = s.get("ai_positioning") or {}
        if ap.get("stance"):
            c, word = STANCE.get(str(ap["stance"]).lower(), ("#64748b", ap["stance"]))
            H.append(f'<p><b>AI positioning:</b> <span style="color:{c};font-weight:600">{esc(word)}</span> — {esc(ap.get("note", ""))}</p>')
        if s.get("bull") or s.get("bear"):
            H.append('<div class="grid2">')
            if s.get("bull"):
                H.append('<div class="case bull"><h3>🐂 Bull case</h3><ul>' +
                         "".join(f"<li>{esc(x)}</li>" for x in s["bull"]) + '</ul></div>')
            if s.get("bear"):
                H.append('<div class="case bear"><h3>🐻 Bear case</h3><ul>' +
                         "".join(f"<li>{esc(x)}</li>" for x in s["bear"]) + '</ul></div>')
            H.append('</div>')
        if s.get("analyst_note"):
            H.append(f'<p><b>Latest analyst view:</b> {esc(s["analyst_note"])}</p>')
        if s.get("key_risks"):
            H.append('<h3>Key risks before next earnings</h3><ul>' +
                     "".join(f"<li>{esc(x)}</li>" for x in s["key_risks"]) + '</ul>')
    if detail:
        H.append('<details open><summary>Full written analysis</summary>'
                 f'<div class="prose">{_md.markdown(detail, extensions=["tables", "sane_lists"])}</div></details>')
    if not s and not detail:
        H.append('<p class="muted">Run the Claude agent in the app to populate this section.</p>')
    H.append('</section>')

    # ---- Section: Data ----
    if report.website and (report.website.products or report.website.description) or report.news:
        H.append('<section><h2>📋 Data</h2>')
        if report.website and report.website.description:
            H.append(f'<p class="muted">{esc(report.website.description)}</p>')
        if report.website and report.website.products:
            H.append('<ul>' + "".join(f"<li>{esc(x)}</li>" for x in report.website.products) + '</ul>')
        if report.news:
            H.append('<h3>Recent news</h3><ul>')
            for n in report.news:
                link = f'<a href="{esc(n.url)}">{esc(n.title)}</a>' if n.url else esc(n.title)
                src = " · ".join(x for x in [n.source, n.date] if x)
                H.append(f'<li>{link}<br><small class="muted">{esc(src)}</small></li>')
            H.append('</ul>')
        H.append('</section>')

    body = "\n".join(H)
    return _PAGE.format(title=esc(f"{p.name} ({p.ticker})"), plotly=_plotlyjs(), body=body)


_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Stock Research</title>
<script>{plotly}</script>
<style>
  :root {{ --brand:#0ea5e9; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0; --bg:#f8fafc; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         color:var(--ink); background:var(--bg); margin:0; line-height:1.5; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:24px 20px 64px; }}
  header {{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:22px; box-shadow:0 1px 3px rgba(0,0,0,.05); }}
  h1 {{ margin:0; font-size:26px; }}
  .ticker {{ color:var(--brand); font-weight:700; }}
  .meta {{ color:var(--muted); font-size:13px; margin-top:4px; }}
  .kpis {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }}
  .kpi {{ flex:1 1 130px; background:var(--bg); border:1px solid var(--line); border-radius:10px; padding:10px 12px; }}
  .kpi-label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
  .kpi-value {{ font-size:18px; font-weight:700; margin-top:2px; }}
  .verdict {{ margin-top:16px; border-left:5px solid; padding:10px 14px; background:var(--bg); border-radius:8px; }}
  .vbadge {{ color:#fff; font-weight:700; padding:3px 10px; border-radius:999px; font-size:13px; }}
  .verdict p {{ margin:8px 0 0; font-size:15px; }}
  section {{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:22px; margin-top:18px; box-shadow:0 1px 3px rgba(0,0,0,.05); }}
  h2 {{ margin:0 0 14px; font-size:20px; border-bottom:2px solid var(--line); padding-bottom:8px; }}
  h3 {{ font-size:15px; margin:18px 0 8px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  @media (max-width:760px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
  .chart {{ min-width:0; }}
  .headline {{ color:var(--muted); font-style:italic; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:10px; }}
  .chip {{ flex:1 1 160px; background:var(--bg); border:1px solid var(--line); border-radius:10px; padding:8px 10px; font-size:13px; }}
  .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; }}
  table {{ width:100%; border-collapse:collapse; margin:8px 0; font-size:13.5px; }}
  th,td {{ text-align:left; padding:7px 9px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ background:var(--bg); font-size:12px; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); }}
  .erow {{ border:1px solid var(--line); border-radius:10px; padding:12px 14px; margin:12px 0; }}
  .ehead {{ display:flex; justify-content:space-between; align-items:center; }}
  .ebadge {{ color:#fff; font-weight:600; padding:2px 9px; border-radius:999px; font-size:12px; }}
  .enote {{ color:var(--muted); margin:6px 0; }}
  .pd {{ margin-top:6px; }}
  .pd-box {{ background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }}
  .pd-h {{ font-weight:600; font-size:13px; margin-bottom:4px; }}
  .case {{ border:1px solid var(--line); border-radius:10px; padding:6px 14px; }}
  .case.bull {{ background:#f0fdf4; }} .case.bear {{ background:#fef2f2; }}
  .case ul {{ margin:8px 0; padding-left:20px; }}
  .muted {{ color:var(--muted); }}
  details {{ margin-top:12px; }}
  summary {{ cursor:pointer; font-weight:600; }}
  .prose {{ margin-top:10px; }}
  .prose table {{ font-size:13px; }}
  a {{ color:var(--brand); }}
</style></head>
<body><div class="wrap">
{body}
<p class="meta" style="text-align:center;margin-top:24px">⚠️ Research only — not financial advice. Data via Yahoo Finance &amp; public web; may be delayed or incomplete.</p>
</div></body></html>
"""
