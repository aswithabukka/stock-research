"""Stock research web app — visual edition.

Paste a company website (or ticker) and get a skimmable, chart-first dashboard:
gauges, price-target and earnings charts, plus an auto-run Claude agent that
web-researches and returns a charted verdict AND a full written analysis.

Run:  streamlit run app.py
"""
from __future__ import annotations

import hmac
import os

import streamlit as st

from research import agent, analysis, report_html, report_pdf, run_research, viz
from research.models import ResearchReport

st.set_page_config(page_title="Stock Research", page_icon="📈", layout="wide")


def _check_password() -> None:
    """Gate the app behind a password if STOCK_RESEARCH_PASSWORD is set.

    No env var (e.g. local dev) -> no gate. Constant-time comparison avoids
    timing attacks. Auth is remembered for the browser session.
    """
    expected = os.environ.get("STOCK_RESEARCH_PASSWORD")
    if not expected:
        return
    if st.session_state.get("_authed"):
        return
    st.markdown("## 🔒 Stock Research")
    st.caption("This dashboard is private. Enter the password to continue.")
    pw = st.text_input("Password", type="password", key="_pw")
    if pw:
        if hmac.compare_digest(pw, expected):
            st.session_state["_authed"] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


_check_password()

VERDICT_EMOJI = {"positive": "🟢", "neutral": "🟡", "negative": "🔴", "unknown": "⚪"}
IMPACT_ARROW = {"positive": "🟢 ↑", "neutral": "🟡 →", "negative": "🔴 ↓"}
STANCE_BADGE = {
    "tailwind": ("🟢", "Tailwind"),
    "threat": ("🔴", "Threat"),
    "neutral": ("🟡", "Neutral"),
}
EARNINGS_VERDICT = {
    "beat": ("🟢", "Over-delivered"),
    "met": ("🟡", "In line"),
    "missed": ("🔴", "Under-delivered"),
}
PLOTLY_CFG = {"displayModeBar": False}

# Plain-English explanations shown via the "?" help icon next to each term.
GLOSSARY = {
    "composite_score": "Our overall 0–100 health score — the average of five signals "
        "(analyst upside, analyst rating, revenue growth, profitability, valuation). "
        "Higher leans more constructive. It's a rough heuristic, not financial advice.",
    "analyst_consensus": "The average Wall-Street analyst rating, on a 1–5 scale: "
        "1 = Strong Buy, 3 = Hold, 5 = Sell. Lower is more bullish.",
    "price": "Latest share price from Yahoo Finance (can be delayed).",
    "market_cap": "Total company value = share price × shares outstanding. T = trillion, B = billion.",
    "fwd_pe": "Forward P/E — share price ÷ expected next-year earnings per share. "
        "A higher number means the stock is priced for more growth (pricier); lower can mean cheaper.",
    "trailing_pe": "Trailing P/E — share price ÷ the last 12 months' actual earnings per share.",
    "target_upside": "How far the average analyst 12-month price target sits above (or below) "
        "today's price, as a percentage.",
    "consensus": "Analysts' overall recommendation (Buy / Hold / Sell), in plain words.",
    "profit_margin": "Net profit margin — what % of each sales dollar becomes profit after all costs.",
    "revenue_growth": "Year-over-year growth in revenue (total sales).",
    "range_52w": "The lowest and highest the share price has traded over the past 52 weeks.",
    "price_targets": "Analysts' 12-month price forecasts — the lowest, average (mean), "
        "middle (median), and highest of all covering analysts.",
    "price_history": "The daily closing price over the last 12 months, with the 52-week high and low marked.",
    "revenue_income": "Annual revenue (sales) vs. net income (profit) over recent years, in $ billions.",
    "eps_surprise": "Each quarter's expected earnings per share (EPS) vs. what was actually reported. "
        "Reported above estimate = a 'beat'.",
    "quarters_beaten": "How many of the recent quarters the company reported EPS above the analyst estimate.",
    "revenue_mix": "Estimated share of revenue by business segment (e.g. iPhone, Services) — from the AI agent.",
    "agent_confidence": "How confident the AI analysis is in its own verdict, 0–100. Not a guarantee.",
    "verdict": "The AI agent's overall call — Buy, Hold, or Avoid — with a one-line reason.",
}


def _chart_header(container, label: str, key: str) -> None:
    """A small heading with a hoverable '?' icon explaining a technical term."""
    container.subheader(label, help=GLOSSARY.get(key, ""), anchor=False, divider=False)


# Explanations for the five scorecard chips (keyed by their signal label).
SIGNAL_HELP = {
    "Analyst upside": "One of the five composite-score signals. How far the average analyst "
        "12-month price target is above today's price. Positive = analysts see room to rise; "
        "negative = the stock already trades above target.",
    "Analyst rating": "One of the five composite-score signals. The Wall-Street consensus rating "
        "(1 = Strong Buy … 5 = Sell). A buy lean scores positive, a sell lean scores negative.",
    "Revenue growth": "One of the five composite-score signals. Year-over-year growth in sales. "
        "Faster growth scores positive; shrinking revenue scores negative.",
    "Profitability": "One of the five composite-score signals. Whether the company is profitable "
        "and how fat its net profit margin is. Losses score negative.",
    "Valuation (fwd P/E)": "One of the five composite-score signals. Forward P/E (price ÷ expected "
        "earnings). Lower is cheaper and scores positive; a very high P/E scores cautious.",
}


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


def _md_safe(text) -> str:
    """Escape $ so Streamlit's markdown doesn't render text as LaTeX math."""
    return "" if text is None else str(text).replace("$", r"\$")


@st.cache_data(show_spinner=False, ttl=900)
def _cached_research(raw: str, manual: str, with_news: bool) -> ResearchReport:
    return run_research(raw, manual_ticker=manual or None, with_news=with_news)


# Pre-fill from the URL (?q=<website/name>&ticker=<TICKER>) so the skill can
# launch the app already pointed at a company — just open the link, no typing.
_qp = st.query_params
_q_default = _qp.get("q", "") or ""
_ticker_default = _qp.get("ticker", "") or ""

# ---------------------------------------------------------------- sidebar
st.sidebar.title("📈 Stock Research")
st.sidebar.caption("Free data via Yahoo Finance + web scraping. No API key required.")
raw = st.sidebar.text_input("Company website or name", value=_q_default,
                            placeholder="https://www.nvidia.com")
manual = st.sidebar.text_input("Ticker override (optional)", value=_ticker_default,
                               placeholder="NVDA")
with_news = st.sidebar.checkbox("Fetch recent news", value=True)
go = st.sidebar.button("Research", type="primary", use_container_width=True)

# Auto-run once when the app is opened via a pre-filled link (?q=...).
auto_go = (bool(_q_default) or bool(_ticker_default)) and "report" not in st.session_state

st.sidebar.markdown("---")
st.sidebar.markdown("**🤖 Claude agent analysis**")
st.sidebar.caption("Runs on your Claude Code subscription — no API key.")
agent_model = st.sidebar.selectbox("Model", ["sonnet", "opus"], index=0)
auto_agent = st.sidebar.checkbox("Auto-run agent after research", value=True)
agent_web = st.sidebar.checkbox("Let agent web-search latest data", value=True)

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ For research only — not financial advice. Numbers come from Yahoo Finance "
    "and may be delayed or incomplete."
)

# ---------------------------------------------------------------- landing
if not go and not auto_go and "report" not in st.session_state:
    st.title("Company stock research")
    st.markdown(
        "Enter a **company website** (e.g. `https://www.nvidia.com`) or a name in the sidebar "
        "and press **Research**.\n\n"
        "You'll get a chart-first dashboard — valuation & analyst-target gauges, price and "
        "earnings charts — plus a **Claude agent** that web-researches and returns a charted "
        "verdict and a full written analysis (what they do, AI positioning, datacenter/sector "
        "trends, bull/bear, is-it-a-reasonable-entry)."
    )
    st.stop()

if go or auto_go:
    if not raw and not manual:
        st.error("Enter a website/name or a ticker in the sidebar.")
        st.stop()
    try:
        with st.spinner("Researching… (resolving ticker, pulling financials, news)"):
            st.session_state["report"] = _cached_research(raw, manual, with_news)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not complete research: {exc}")
        st.stop()

report: ResearchReport = st.session_state["report"]
p, m, e = report.profile, report.market, report.earnings
brief = analysis.build_brief(report)

# ---------------------------------------------------------------- header
st.title(f"{p.name}  ·  {p.ticker}")
meta = " · ".join(x for x in [p.exchange, p.sector, p.industry, p.country] if x)
if meta:
    st.caption(meta)
for w in report.warnings:
    st.warning(w)

# KPI row (always visible above the tabs)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Price", f"{_num(m.price)} {m.currency or ''}".strip(), help=GLOSSARY["price"])
c2.metric("Market cap", _money(m.market_cap), help=GLOSSARY["market_cap"])
c3.metric("Fwd P/E", _num(m.forward_pe, "{:.1f}"), help=GLOSSARY["fwd_pe"])
up = m.upside_pct
c4.metric("Target upside", f"{up:.1f}%" if up is not None else "—", help=GLOSSARY["target_upside"])
c5.metric("Consensus", (m.recommendation_key or "—").replace("_", " ").title(), help=GLOSSARY["consensus"])

agent_run_key = f"{p.ticker}:{agent_model}:{agent_web}"


@st.cache_data(show_spinner=False)
def _pdf_bytes(ticker: str, sig: str) -> bytes:
    """Cached by ticker + a signature of the agent result so we don't rebuild every rerun."""
    res = st.session_state.get("agent_results", {}).get(agent_run_key)
    res = res if (res and res.get("ok")) else None
    return report_pdf.build_pdf(report, res)


@st.cache_data(show_spinner=False)
def _html_report(ticker: str, sig: str) -> str:
    """Self-contained HTML report that mirrors the app (interactive charts included)."""
    res = st.session_state.get("agent_results", {}).get(agent_run_key)
    res = res if (res and res.get("ok")) else None
    return report_html.build_html(report, res)


tab_overview, tab_fin, tab_earnings, tab_ai, tab_data = st.tabs(
    ["📊 Overview", "💰 Financials", "📅 Earnings", "🤖 AI Analysis", "📋 Data & Brief"]
)

# ================================================================ OVERVIEW
with tab_overview:
    if report.scorecard:
        sc = report.scorecard
        g1, g2 = st.columns(2)
        _chart_header(g1, "Composite score", "composite_score")
        g1.plotly_chart(viz.score_gauge(sc.score, title=None), use_container_width=True, config=PLOTLY_CFG)
        _chart_header(g2, "Analyst consensus", "analyst_consensus")
        g2.plotly_chart(viz.recommendation_gauge(m.recommendation_mean, title=None),
                        use_container_width=True, config=PLOTLY_CFG)
        st.caption(sc.headline)
        chips = st.columns(len(sc.signals))
        for col, sig in zip(chips, sc.signals):
            col.markdown(f"**{VERDICT_EMOJI.get(sig.verdict,'⚪')} {sig.label}**",
                         help=SIGNAL_HELP.get(sig.label, ""))
            col.caption(sig.detail)

    st.markdown("---")
    t1, t2 = st.columns(2)
    _chart_header(t1, "Analyst price targets", "price_targets")
    t1.plotly_chart(viz.target_chart(m, title=None), use_container_width=True, config=PLOTLY_CFG)
    _chart_header(t2, "Price — last 12 months", "price_history")
    t2.plotly_chart(viz.price_history_chart(report.price_history, m.fifty_two_high, m.fifty_two_low, title=None),
                    use_container_width=True, config=PLOTLY_CFG)

    if p.summary:
        with st.expander("Business summary", expanded=False):
            st.write(p.summary)

# ================================================================ FINANCIALS
with tab_fin:
    f1, f2 = st.columns(2)
    _chart_header(f1, "Revenue & net income", "revenue_income")
    f1.plotly_chart(viz.revenue_income_chart(e, title=None), use_container_width=True, config=PLOTLY_CFG)
    _chart_header(f2, "Earnings: estimate vs reported", "eps_surprise")
    f2.plotly_chart(viz.eps_surprise_chart(e, title=None), use_container_width=True, config=PLOTLY_CFG)

    _chart_header(st, "Analyst price targets", "price_targets")
    tcol = st.columns(4)
    tcol[0].metric("Low", _num(m.target_low), help=GLOSSARY["price_targets"])
    tcol[1].metric("Mean", _num(m.target_mean), help=GLOSSARY["price_targets"])
    tcol[2].metric("Median", _num(m.target_median), help=GLOSSARY["price_targets"])
    tcol[3].metric("High", _num(m.target_high), help=GLOSSARY["price_targets"])
    st.caption(f"{int(m.num_analysts)} analysts" if m.num_analysts else "Coverage count unavailable")

    _chart_header(st, "Key fundamentals", "profit_margin")
    k = st.columns(4)
    k[0].metric("Profit margin", _pct(m.profit_margin, 100), help=GLOSSARY["profit_margin"])
    k[1].metric("Revenue growth", _pct(m.revenue_growth, 100), help=GLOSSARY["revenue_growth"])
    k[2].metric("Trailing P/E", _num(m.trailing_pe, "{:.1f}"), help=GLOSSARY["trailing_pe"])
    k[3].metric("52w range", f"{_num(m.fifty_two_low,'{:.0f}')}–{_num(m.fifty_two_high,'{:.0f}')}",
                help=GLOSSARY["range_52w"])

    st.write(f"**Next earnings date:** {e.next_date or '—'}")
    if e.annual:
        st.markdown("**Annual results** (most recent first)")
        st.table([
            {"Period": r.period[:10], "Revenue": _money(r.revenue), "Net income": _money(r.net_income)}
            for r in e.annual
        ])
    if e.surprises:
        st.markdown("**Recent EPS surprises**")
        st.table([
            {"Date": s.date, "Est EPS": _num(s.eps_estimate), "Reported": _num(s.eps_reported),
             "Surprise %": _num(s.surprise_pct, "{:.1f}")}
            for s in e.surprises
        ])

# ================================================================ EARNINGS
with tab_earnings:
    st.markdown("#### Earnings track record")
    st.caption(
        "Hard numbers from Yahoo Finance below; the promised-vs-delivered review of the "
        "last few reports comes from the Claude agent (run it in the **AI Analysis** tab)."
    )

    # Deterministic backbone: estimate vs reported EPS.
    ec1, ec2 = st.columns([3, 2])
    _chart_header(ec1, "Earnings: estimate vs reported", "eps_surprise")
    ec1.plotly_chart(viz.eps_surprise_chart(e, title=None), use_container_width=True, config=PLOTLY_CFG,
                     key="earnings_eps_chart")
    with ec2:
        st.markdown("**Beat / miss history**")
        if e.surprises:
            beats = sum(1 for s in e.surprises if (s.surprise_pct or 0) > 0)
            st.metric("Quarters beaten", f"{beats}/{len(e.surprises)}",
                      help=GLOSSARY["quarters_beaten"])
            st.write(f"**Next earnings date:** {e.next_date or '—'}")
            st.table([
                {"Date": s.date, "Est EPS": _num(s.eps_estimate), "Reported": _num(s.eps_reported),
                 "Surprise %": _num(s.surprise_pct, "{:.1f}")}
                for s in e.surprises
            ])
        else:
            st.caption("No EPS estimate/actual history available.")

    st.markdown("---")
    st.markdown("#### Last few reports — what they promised vs. delivered")

    _eres = st.session_state.get("agent_results", {}).get(agent_run_key)
    reviews = []
    if _eres and _eres.get("ok"):
        reviews = (_eres.get("structured") or {}).get("earnings_reviews") or []

    if reviews:
        for rv in reviews:
            emoji, label = EARNINGS_VERDICT.get(str(rv.get("verdict")).lower(), ("⚪", "—"))
            with st.container():
                st.markdown(f"##### {emoji} {_md_safe(rv.get('period', 'Earnings report'))} — {label}")
                if rv.get("note"):
                    st.caption(_md_safe(rv["note"]))

                segs = rv.get("segments") or []
                if segs:
                    st.markdown("**Key segments this quarter**")
                    st.table([
                        {"Segment": sg.get("name", "—"), "How it did": sg.get("result", "—")}
                        for sg in segs
                    ])

                pc1, pc2 = st.columns(2)
                with pc1:
                    st.markdown("**🎯 Promised (prior guidance)**")
                    st.write(_md_safe(rv.get("promised") or "—"))
                with pc2:
                    st.markdown("**📦 Delivered (actual)**")
                    st.write(_md_safe(rv.get("delivered") or "—"))
                st.markdown("---")
    elif _eres and not _eres.get("ok"):
        st.error(_eres.get("error", "Agent run failed."))
    else:
        st.info(
            "Run the Claude agent in the **🤖 AI Analysis** tab to pull the last 2-3 earnings "
            "reports and see, segment by segment, where the company over- or under-delivered "
            "versus its own prior guidance."
        )

# ================================================================ AI ANALYSIS
with tab_ai:
    if not agent.is_available():
        st.info(
            "The `claude` CLI isn't on PATH, so automated analysis is off. Install Claude Code, "
            "or use the brief in the Data tab and paste it into Claude Code yourself."
        )
    else:
        st.session_state.setdefault("agent_results", {})
        run_key = agent_run_key
        force = st.button("Run / re-run agent analysis")
        need_auto = auto_agent and run_key not in st.session_state["agent_results"]

        if force or need_auto:
            msg = ("Claude agent researching the web and writing the analysis… (a few minutes)"
                   if agent_web else "Claude agent writing the analysis…")
            with st.spinner(msg):
                try:
                    result = agent.run_agent(brief, model=agent_model, web_research=agent_web)
                    st.session_state["agent_results"][run_key] = {"ok": True, **result}
                except agent.AgentError as exc:
                    st.session_state["agent_results"][run_key] = {"ok": False, "error": str(exc)}

        res = st.session_state["agent_results"].get(run_key)
        if res and res.get("ok"):
            s = res.get("structured") or {}

            # Verdict + confidence
            v1, v2 = st.columns([2, 1])
            verdict = (s.get("verdict") or "").strip()
            one = _md_safe(s.get("one_liner") or "")
            with v1:
                if verdict.lower() == "buy":
                    st.success(f"### Verdict: 🟢 Buy\n{one}")
                elif verdict.lower() == "avoid":
                    st.error(f"### Verdict: 🔴 Avoid\n{one}")
                elif verdict.lower() == "hold":
                    st.warning(f"### Verdict: 🟡 Hold\n{one}")
                elif one:
                    st.info(one)
            with v2:
                conf = s.get("confidence")
                if isinstance(conf, (int, float)):
                    _chart_header(st, "Agent confidence", "agent_confidence")
                    st.plotly_chart(viz.confidence_gauge(conf, title=None), use_container_width=True, config=PLOTLY_CFG)

            if s.get("what_they_do"):
                st.markdown(f"**What they do:** {_md_safe(s['what_they_do'])}")

            # Revenue mix donut + trends
            d1, d2 = st.columns(2)
            donut = viz.segments_donut(s.get("revenue_segments") or [])
            if donut is not None:
                _chart_header(d1, "Revenue mix (est.)", "revenue_mix")
                d1.plotly_chart(donut, use_container_width=True, config=PLOTLY_CFG)
            with d2:
                trends = s.get("trends") or []
                if trends:
                    st.markdown("**Sector & macro trends**")
                    for tr in trends:
                        arrow = IMPACT_ARROW.get(str(tr.get("impact")).lower(), "⚪")
                        st.markdown(f"{arrow} **{_md_safe(tr.get('name',''))}** — {_md_safe(tr.get('note',''))}")
                ap = s.get("ai_positioning") or {}
                if ap.get("stance"):
                    emoji, label = STANCE_BADGE.get(str(ap["stance"]).lower(), ("⚪", ap["stance"]))
                    st.markdown(f"**AI positioning:** {emoji} {label} — {_md_safe(ap.get('note',''))}")

            # Bull / Bear
            b1, b2 = st.columns(2)
            with b1:
                if s.get("bull"):
                    st.markdown("**🐂 Bull case**")
                    for x in s["bull"]:
                        st.markdown(f"- ✅ {_md_safe(x)}")
            with b2:
                if s.get("bear"):
                    st.markdown("**🐻 Bear case**")
                    for x in s["bear"]:
                        st.markdown(f"- ⚠️ {_md_safe(x)}")

            if s.get("analyst_note"):
                st.markdown(f"**Latest analyst view:** {_md_safe(s['analyst_note'])}")
            if s.get("key_risks"):
                st.markdown("**Key risks before next earnings**")
                for x in s["key_risks"]:
                    st.markdown(f"- 🔺 {_md_safe(x)}")

            # Full detailed write-up
            if res.get("text"):
                with st.expander("📄 Full written analysis", expanded=False):
                    st.markdown(_md_safe(res["text"]))

            meta_bits = []
            if res.get("cost_usd") is not None:
                meta_bits.append(f"${res['cost_usd']:.3f}")
            if res.get("duration_ms"):
                meta_bits.append(f"{res['duration_ms'] / 1000:.0f}s")
            if res.get("num_turns"):
                meta_bits.append(f"{res['num_turns']} turns")
            meta_bits.append(f"model: {agent_model}")
            st.caption(" · ".join(meta_bits) + " — Not financial advice.")

            st.markdown("---")
            st.markdown("#### Share with your team")
            sig = f"{len(res.get('text') or '')}:{res.get('cost_usd')}"
            dl1, dl2 = st.columns(2)
            try:
                dl1.download_button(
                    "⬇️ Download HTML report (looks like the app)",
                    _html_report(p.ticker, sig),
                    file_name=f"{p.ticker}_analysis.html",
                    mime="text/html",
                    type="primary",
                    help="Self-contained web page with the same charts and layout — opens in any browser.",
                )
            except Exception as exc:  # noqa: BLE001
                dl1.caption(f"HTML export unavailable: {exc}")
            try:
                dl2.download_button(
                    "⬇️ PDF (plain text version)",
                    _pdf_bytes(p.ticker, sig),
                    file_name=f"{p.ticker}_analysis.pdf",
                    mime="application/pdf",
                )
            except Exception as exc:  # noqa: BLE001
                dl2.caption(f"PDF export unavailable: {exc}")
        elif res:
            st.error(res["error"])
        elif not auto_agent:
            st.caption("Auto-run is off — press **Run / re-run agent analysis** above.")

# ================================================================ DATA & BRIEF
with tab_data:
    if report.website and (report.website.products or report.website.description):
        st.markdown("#### From their website")
        if report.website.description:
            st.caption(report.website.description)
        for prod in report.website.products:
            st.markdown(f"- {prod}")

    if report.news:
        st.markdown("#### Recent news")
        for n in report.news:
            title = f"[{n.title}]({n.url})" if n.url else n.title
            st.markdown(f"**{title}**")
            st.caption(" · ".join(x for x in [n.source, n.date] if x))

    st.markdown("---")
    st.markdown("#### Export")
    _res = st.session_state.get("agent_results", {}).get(agent_run_key)
    _res_ok = _res and _res.get("ok")
    _suffix = "" if _res_ok else " (data only — run agent for full analysis)"
    sig = f"{len(_res.get('text') or '') if _res_ok else 0}:{_res.get('cost_usd') if _res_ok else None}"
    ecol1, ecol2, ecol3 = st.columns(3)
    try:
        ecol1.download_button(
            "⬇️ HTML report" + _suffix,
            _html_report(p.ticker, sig),
            file_name=f"{p.ticker}_analysis.html",
            mime="text/html",
            type="primary",
            help="Self-contained web page with the same charts and layout.",
        )
    except Exception as exc:  # noqa: BLE001
        ecol1.caption(f"HTML export unavailable: {exc}")
    try:
        ecol2.download_button(
            "⬇️ PDF (plain)",
            _pdf_bytes(p.ticker, sig),
            file_name=f"{p.ticker}_analysis.pdf",
            mime="application/pdf",
        )
    except Exception as exc:  # noqa: BLE001
        ecol2.caption(f"PDF export unavailable: {exc}")
    ecol3.download_button("⬇️ Brief (.md)", brief, file_name=f"{p.ticker}_brief.md", mime="text/markdown")
    with st.expander("Show brief"):
        st.code(brief, language="markdown")
