# 📈 Stock Research

A **chart-first** research dashboard for investors. Give it a company website,
name, or ticker and it produces a skimmable, five-tab report — valuation gauges,
analyst targets, an earnings *promised-vs-delivered* review, and a Buy / Hold /
Avoid verdict — then lets you export the whole thing as a shareable HTML or PDF.

The qualitative analysis is written by a **Claude Code agent that runs on your
existing subscription — no paid API key required.**

> ⚠️ **Research tool, not financial advice.** Numbers come from Yahoo Finance
> (via `yfinance`) and public web pages, and can be delayed or incomplete.

---

## ✨ What you get

Five tabs, built from exact data (charts never hallucinate numbers):

| Tab | Contents |
|-----|----------|
| 📊 **Overview** | Composite-score gauge, analyst-consensus gauge, scorecard signals, price-target chart, 12-month price history |
| 💰 **Financials** | Revenue/net-income bars, EPS-surprise bars, analyst targets, key fundamentals (margin, growth, P/E, 52-week range) |
| 📅 **Earnings** | Estimate-vs-reported EPS, beat/miss history, and an agent-built review of the last 2–3 reports — *segment by segment, where the company over- or under-delivered vs. its own prior guidance* |
| 🤖 **AI Analysis** | Buy/Hold/Avoid verdict, confidence gauge, revenue-mix donut, sector-trend arrows, AI-positioning badge, bull/bear cases, and a full written deep-dive |
| 📋 **Data & Brief** | Website products, recent news, and downloadable HTML / PDF / Markdown brief |

Extras:
- **🔎 Every technical term has a hover "?" tooltip** explaining it in plain English.
- **⬇️ HTML & PDF export** — the HTML report embeds the same interactive charts and mirrors the app, so it works offline and looks like the dashboard.
- **🔗 Deep links** — open `?q=<website>` or `?ticker=<SYMBOL>` to auto-run research on load.

---

## 🚀 Quick start

**Requirements:** Python 3.9+, and the [`claude` CLI](https://docs.claude.com/en/docs/claude-code)
on your `PATH` (logged in) for the AI analysis. The data tabs work without it.

```bash
git clone https://github.com/aswithabukka/stock-research.git
cd stock-research
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at **http://localhost:8501**. Enter a website like `https://www.nvidia.com`
(or a ticker like `NVDA`) in the sidebar and press **Research** — or jump straight in:

```
http://localhost:8501/?q=https://www.apple.com
http://localhost:8501/?ticker=NVDA
```

Sidebar controls: **Model** (sonnet/opus), **Auto-run agent after research**, and
**Let agent web-search latest data**. Each run prints its cost, duration, and turn count.

---

## 🤖 How the agent runs (no API key)

When research finishes, the app pipes a structured brief into a local Claude Code
subprocess:

```bash
claude -p --output-format json --dangerously-skip-permissions \
       --model sonnet --allowedTools WebSearch WebFetch
```

It web-searches for the latest targets / earnings / news, returns **structured JSON**
(for the charts) plus a **detailed Markdown** write-up, and the app renders both. Tools
are scoped to `WebSearch` / `WebFetch`, so the agent **cannot read or write your files**.
Auth comes from your Claude Code login — **nothing is billed to an API key**.

Prefer manual control? Turn off **Auto-run agent**, download the brief from the Data
tab, and paste it into a fresh Claude session — the brief ends with the exact questions.

---

## 🧱 Architecture

| Layer | File | Job |
|-------|------|-----|
| Orchestrator | `research/__init__.py` | `run_research(input)` → `ResearchReport` |
| Resolver | `research/resolver.py` | Website/name/ticker → best real symbol via Yahoo search |
| Financials | `research/financials.py` | Profile, valuation, analyst targets, earnings, 1y price history (`yfinance`) |
| Website | `research/website.py` | Scrapes homepage for tagline + product links |
| News | `research/news.py` | Yahoo ticker news + DuckDuckGo (key-less) fallback |
| Analysis | `research/analysis.py` | Heuristic scorecard + the agent brief |
| Charts | `research/viz.py` | Plotly builders (gauges, target/price/earnings charts, donut) — drawn from exact data |
| Agent | `research/agent.py` | Shells out to `claude -p`; returns structured JSON + Markdown |
| HTML export | `research/report_html.py` | Self-contained HTML report with embedded interactive charts |
| PDF export | `research/report_pdf.py` | Shareable PDF via `fpdf2` |
| Web app | `app.py` | Streamlit UI (tabs, tooltips, exports, optional password gate) |

---

## 🏠 Self-hosting (always-on, free, access from anywhere)

Run it on a spare Mac (e.g. a Mac mini) so you and others can reach it from any
phone or laptop — securely and for free — using [Tailscale](https://tailscale.com).
The `deploy/` folder has everything:

- `run_server.sh` — launches the app, **bound only to your Tailscale IP** (invisible on your home Wi-Fi; never `0.0.0.0`).
- `com.stockresearch.app.plist` — a launchd service that **auto-starts and self-restarts**.
- `app_password.txt` *(you create it)* — turns on a **password gate**.
- **[`deploy/SETUP_MACMINI.md`](deploy/SETUP_MACMINI.md)** — full step-by-step guide + troubleshooting.

**Security model:** Tailscale-only private access (encrypted, your devices only),
password-protected, Streamlit XSRF/CORS protections on, no stored secrets, agent
sandboxed to web tools. Don't expose it to the public internet (no port-forwarding
/ Tailscale Funnel / tunnels) and it stays locked down.

---

## 📤 Sharing a report

The **AI Analysis** and **Data & Brief** tabs have a **⬇️ Download HTML report**
button (primary) plus PDF and Markdown options. The HTML version bundles the
snapshot, verdict, revenue mix, sector trends, earnings review, bull/bear, analyst
targets, scorecard, and the full written analysis — with the live charts — so a
teammate can open it in any browser and make a buy/no-buy call. Run the agent first
for the complete version; before that you get a data-only export.

---

## 📦 As a Claude Code skill

This repo doubles as a [Claude Code skill](https://docs.claude.com/en/docs/claude-code)
(`SKILL.md` included). Drop it in `~/.claude/skills/stock-research/` and invoke it with
`/stock-research <company>` or just ask Claude to "research \<company\> for investing."

---

*Built for personal research. Not financial advice — do your own due diligence.*
