---
name: stock-research
description: >-
  Research a public company before investing. Use when the user gives a company
  website, name, or ticker and wants to know what the company does, how it makes
  money, its sector/segments, analyst price targets, valuation, earnings track
  record (promised vs. delivered over the last 2-3 reports), AI positioning, how
  macro/sector trends (e.g. datacenter/AI capex) affect it, and whether it's a
  reasonable entry. Launches a local Streamlit dashboard (chart-first, with a
  PDF export) that pulls Yahoo Finance data and runs a headless Claude Code agent
  for the qualitative analysis. Runs entirely on the existing Claude Code
  subscription — no paid API key required.
allowed-tools: Bash, Read
---

# Stock Research

A self-contained Streamlit web app that turns a company website / ticker into a
skimmable, chart-first research dashboard plus an automated written analysis.
All files live in this skill directory; `${CLAUDE_SKILL_DIR}` points at it.

## What it produces

Five tabs:

1. **Overview** — composite-score gauge, analyst-consensus gauge, scorecard
   chips, price-target chart, 12-month price history.
2. **Financials** — revenue/net-income bars, EPS-surprise bars, analyst targets,
   key fundamentals, annual results table.
3. **Earnings** — estimate-vs-reported EPS + beat/miss history, and an
   agent-built **promised-vs-delivered** review of the last 2-3 reports
   (segment by segment, with an over/under-delivered verdict).
4. **AI Analysis** — a Claude agent web-researches and returns a charted verdict
   (Buy/Hold/Avoid + confidence gauge), revenue-mix donut, sector-trend arrows,
   AI-positioning badge, bull/bear columns, and a full written deep-dive.
5. **Data & Brief** — website products, recent news, and downloadable PDF + brief.

A **PDF report** (shareable with a team) is downloadable from the AI Analysis and
Data tabs.

## How it works (no paid API key)

- Hard numbers come from **Yahoo Finance** via `yfinance` (deterministic charts —
  numbers are always exact).
- Qualitative analysis runs by shelling out to the local **`claude` CLI**
  (`claude -p --dangerously-skip-permissions --allowedTools WebSearch WebFetch`),
  which uses the user's existing Claude Code subscription — **nothing is billed to
  an API key**. Web tools are scoped to search/fetch so the agent can't touch files.

> ⚠️ Research tool, not financial advice. Yahoo data can be delayed or incomplete.

## Running it

The app needs a Python virtual environment with the dependencies installed. On
first use, create it; afterward just launch.

**First-time setup** (only if `${CLAUDE_SKILL_DIR}/.venv` does not exist):

```bash
cd "${CLAUDE_SKILL_DIR}"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
```

**Launch the app** (every time). Run it detached so the server survives — a
plain foreground/background run inside a sandbox gets torn down:

```bash
cd "${CLAUDE_SKILL_DIR}"
nohup .venv/bin/streamlit run app.py --server.headless true --server.port 8501 \
  >/tmp/stock_research_streamlit.log 2>&1 &
disown
```

**Hand the company straight to the app via the URL.** The app reads `?q=` (a
website or name) or `?ticker=` from the URL and auto-runs the research on load —
the user just opens the link, no sidebar typing or clicking required. When the
skill is invoked with an argument (a website/name/ticker in ARGUMENTS), give the
user a pre-filled link, URL-encoding the value:

- Website/name → `http://localhost:8501/?q=<url-encoded value>`
  e.g. `http://localhost:8501/?q=https%3A%2F%2Fwww.nvidia.com`
- Bare ticker → `http://localhost:8501/?ticker=NVDA`

Opening that link runs the data fetch, then the Claude agent auto-runs; the
Earnings tab's promised-vs-delivered review and the full AI Analysis populate
from that run. With no argument, just send the user to `http://localhost:8501`
and they type a company in the sidebar.

Requires the `claude` CLI on PATH for the agent (the data tabs work without it).

## Notes

- Sidebar controls: model (sonnet/opus), auto-run agent, and let-agent-web-search.
- If port 8501 is busy, add `--server.port <PORT>` to the launch command.
- Architecture and per-file responsibilities are documented in
  [README.md](README.md).
