"""Run the local Claude Code CLI as a headless research agent.

No API key: this shells out to the `claude` binary, which uses the user's
existing Claude Code subscription. The agent is given the research brief and
web tools so it can pull the latest targets / news before answering.

It returns BOTH a detailed Markdown write-up and a structured JSON object so the
app can render charts (verdict gauge, revenue-mix donut, trend arrows, bull/bear).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Optional


class AgentError(Exception):
    pass


CLAUDE_BIN_CANDIDATES = ["claude"]

ANALYSIS_INSTRUCTIONS = """You are an experienced equity research analyst.

Using the structured RESEARCH BRIEF below AND live web search for the latest
information (current analyst price targets, the most recent earnings, recent
product / AI announcements, sector news), analyse this company for a long-term
retail investor.

Return a SINGLE valid JSON object and NOTHING ELSE (no prose, no code fences).
Inside string values, escape newlines as \\n. Use this exact schema:

{
  "verdict": "Buy" | "Hold" | "Avoid",
  "confidence": <integer 0-100>,
  "one_liner": "<one-sentence thesis>",
  "what_they_do": "<1-2 sentences on the business and how it makes money>",
  "revenue_segments": [ {"name": "<segment>", "pct": <number, share of revenue>} ],
  "trends": [ {"name": "<macro/sector trend, e.g. datacenter AI capex>",
               "impact": "positive" | "neutral" | "negative",
               "note": "<why / direction>"} ],
  "ai_positioning": {"stance": "tailwind" | "threat" | "neutral",
                     "note": "<concrete evidence>"},
  "earnings_reviews": [
    {
      "period": "<the fiscal quarter and report date, e.g. 'Q1 FY2026 (reported May 2026)'>",
      "segments": [ {"name": "<key business segment / sector, e.g. Data Center>",
                     "result": "<how that segment did this quarter, with the actual numbers>"} ],
      "promised": "<what management GUIDED or promised for this quarter back when they
                    reported the PRIOR quarter — the prior-period guidance, with numbers>",
      "delivered": "<what they actually reported for this quarter, with the actual numbers>",
      "verdict": "beat" | "met" | "missed",
      "note": "<one line: over- or under-delivered vs the prior guidance, and why>"
    }
  ],
  "analyst_note": "<latest targets & sentiment, verified from the web with a date>",
  "bull": ["<point>", "<point>", "<point>"],
  "bear": ["<point>", "<point>", "<point>"],
  "key_risks": ["<risk before next earnings>", "<risk>"],
  "detail_markdown": "<the FULL detailed analysis in Markdown, with sections for
      business & revenue, sector & themes, AI positioning, latest analyst targets
      (with sources/dates), bull vs bear, valuation read, and a verdict with risks.
      Be specific and use numbers. End with the line: Not financial advice.>"
}

Prefer sources from the last 3 months. The revenue_segments percentages should sum
to roughly 100. Keep arrays to 3-5 items.

For "earnings_reviews", web-search the company's LAST 2-3 quarterly earnings reports /
calls. For each, list the key business segments and how they did, then compare what
management PROMISED (the guidance they gave when reporting the prior quarter) against
what they actually DELIVERED, and judge beat / met / missed. Order most-recent first.

Output ONLY the JSON object.

--- RESEARCH BRIEF ---
"""


def claude_path() -> Optional[str]:
    for name in CLAUDE_BIN_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


def is_available() -> bool:
    return claude_path() is not None


def _extract_json(text: str) -> Optional[dict]:
    """Parse the agent's answer into a dict, tolerating fences / stray prose."""
    if not text:
        return None
    t = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    for candidate in (t, _largest_brace_block(t)):
        if not candidate:
            continue
        # strict=False tolerates literal newlines/tabs inside string values,
        # which strong models often emit despite the "escape newlines" hint.
        for kwargs in ({"strict": False}, {}):
            try:
                obj = json.loads(candidate, **kwargs)
                if isinstance(obj, dict):
                    return obj
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def _largest_brace_block(t: str) -> Optional[str]:
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start : end + 1]
    return None


def run_agent(
    brief: str,
    model: str = "sonnet",
    timeout: int = 480,
    web_research: bool = True,
) -> dict:
    """Invoke `claude -p` headlessly.

    Returns {structured: dict, text: str (detail markdown), cost_usd, duration_ms, num_turns}.
    """
    binary = claude_path()
    if not binary:
        raise AgentError(
            "`claude` CLI not found on PATH. Install Claude Code so the app can run "
            "the analysis on your subscription."
        )

    cmd = [
        binary,
        "-p",
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
        "--model",
        model,
    ]
    if web_research:
        cmd += ["--allowedTools", "WebSearch", "WebFetch"]
    else:
        cmd += ["--allowedTools", ""]  # knowledge-only, no tools

    prompt = ANALYSIS_INSTRUCTIONS + brief

    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise AgentError(f"Claude agent timed out after {timeout}s.")
    except FileNotFoundError:
        raise AgentError("Could not launch the `claude` binary.")

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise AgentError(f"claude exited with code {proc.returncode}: {msg[:500]}")

    out = (proc.stdout or "").strip()
    if not out:
        raise AgentError("Claude agent returned no output.")

    # claude --output-format json wraps the agent's answer in an envelope.
    cost = duration = turns = None
    answer = out
    try:
        env = json.loads(out)
        if isinstance(env, dict):
            if env.get("is_error"):
                raise AgentError(f"Agent reported an error: {str(env.get('result'))[:400]}")
            answer = env.get("result", out)
            cost = env.get("total_cost_usd")
            duration = env.get("duration_ms")
            turns = env.get("num_turns")
    except json.JSONDecodeError:
        pass

    structured = _extract_json(answer) or {}
    detail = structured.get("detail_markdown") or (answer if not structured else "")

    return {
        "structured": structured,
        "text": detail,
        "cost_usd": cost,
        "duration_ms": duration,
        "num_turns": turns,
    }
