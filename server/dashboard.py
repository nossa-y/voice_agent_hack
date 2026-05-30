#!/usr/bin/env python3
"""SyncFlow Sales Agent - Self-Improvement Dashboard.

Visual interface for the hackathon demo. Shows prompt evolution,
Cekura scores, diffs, and links to the live agent.

Run: uv run dashboard.py
Open: http://localhost:8501
"""

import difflib
import json
import os
import traceback
from datetime import date, datetime, timezone
from glob import glob

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

load_dotenv(override=True)

PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_versions")
TRANSCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcripts")
SCENARIO_IDS = [272894, 272893, 272892, 272891, 272890]
CEKURA_API_KEY = os.environ.get("CEKURA_API_KEY", "")

app = FastAPI(title="SyncFlow Dashboard")


# --- API Endpoints -----------------------------------------------------------

@app.get("/api/status")
async def get_status():
    versions = _load_all_versions()
    current = versions[-1] if versions else None
    return {
        "current_version": current["version"] if current else 0,
        "total_versions": len(versions),
        "versions_summary": [
            {
                "version": v["version"],
                "success_rate": (v.get("scores") or {}).get("success_rate"),
                "timestamp": v.get("timestamp"),
            }
            for v in versions
        ],
    }


@app.get("/api/versions")
async def get_versions():
    versions = _load_all_versions()
    return [
        {
            "version": v["version"],
            "timestamp": v.get("timestamp"),
            "changes": v.get("changes", ""),
            "scores": v.get("scores"),
            "prompt_length": len(v.get("system_instruction", "")),
        }
        for v in versions
    ]


@app.get("/api/diff")
async def get_diff():
    versions = _load_all_versions()
    if len(versions) < 2:
        return {"diff": "No previous version to compare.", "from_v": 0, "to_v": 0}
    prev = versions[-2]["system_instruction"]
    curr = versions[-1]["system_instruction"]
    diff_lines = list(difflib.unified_diff(
        prev.splitlines(), curr.splitlines(),
        fromfile=f"v{versions[-2]['version']}", tofile=f"v{versions[-1]['version']}",
        lineterm="",
    ))
    return {
        "diff": "\n".join(diff_lines),
        "from_v": versions[-2]["version"],
        "to_v": versions[-1]["version"],
    }


@app.get("/api/prompt/{version}")
async def get_prompt(version: int):
    filepath = os.path.join(PROMPT_DIR, f"v{version}.json")
    if not os.path.exists(filepath):
        return JSONResponse({"error": "Version not found"}, status_code=404)
    with open(filepath) as f:
        data = json.load(f)
    return data


@app.post("/api/improve")
async def run_improvement():
    """Run the full improvement loop: Cekura test -> Nemotron reflection -> save."""
    try:
        from cekura._client import Cekura
        from openai import OpenAI

        cekura = Cekura(api_key=CEKURA_API_KEY)

        # 1. Run Cekura tests
        run_result = cekura.scenarios.run_pipecat_v2(
            scenarios=[{"scenario": sid} for sid in SCENARIO_IDS],
        )
        result_id = run_result.get("id")

        # 2. Wait for completion
        final = cekura.results.wait(result_id, poll_interval=10, timeout=600)
        success_rate = final.get("success_rate", 0)

        # 3. Extract feedback
        feedback_lines = []
        runs = final.get("runs", {})
        if isinstance(runs, dict):
            for rid, rdata in runs.items():
                name = rdata.get("scenario", {}).get("name", "?")
                success = rdata.get("success", False)
                transcript = rdata.get("transcript_object", [])
                feedback_lines.append(f"SCENARIO: {name} | PASSED: {success}")
                if isinstance(transcript, list):
                    for t in transcript:
                        if isinstance(t, dict):
                            role = t.get("role", "?")
                            text = str(t.get("content", t.get("text", "")))[:200]
                            feedback_lines.append(f"  {role}: {text}")
                feedback_lines.append("")
        feedback = "\n".join(feedback_lines)

        # 4. Load current prompt
        current_prompt, current_version = _load_current()

        # 5. Nemotron self-reflection
        llm_client = OpenAI(
            api_key=os.getenv("NEMOTRON_LLM_API_KEY", "EMPTY"),
            base_url=os.environ["NEMOTRON_LLM_URL"],
        )
        analysis_prompt = (
            "You are a sales coaching expert. Analyze these test results and generate an improved prompt.\n\n"
            f"CURRENT PROMPT:\n---\n{current_prompt}\n---\n\n"
            f"TEST RESULTS (success rate: {success_rate}%):\n---\n{feedback}\n---\n\n"
            "Generate an improved prompt. Fix the failures. Keep what works.\n"
            "Rules: Under 2000 words. Start with 'You are Alex, a sales development rep at SyncFlow.'\n"
            f"Include today: {date.today().strftime('%A, %B %d, %Y')}.\n\n"
            "Output: CHANGES (3-5 bullets), then ===PROMPT===, then the full improved prompt."
        )
        response = llm_client.chat.completions.create(
            model=os.getenv("NEMOTRON_LLM_MODEL", "nvidia/nemotron-3-super"),
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.7,
            max_tokens=4096,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        result_text = response.choices[0].message.content

        if "===PROMPT===" in result_text:
            parts = result_text.split("===PROMPT===", 1)
            changes = parts[0].strip()
            improved_prompt = parts[1].strip()
        else:
            changes = "Full rewrite"
            improved_prompt = result_text.strip()

        # 6. Save new version
        new_version = current_version + 1
        data = {
            "version": new_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_instruction": improved_prompt,
            "changes": changes,
            "scores": {"success_rate": success_rate, "result_id": result_id},
        }
        os.makedirs(PROMPT_DIR, exist_ok=True)
        for fn in [f"v{new_version}.json", "current.json"]:
            with open(os.path.join(PROMPT_DIR, fn), "w") as f:
                json.dump(data, f, indent=2)

        return {
            "version": new_version,
            "success_rate": success_rate,
            "changes": changes,
            "status": "success",
        }

    except Exception as e:
        return JSONResponse(
            {"error": str(e), "traceback": traceback.format_exc()},
            status_code=500,
        )


# --- Helpers -----------------------------------------------------------------

def _load_all_versions():
    versions = []
    for f in sorted(glob(os.path.join(PROMPT_DIR, "v*.json"))):
        with open(f) as fh:
            versions.append(json.load(fh))
    return versions


def _load_current():
    current_file = os.path.join(PROMPT_DIR, "current.json")
    if os.path.exists(current_file):
        with open(current_file) as f:
            data = json.load(f)
        return data["system_instruction"], data["version"]
    return "", 0


# --- Dashboard HTML ----------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SyncFlow - Self-Improving Sales Agent</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { background: #0a0a0a; color: #e5e5e5; font-family: 'Inter', system-ui, sans-serif; }
  .card { background: #141414; border: 1px solid #262626; border-radius: 12px; }
  .bar { background: #22c55e; border-radius: 4px; height: 28px; transition: width 0.8s ease; }
  .bar-bg { background: #1a1a1a; border-radius: 4px; height: 28px; }
  .diff-add { color: #22c55e; background: rgba(34,197,94,0.1); }
  .diff-del { color: #ef4444; background: rgba(239,68,68,0.1); }
  .diff-header { color: #60a5fa; }
  .pulse { animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.5 } }
  .glow { box-shadow: 0 0 20px rgba(34,197,94,0.3); }
</style>
</head>
<body class="min-h-screen p-6">

<div class="max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex items-center justify-between mb-8">
    <div>
      <h1 class="text-3xl font-bold text-white">SyncFlow Sales Agent</h1>
      <p class="text-gray-400 mt-1">Self-improving AI SDR - Nemotron + Cekura + Pipecat</p>
    </div>
    <div class="flex gap-3">
      <a href="http://localhost:7860" target="_blank"
         class="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition">
        Try the Agent
      </a>
      <button onclick="runImprove()"
              id="improveBtn"
              class="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-white font-medium transition">
        Run Improvement Loop
      </button>
    </div>
  </div>

  <!-- Top Row: Score Timeline + Current Version -->
  <div class="grid grid-cols-2 gap-6 mb-6">
    <!-- Score Timeline -->
    <div class="card p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Improvement Timeline</h2>
      <div id="timeline" class="space-y-3">
        <p class="text-gray-500">Loading...</p>
      </div>
    </div>

    <!-- Current Version -->
    <div class="card p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Current Version</h2>
      <div id="currentVersion">
        <p class="text-gray-500">Loading...</p>
      </div>
    </div>
  </div>

  <!-- Bottom Row: Diff + Architecture -->
  <div class="grid grid-cols-2 gap-6">
    <!-- Prompt Diff -->
    <div class="card p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Prompt Evolution</h2>
      <div id="diffView" class="font-mono text-sm overflow-auto max-h-96">
        <p class="text-gray-500">Loading...</p>
      </div>
    </div>

    <!-- How it Works -->
    <div class="card p-6">
      <h2 class="text-lg font-semibold text-white mb-4">How It Works</h2>
      <div class="space-y-4 text-sm text-gray-300">
        <div class="flex items-start gap-3">
          <span class="text-green-400 font-bold text-lg">1</span>
          <div>
            <p class="text-white font-medium">Cekura runs 5 test scenarios</p>
            <p class="text-gray-400">Simulated prospects call the bot with different personas, objections, and edge cases</p>
          </div>
        </div>
        <div class="flex items-start gap-3">
          <span class="text-green-400 font-bold text-lg">2</span>
          <div>
            <p class="text-white font-medium">Transcripts + scores captured</p>
            <p class="text-gray-400">Each call is graded: did the bot qualify? handle objections? book a demo?</p>
          </div>
        </div>
        <div class="flex items-start gap-3">
          <span class="text-green-400 font-bold text-lg">3</span>
          <div>
            <p class="text-white font-medium">Nemotron self-reflects</p>
            <p class="text-gray-400">The same LLM analyzes its own failures and generates an improved system prompt</p>
          </div>
        </div>
        <div class="flex items-start gap-3">
          <span class="text-green-400 font-bold text-lg">4</span>
          <div>
            <p class="text-white font-medium">Prompt evolves, bot improves</p>
            <p class="text-gray-400">New prompt is saved. Next call uses it. Repeat until scores plateau.</p>
          </div>
        </div>
      </div>

      <div class="mt-6 p-4 bg-gray-900 rounded-lg">
        <p class="text-xs text-gray-400 uppercase tracking-wider mb-2">Tech Stack</p>
        <div class="flex flex-wrap gap-2">
          <span class="px-2 py-1 bg-green-900/50 text-green-400 rounded text-xs">NVIDIA Nemotron 3 Super 120B</span>
          <span class="px-2 py-1 bg-blue-900/50 text-blue-400 rounded text-xs">Pipecat Cloud</span>
          <span class="px-2 py-1 bg-purple-900/50 text-purple-400 rounded text-xs">Cekura Eval</span>
          <span class="px-2 py-1 bg-yellow-900/50 text-yellow-400 rounded text-xs">Gradium TTS</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Status Bar -->
  <div id="statusBar" class="mt-6 card p-4 text-center text-gray-400 text-sm hidden">
    <span id="statusText"></span>
  </div>
</div>

<script>
async function loadData() {
  try {
    const [versions, diff] = await Promise.all([
      fetch('/api/versions').then(r => r.json()),
      fetch('/api/diff').then(r => r.json()),
    ]);
    renderTimeline(versions);
    renderCurrentVersion(versions);
    renderDiff(diff);
  } catch (e) {
    console.error('Failed to load data:', e);
  }
}

function renderTimeline(versions) {
  const el = document.getElementById('timeline');
  if (!versions.length) {
    el.innerHTML = '<p class="text-gray-500">No versions yet. Run the improvement loop.</p>';
    return;
  }
  el.innerHTML = versions.map(v => {
    const rate = (v.scores && v.scores.success_rate) ?? (v.scores && v.scores.baseline_success_rate) ?? null;
    const pct = rate !== null ? rate : 0;
    const label = rate !== null ? pct + '%' : 'baseline';
    const barColor = pct >= 60 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500';
    return '<div class="flex items-center gap-3">' +
      '<span class="text-gray-400 w-8 text-right font-mono">v' + v.version + '</span>' +
      '<div class="bar-bg flex-1 relative">' +
        '<div class="' + barColor + ' rounded h-7 flex items-center px-2 text-xs font-bold text-white" style="width:' + Math.max(pct, 8) + '%">' + label + '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

function renderCurrentVersion(versions) {
  const el = document.getElementById('currentVersion');
  if (!versions.length) { el.innerHTML = '<p class="text-gray-500">No versions.</p>'; return; }
  const v = versions[versions.length - 1];
  const changes = (v.changes || '').replace(/^CHANGES:\n?/i, '');
  const bullets = changes.split('\n').filter(l => l.trim().startsWith('-')).map(l =>
    '<li class="text-gray-300">' + l.trim().substring(1).trim() + '</li>'
  ).join('');

  el.innerHTML =
    '<div class="flex items-center gap-2 mb-3">' +
      '<span class="text-2xl font-bold text-white">v' + v.version + '</span>' +
      '<span class="text-gray-500 text-sm">' + (v.timestamp || '').substring(0, 19) + '</span>' +
    '</div>' +
    '<p class="text-sm text-gray-400 mb-3">Prompt length: ' + v.prompt_length + ' chars</p>' +
    (bullets ? '<p class="text-sm text-gray-400 mb-2 font-medium">Changes:</p><ul class="list-disc pl-5 space-y-1 text-sm">' + bullets + '</ul>' : '') +
    (v.scores ? '<div class="mt-4 p-3 bg-gray-900 rounded-lg"><p class="text-xs text-gray-400">Score: <span class="text-white font-bold">' + JSON.stringify(v.scores) + '</span></p></div>' : '');
}

function renderDiff(data) {
  const el = document.getElementById('diffView');
  if (!data.diff || data.diff === 'No previous version to compare.') {
    el.innerHTML = '<p class="text-gray-500">No diff available yet. Run the improvement loop to see changes.</p>';
    return;
  }
  const lines = data.diff.split('\\n').map(line => {
    if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) {
      return '<div class="diff-header">' + escHtml(line) + '</div>';
    } else if (line.startsWith('+')) {
      return '<div class="diff-add">' + escHtml(line) + '</div>';
    } else if (line.startsWith('-')) {
      return '<div class="diff-del">' + escHtml(line) + '</div>';
    }
    return '<div>' + escHtml(line) + '</div>';
  }).join('');
  el.innerHTML = lines;
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function runImprove() {
  const btn = document.getElementById('improveBtn');
  const bar = document.getElementById('statusBar');
  const txt = document.getElementById('statusText');

  btn.disabled = true;
  btn.className = btn.className.replace('bg-green-600 hover:bg-green-500', 'bg-gray-600');
  btn.textContent = 'Running...';
  bar.classList.remove('hidden');
  txt.innerHTML = '<span class="pulse">Running 5 Cekura test scenarios + Nemotron self-reflection... (2-5 min)</span>';

  try {
    const res = await fetch('/api/improve', { method: 'POST' });
    const data = await res.json();
    if (data.error) {
      txt.innerHTML = '<span class="text-red-400">Error: ' + data.error + '</span>';
    } else {
      txt.innerHTML = '<span class="text-green-400">v' + data.version + ' created! Success rate: ' + data.success_rate + '%</span>';
      await loadData();
    }
  } catch (e) {
    txt.innerHTML = '<span class="text-red-400">Failed: ' + e.message + '</span>';
  }

  btn.disabled = false;
  btn.className = btn.className.replace('bg-gray-600', 'bg-green-600 hover:bg-green-500');
  btn.textContent = 'Run Improvement Loop';
}

// Load on page ready
loadData();
// Auto-refresh every 30s
setInterval(loadData, 30000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8501)
