# Stock Research

Paste a company **website** (or ticker) and get a **chart-first**, skimmable
research dashboard across five tabs (Overview · Financials · Earnings · AI Analysis ·
Data): score & analyst gauges, a price-target chart, 12-month price, revenue/net-income
and EPS-surprise bars — plus the underlying tables and a heuristic scorecard. The
**Earnings** tab reviews the last 2-3 reports segment by segment and shows where the
company **over- or under-delivered** versus its own prior guidance.

It then **automatically runs a Claude Code agent in the background** (`claude -p`)
that takes the brief, does live web research, and returns **both** a charted summary
(verdict badge, confidence gauge, revenue-mix donut, trend arrows, bull/bear columns)
**and** a full written deep-dive — what they do, AI positioning, datacenter/sector
trends, valuation, and an is-it-a-reasonable-entry verdict. It renders right in the app.

This runs on your **existing Claude Code subscription — no paid API key**. You can
also download the raw brief to continue the conversation in a fresh Claude session.

> ⚠️ Research tool, not financial advice. Data comes from Yahoo Finance (via
> `yfinance`) and public web pages; it can be delayed or incomplete.

## Setup

```bash
cd ~/projects/stock-research
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501. Enter a website like `https://www.nvidia.com`
in the sidebar (or just a ticker like `NVDA`) and press **Research**.

## How it works

| Layer | File | Job |
|-------|------|-----|
| Resolver | `research/resolver.py` | Website/name → ticker via Yahoo's search endpoint |
| Financials | `research/financials.py` | Profile, valuation, analyst targets, earnings, 1y price history (`yfinance`) |
| Website | `research/website.py` | Scrapes homepage for tagline + product/solution links |
| News | `research/news.py` | Yahoo ticker news + DuckDuckGo (key-less) fallback |
| Analysis | `research/analysis.py` | Heuristic scorecard + the Claude Code brief |
| Charts | `research/viz.py` | Plotly figure builders (gauges, target/price/earnings charts, revenue donut) — drawn from the structured data, so numbers are always exact |
| PDF export | `research/report_pdf.py` | Builds a shareable PDF (snapshot, verdict, revenue mix, trends, bull/bear, targets, scorecard + full written analysis) via fpdf2 |
| Agent | `research/agent.py` | Shells out to `claude -p --dangerously-skip-permissions` (web tools on); returns structured JSON (for charts) + detailed Markdown — uses your subscription, no API key |
| Orchestrator | `research/__init__.py` | `run_research(url)` → `ResearchReport` |
| Web app | `app.py` | Streamlit UI |

Sidebar controls: **Model** (sonnet/opus), **Auto-run agent after research**, and
**Let agent web-search latest data**. Each analysis prints its cost, duration, and
turn count. Requires the `claude` CLI on your PATH.

## How the agent runs (no API key)

When research finishes, the app pipes the brief into a local Claude Code subprocess:

```
claude -p --output-format json --dangerously-skip-permissions \
       --model sonnet --allowedTools WebSearch WebFetch
```

The agent web-searches for the latest targets/earnings/news, writes the analysis,
and the app renders it. Tools are scoped to `WebSearch`/`WebFetch` so it can't touch
your files. Auth comes from your Claude Code login — nothing is billed to an API key.

Prefer to drive it manually instead? Turn off **Auto-run agent**, download the brief,
and paste it into a fresh Claude Code session — the brief ends with the exact questions.

## Sharing with your team

Both the **AI Analysis** and **Data & Brief** tabs have a **⬇️ Download PDF report**
button. The PDF bundles the snapshot, verdict, revenue mix, sector trends, bull/bear,
analyst targets, scorecard, and the full written analysis — formatted for a teammate
to read and make a buy/no-buy call. (Run the agent first for the full version; before
that you get a data-only PDF.)
