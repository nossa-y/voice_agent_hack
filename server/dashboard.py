#!/usr/bin/env python3
"""ColdLoop Sales Agent - Self-Improvement Dashboard.

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

app = FastAPI(title="ColdLoop Dashboard")


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
        return {"diff": "", "from_v": 0, "to_v": 0}
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


@app.get("/api/scenarios")
async def get_scenarios():
    """Return the latest Cekura test results if available."""
    try:
        from cekura._client import Cekura
        cekura = Cekura(api_key=CEKURA_API_KEY)
        results = cekura.results.list(agent_id=18058, limit=1)
        if isinstance(results, dict):
            results = results.get("results", [])
        if not results:
            return {"scenarios": [], "result_id": None}

        latest = results[0] if isinstance(results[0], dict) else cekura.results.get(results[0])
        result_id = latest.get("id")
        full = cekura.results.get(result_id)

        scenarios = []
        runs = full.get("runs", {})
        if isinstance(runs, dict):
            for rid, rdata in runs.items():
                name = rdata.get("scenario", {}).get("name", "?")
                success = rdata.get("success", False)
                status = rdata.get("status", "unknown")
                transcript = rdata.get("transcript_object", [])
                turns = len(transcript) if isinstance(transcript, list) else 0

                # Get first few transcript turns for preview
                preview = []
                if isinstance(transcript, list):
                    for t in transcript[:6]:
                        if isinstance(t, dict):
                            preview.append({
                                "role": t.get("role", "?"),
                                "text": str(t.get("content", t.get("text", "")))[:150],
                            })

                scenarios.append({
                    "name": name,
                    "success": success,
                    "status": status,
                    "turns": turns,
                    "preview": preview,
                })

        return {"scenarios": scenarios, "result_id": result_id, "success_rate": full.get("success_rate", 0)}

    except Exception as e:
        return {"scenarios": [], "error": str(e)}


@app.post("/api/call-prospect")
async def call_prospect(request_data: dict = None):
    """Initiate an outbound Twilio call to a prospect, connected to the Pipecat bot."""
    try:
        from twilio.rest import Client

        account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        api_key_sid = os.environ["TWILIO_API_KEY_SID"]
        api_key_secret = os.environ["TWILIO_API_KEY_SECRET"]
        from_number = os.environ["TWILIO_PHONE_NUMBER"]

        # Default prospect number, can be overridden via request body
        to_number = "+1234567890"
        if request_data and request_data.get("to"):
            to_number = request_data["to"]

        client = Client(api_key_sid, api_key_secret, account_sid)

        # Route Twilio stream to local bot via ngrok
        # Pipecat Cloud's Twilio WS handler conflicts with our bot's parser,
        # so we route directly to the local bot's /ws endpoint
        bot_ws_url = os.environ.get("BOT_WS_URL", "")
        if not bot_ws_url:
            return JSONResponse(
                {"error": "BOT_WS_URL not set. Run: ngrok http 7860 and set BOT_WS_URL in .env"},
                status_code=400,
            )

        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            "<Connect>"
            f'<Stream url="{bot_ws_url}">'
            "</Stream>"
            "</Connect>"
            "</Response>"
        )

        call = client.calls.create(
            twiml=twiml,
            to=to_number,
            from_=from_number,
        )

        return {
            "status": "calling",
            "call_sid": call.sid,
            "to": to_number,
            "from": from_number,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/start-session")
async def start_session():
    """Start a Pipecat Cloud session and return Daily room URL for embedding."""
    import httpx
    try:
        pipecat_key = "pk_f3f0aa23-28ac-4b3b-88ca-9e7c57789c8d"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.pipecat.daily.co/v1/public/sales-bot/start",
                headers={
                    "Authorization": f"Bearer {pipecat_key}",
                    "Content-Type": "application/json",
                },
                json={"createDailyRoom": True},
                timeout=30,
            )
            data = resp.json()
        return {
            "room_url": data.get("dailyRoom"),
            "token": data.get("dailyToken"),
            "session_id": data.get("sessionId"),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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
        scenario_results = []
        if isinstance(runs, dict):
            for rid, rdata in runs.items():
                name = rdata.get("scenario", {}).get("name", "?")
                success = rdata.get("success", False)
                expected = rdata.get("scenario", {}).get("expected_outcome_prompt", "")
                transcript = rdata.get("transcript_object", [])
                turns = len(transcript) if isinstance(transcript, list) else 0
                scenario_results.append({"name": name, "success": success, "turns": turns})
                feedback_lines.append(f"SCENARIO: {name} | PASSED: {success}")
                feedback_lines.append(f"EXPECTED: {expected[:200]}")
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
            "Rules: Under 2000 words. Start with 'You are Alex, a sales development rep at ColdLoop.'\n"
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
            "scenarios": scenario_results,
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
<title>ColdLoop - Self-Improving Sales Agent</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>
tailwind.config = {
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] },
      colors: {
        surface: { 50: '#faf9f7', 100: '#f5f3f0', 200: '#ebe8e3', 300: '#d6d1ca' },
        ink: { DEFAULT: '#1a1a1a', light: '#4a4a4a', muted: '#7a7a7a' },
        accent: { DEFAULT: '#2563eb', dim: '#dbeafe' },
        success: { DEFAULT: '#16a34a', dim: '#dcfce7' },
        danger: { DEFAULT: '#dc2626', dim: '#fee2e2' },
      }
    }
  }
}
</script>
<style>
  * { box-sizing: border-box; }
  body { background: #faf9f7; color: #1a1a1a; font-family: 'Inter', system-ui, sans-serif; }
  .glass {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
  }
  .glass-sm { border-radius: 12px; }
  .score-bar { height: 32px; border-radius: 8px; transition: width 1s cubic-bezier(0.4, 0, 0.2, 1); }
  .score-bar-bg { background: #f0ede8; height: 32px; border-radius: 8px; }
  .diff-add { color: #16a34a; background: rgba(22,163,74,0.08); padding: 1px 4px; }
  .diff-del { color: #dc2626; background: rgba(220,38,38,0.06); padding: 1px 4px; text-decoration: line-through; text-decoration-color: rgba(220,38,38,0.3); }
  .diff-hunk { color: #2563eb; opacity: 0.7; }
  .diff-file { color: #7c3aed; font-weight: 600; }
  .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #16a34a; animation: pulse-dot 2s infinite; }
  @keyframes pulse-dot { 0%,100% { box-shadow: 0 0 0 0 rgba(22,163,74,0.4) } 50% { box-shadow: 0 0 0 6px rgba(22,163,74,0) } }
  .fade-in { animation: fadeIn 0.5s ease; }
  @keyframes fadeIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
  .btn-primary {
    background: #1a1a1a;
    color: white;
    transition: all 0.2s;
    box-shadow: 0 1px 4px rgba(0,0,0,0.12);
  }
  .btn-primary:hover { background: #333; box-shadow: 0 2px 8px rgba(0,0,0,0.2); transform: translateY(-1px); }
  .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none; }
  .btn-success {
    background: #16a34a;
    color: white;
    transition: all 0.2s;
    box-shadow: 0 1px 4px rgba(22,163,74,0.25);
  }
  .btn-success:hover { background: #15803d; box-shadow: 0 2px 8px rgba(22,163,74,0.4); transform: translateY(-1px); }
  .btn-success:disabled { opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none; }
  .tag { display: inline-flex; align-items: center; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; }
  .tag-pass { background: #dcfce7; color: #16a34a; border: 1px solid #bbf7d0; }
  .tag-fail { background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; }
  .tag-version { background: #dbeafe; color: #2563eb; border: 1px solid #bfdbfe; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.4); border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg) } }
  .transcript-preview { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
  .transcript-preview.open { max-height: 400px; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #d6d1ca; border-radius: 3px; }
</style>
</head>
<body class="min-h-screen">

<!-- Fixed Header -->
<header class="fixed top-0 left-0 right-0 z-50" style="background:rgba(250,249,247,0.85);backdrop-filter:blur(16px);border-bottom:1px solid rgba(0,0,0,0.06)">
  <div class="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="12" stroke="#1a1a1a" stroke-width="2"/><path d="M9 14l3 3 7-7" stroke="#1a1a1a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span class="text-lg font-bold text-ink tracking-tight">ColdLoop</span>
      </div>
      <span class="text-ink-muted text-sm hidden sm:inline">Self-Improving Sales Agent</span>
    </div>
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2 mr-2">
        <div class="pulse-dot"></div>
        <span class="text-xs text-ink-muted" id="headerVersion">Agent Live</span>
      </div>
      <button onclick="startCall()" id="callBtn" class="btn-primary px-4 py-2 rounded-xl text-sm font-medium">
        Try the Agent
      </button>
    </div>
  </div>
</header>

<main class="max-w-7xl mx-auto px-6 pt-20 pb-16">

  <!-- Hero -->
  <section class="mt-8 mb-12 fade-in">
    <h1 class="text-4xl sm:text-5xl font-extrabold text-ink leading-tight tracking-tight">
      An AI sales agent that rewrites<br>its own playbook.
    </h1>
    <p class="mt-4 text-lg text-ink-light max-w-2xl leading-relaxed">
      ColdLoop runs sales calls, evaluates performance with Cekura, reflects with Nemotron, and generates an improved prompt. Automatically. Watch it evolve.
    </p>
  </section>

  <!-- Metric Cards -->
  <section class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8 fade-in">
    <div class="glass p-6">
      <p class="text-xs text-ink-muted uppercase tracking-widest mb-1">Current Version</p>
      <p class="text-3xl font-bold text-ink" id="metricVersion">--</p>
      <p class="text-sm text-ink-light mt-1" id="metricVersionSub">Loading...</p>
    </div>
    <div class="glass p-6">
      <p class="text-xs text-ink-muted uppercase tracking-widest mb-1">Scenarios Passed</p>
      <p class="text-3xl font-bold text-ink" id="metricScore">--</p>
      <p class="text-sm text-ink-light mt-1" id="metricScoreSub">Loading...</p>
    </div>
    <div class="glass p-6">
      <p class="text-xs text-ink-muted uppercase tracking-widest mb-1">Prompt Rewrites</p>
      <p class="text-3xl font-bold text-ink" id="metricCycles">--</p>
      <p class="text-sm text-ink-light mt-1" id="metricCyclesSub">Loading...</p>
    </div>
  </section>

  <!-- 1. Talk to the Agent (TOP) -->
  <section class="glass p-6 mb-8">
    <h2 class="text-base font-semibold text-ink mb-4">Talk to the Agent</h2>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2">
        <div id="callArea">
          <p class="text-sm text-ink-light mb-5">Try the agent yourself via WebRTC, or have it call a real prospect's phone.</p>
          <div class="flex flex-wrap gap-3 mb-3">
            <button onclick="startCall()" id="callBtn2" class="btn-primary inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1a7 7 0 100 14A7 7 0 008 1z" stroke="currentColor" stroke-width="1.5"/><path d="M6.5 5l4 3-4 3V5z" fill="currentColor"/></svg>
              Try in Browser
            </button>
            <button onclick="callProspect()" id="callProspectBtn" class="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm text-white transition" style="background:linear-gradient(135deg,#16a34a,#15803d);box-shadow:0 2px 8px rgba(22,163,74,0.3)">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M14.5 11.1v1.9a1.3 1.3 0 01-1.4 1.3A12.8 12.8 0 011.7 2.9 1.3 1.3 0 013 1.5h1.9a1.3 1.3 0 011.3 1.1c.1.6.2 1.2.4 1.8a1.3 1.3 0 01-.3 1.3l-.8.8a10.2 10.2 0 004.5 4.5l.8-.8a1.3 1.3 0 011.3-.3c.6.2 1.2.3 1.8.4a1.3 1.3 0 011.1 1.3z" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <span id="callProspectText">Call Prospect</span>
            </button>
          </div>
          <div id="phoneInput" class="flex gap-2 items-center mb-3">
            <input type="tel" id="prospectPhone" value="+1234567890" placeholder="+1234567890" class="px-3 py-2 rounded-lg text-sm border border-surface-300 bg-surface-100 text-ink w-48 focus:outline-none focus:border-blue-500">
            <span class="text-xs text-ink-muted">Prospect's phone number</span>
          </div>
          <p id="callStatus" class="text-xs text-ink-muted mt-3 hidden"></p>
        </div>
        <div id="callEmbed" class="hidden">
          <iframe id="callFrame" allow="microphone; camera; autoplay;" style="width:100%; height:400px; border:none; border-radius:12px; background:#000;"></iframe>
          <button onclick="endCall()" class="mt-3 px-4 py-2 rounded-lg text-xs font-medium bg-red-600 hover:bg-red-500 text-white transition">
            End Call
          </button>
        </div>
      </div>
      <div>
        <p class="text-xs text-ink-muted uppercase tracking-widest mb-3">Today's Call List</p>
        <div class="space-y-2">
          <div class="p-3 rounded-xl bg-surface-100 border border-surface-300/50">
            <p class="text-xs font-semibold text-ink">Jake Morrison</p>
            <p class="text-xs text-ink-muted">VP Sales Ops, Packsmith</p>
          </div>
          <div class="p-3 rounded-xl bg-surface-100 border border-surface-300/50">
            <p class="text-xs font-semibold text-ink">Lisa Tran</p>
            <p class="text-xs text-ink-muted">Head of Data, Ridgewell</p>
          </div>
          <div class="p-3 rounded-xl bg-surface-100 border border-surface-300/50">
            <p class="text-xs font-semibold text-ink">Dan Cooper</p>
            <p class="text-xs text-ink-muted">Dir RevOps, Folio Systems</p>
          </div>
          <div class="p-3 rounded-xl bg-surface-100 border border-surface-300/50">
            <p class="text-xs font-semibold text-ink">Maria Santos</p>
            <p class="text-xs text-ink-muted">Ops Lead, Trellus</p>
          </div>
        </div>
      </div>
    </div>
    <div id="statusBar" class="mt-4 p-4 rounded-xl bg-surface-100 text-center text-sm text-ink-light hidden">
      <span id="statusText"></span>
    </div>
  </section>

  <!-- 2. Cekura Test Results -->
  <section class="glass p-6 mb-8">
    <div class="flex items-center justify-between mb-5">
      <h2 class="text-base font-semibold text-ink flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 3h12M2 8h12M2 13h12" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/></svg>
        Cekura Test Results
      </h2>
      <button onclick="runImprove()" id="improveBtn" class="btn-success px-4 py-2 rounded-xl font-semibold text-sm flex items-center gap-2">
        <span id="improveBtnText">Run Improvement</span>
        <span id="improveBtnSpinner" class="spinner hidden"></span>
      </button>
    </div>
    <div id="scenarios">
      <p class="text-ink-muted text-sm">Loading scenarios...</p>
    </div>
  </section>

  <!-- 3. Prompt Diff -->
  <section class="glass p-6 mb-8">
    <h2 class="text-base font-semibold text-ink mb-4 flex items-center gap-2">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="1" width="14" height="14" rx="3" stroke="#a78bfa" stroke-width="1.5"/><path d="M5 5h6M5 8h4M5 11h5" stroke="#a78bfa" stroke-width="1.5" stroke-linecap="round"/></svg>
      Prompt Diff
    </h2>
    <div id="diffView" class="font-mono text-xs leading-relaxed overflow-auto max-h-80 p-4 rounded-xl bg-surface-200">
      <p class="text-ink-muted">Loading...</p>
    </div>
  </section>

  <!-- 4. Evolution History + Latest Changes -->
  <section class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
    <div class="glass p-6">
      <h2 class="text-base font-semibold text-ink mb-5 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 14V2m0 12h12M5 11l3-4 3 2 3-5" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Evolution History
      </h2>
      <div id="timeline" class="space-y-3">
        <p class="text-ink-muted text-sm">Loading...</p>
      </div>
    </div>
    <div class="glass p-6">
      <h2 class="text-base font-semibold text-ink mb-5 flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1v14M1 8h14" stroke="#22c55e" stroke-width="1.5" stroke-linecap="round"/></svg>
        Latest Changes
      </h2>
      <div id="currentVersion">
        <p class="text-ink-muted text-sm">Loading...</p>
      </div>
    </div>
  </section>

  <!-- How the Loop Works + Tech Stack -->
  <section class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
    <div class="glass p-6">
      <h2 class="text-base font-semibold text-ink mb-5">How the Loop Works</h2>
      <div class="space-y-5">
        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center shrink-0">
            <span class="text-blue-600 text-sm font-bold">1</span>
          </div>
          <div>
            <p class="text-sm font-medium text-ink">Agent makes calls</p>
            <p class="text-xs text-ink-muted">Nemotron 3 Super 120B powers conversation via Pipecat</p>
          </div>
        </div>
        <div class="w-px h-4 bg-surface-300 ml-4"></div>
        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center shrink-0">
            <span class="text-amber-600 text-sm font-bold">2</span>
          </div>
          <div>
            <p class="text-sm font-medium text-ink">Cekura evaluates</p>
            <p class="text-xs text-ink-muted">5 automated test scenarios with pass/fail scoring</p>
          </div>
        </div>
        <div class="w-px h-4 bg-surface-300 ml-4"></div>
        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-lg bg-purple-50 border border-purple-200 flex items-center justify-center shrink-0">
            <span class="text-purple-600 text-sm font-bold">3</span>
          </div>
          <div>
            <p class="text-sm font-medium text-ink">Nemotron reflects</p>
            <p class="text-xs text-ink-muted">Analyzes its own failures, identifies what to fix</p>
          </div>
        </div>
        <div class="w-px h-4 bg-surface-300 ml-4"></div>
        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-lg bg-green-50 border border-green-200 flex items-center justify-center shrink-0">
            <span class="text-green-600 text-sm font-bold">4</span>
          </div>
          <div>
            <p class="text-sm font-medium text-ink">Prompt evolves</p>
            <p class="text-xs text-ink-muted">New system prompt saved. Next calls use it. Repeat.</p>
          </div>
        </div>
      </div>

      <div class="mt-6 p-4 rounded-xl bg-surface-200">
        <p class="text-[10px] text-ink-muted uppercase tracking-widest mb-3">Tech Stack</p>
        <div class="flex flex-wrap gap-2">
          <span class="tag" style="background:#dcfce7;color:#16a34a;border:1px solid #bbf7d0">NVIDIA Nemotron 120B</span>
          <span class="tag" style="background:#dbeafe;color:#2563eb;border:1px solid #bfdbfe">Pipecat Cloud</span>
          <span class="tag" style="background:#f3e8ff;color:#7c3aed;border:1px solid #e9d5ff">Cekura Eval</span>
          <span class="tag" style="background:#fef3c7;color:#d97706;border:1px solid #fde68a">Gradium TTS</span>
        </div>
      </div>
    </div>
  </section>

</main>

<!-- Footer -->
<footer class="border-t border-surface-300/50 py-6">
  <div class="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between text-xs text-ink-muted gap-2">
    <span>Built at YC Voice Agents Hackathon - Pipecat + Cekura + NVIDIA Nemotron</span>
    <span>by ColdLoop team</span>
  </div>
</footer>

<script>
const ESC = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

async function loadData() {
  try {
    const [versions, diff, scenarios] = await Promise.all([
      fetch('/api/versions').then(r => r.json()),
      fetch('/api/diff').then(r => r.json()),
      fetch('/api/scenarios').then(r => r.json()).catch(() => ({scenarios:[]})),
    ]);
    renderMetrics(versions);
    renderTimeline(versions);
    renderCurrentVersion(versions);
    renderDiff(diff);
    renderScenarios(scenarios);
  } catch (e) { console.error('Load failed:', e); }
}

function renderMetrics(versions) {
  if (!versions.length) return;
  const curr = versions[versions.length - 1];
  const rate = (curr.scores||{}).success_rate ?? (curr.scores||{}).baseline_success_rate ?? null;

  document.getElementById('metricVersion').textContent = 'v' + curr.version;
  document.getElementById('metricVersionSub').textContent = 'Prompt evolved ' + curr.version + ' time' + (curr.version !== 1 ? 's' : '');
  document.getElementById('headerVersion').textContent = 'v' + curr.version + ' Live';

  const passed = rate !== null ? Math.round(rate / 20) : 0;
  document.getElementById('metricScore').textContent = rate !== null ? passed + '/5' : '--';
  document.getElementById('metricScoreSub').textContent = rate !== null ? passed + ' of 5 Cekura scenarios passed' : 'No score yet';

  document.getElementById('metricCycles').textContent = versions.length - 1;
  document.getElementById('metricCyclesSub').textContent = versions.length <= 1 ? 'Run your first cycle' : (versions.length - 1) + ' prompt rewrites by Nemotron';
}

function renderTimeline(versions) {
  const el = document.getElementById('timeline');
  if (!versions.length) { el.innerHTML = '<p class="text-ink-muted text-sm">No versions yet.</p>'; return; }
  el.innerHTML = versions.map(v => {
    const rate = (v.scores||{}).success_rate ?? (v.scores||{}).baseline_success_rate ?? 0;
    const pct = rate || 0;
    const color = pct >= 60 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-400';
    const label = rate !== null && rate !== undefined ? pct + '%' : 'base';
    return `<div class="flex items-center gap-3">
      <span class="tag-version tag w-12 justify-center font-mono">v${v.version}</span>
      <div class="score-bar-bg flex-1 relative">
        <div class="${color} score-bar flex items-center px-3" style="width:${Math.max(pct, 6)}%">
          <span class="text-xs font-bold text-ink whitespace-nowrap">${label}</span>
        </div>
      </div>
      <span class="text-xs text-ink-muted w-16 text-right">${(v.timestamp||'').substring(11,16)||''}</span>
    </div>`;
  }).join('');
}

function renderCurrentVersion(versions) {
  const el = document.getElementById('currentVersion');
  if (!versions.length) { el.innerHTML = '<p class="text-ink-muted text-sm">No versions.</p>'; return; }
  const v = versions[versions.length - 1];
  const changes = (v.changes || '').replace(/^CHANGES:?\\n?/i, '');
  const bullets = changes.split('\\n').filter(l => l.trim().startsWith('-')).map(l =>
    `<li class="text-sm text-ink leading-relaxed">${ESC(l.trim().substring(1).trim())}</li>`
  ).join('');

  el.innerHTML = `
    <div class="flex items-baseline gap-3 mb-4">
      <span class="text-2xl font-bold text-ink">v${v.version}</span>
      <span class="text-xs text-ink-muted">${(v.timestamp||'').substring(0,16).replace('T',' ')}</span>
      <span class="text-xs text-ink-muted">${v.prompt_length} chars</span>
    </div>
    ${bullets ? `<ul class="space-y-2 list-none">${bullets.replace(/<li/g, '<li class="flex items-start gap-2 text-sm text-ink"><span class="text-green-600 mt-1 shrink-0">+</span><span')}</ul>` : '<p class="text-ink-muted text-sm">Initial version</p>'}
  `;
}

function renderDiff(data) {
  const el = document.getElementById('diffView');
  if (!data.diff) {
    el.innerHTML = '<p class="text-ink-muted text-sm">No diff available yet. Run an improvement cycle to see prompt changes.</p>';
    return;
  }
  el.innerHTML = data.diff.split('\\n').map(line => {
    if (line.startsWith('+++') || line.startsWith('---')) return `<div class="diff-file">${ESC(line)}</div>`;
    if (line.startsWith('@@')) return `<div class="diff-hunk">${ESC(line)}</div>`;
    if (line.startsWith('+')) return `<div class="diff-add">+ ${ESC(line.substring(1))}</div>`;
    if (line.startsWith('-')) return `<div class="diff-del">- ${ESC(line.substring(1))}</div>`;
    return `<div class="text-ink-muted">${ESC(line)}</div>`;
  }).join('');
}

function renderScenarios(data) {
  const el = document.getElementById('scenarios');
  const scenarios = data.scenarios || [];
  if (!scenarios.length) {
    el.innerHTML = '<p class="text-ink-muted text-sm">No test results yet. Run an improvement cycle to see scenario outcomes.</p>';
    return;
  }

  el.innerHTML = `
    <div class="space-y-3">
      ${scenarios.map((s, i) => `
        <div class="p-4 rounded-xl bg-surface-100 border border-surface-300/30">
          <div class="flex items-center justify-between cursor-pointer" onclick="toggleTranscript(${i})">
            <div class="flex items-center gap-3">
              <span class="${s.success ? 'tag-pass' : 'tag-fail'} tag">${s.success ? 'PASS' : 'FAIL'}</span>
              <span class="text-sm text-ink font-medium">${ESC(s.name)}</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-xs text-ink-muted">${s.turns} turns</span>
              <svg class="w-4 h-4 text-ink-muted transition-transform" id="chevron-${i}" viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>
            </div>
          </div>
          <div class="transcript-preview mt-3 pl-4 border-l border-surface-300" id="transcript-${i}">
            ${(s.preview||[]).map(t => `
              <div class="py-1">
                <span class="text-xs font-medium ${t.role === 'Main Agent' ? 'text-blue-600' : 'text-ink-muted'}">${ESC(t.role)}:</span>
                <span class="text-xs text-ink-light ml-1">${ESC(t.text)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function toggleTranscript(i) {
  const el = document.getElementById('transcript-' + i);
  const chevron = document.getElementById('chevron-' + i);
  el.classList.toggle('open');
  chevron.style.transform = el.classList.contains('open') ? 'rotate(180deg)' : '';
}

async function runImprove() {
  const btn = document.getElementById('improveBtn');
  const btnText = document.getElementById('improveBtnText');
  const btnSpinner = document.getElementById('improveBtnSpinner');
  const bar = document.getElementById('statusBar');
  const txt = document.getElementById('statusText');

  btn.disabled = true;
  btnText.textContent = 'Running...';
  btnSpinner.classList.remove('hidden');
  bar.classList.remove('hidden');
  txt.innerHTML = 'Running 5 Cekura test scenarios + Nemotron self-reflection... <span class="text-ink-muted">(2-5 min)</span>';

  try {
    const res = await fetch('/api/improve', { method: 'POST' });
    const data = await res.json();
    if (data.error) {
      txt.innerHTML = '<span class="text-red-400">Error: ' + ESC(data.error) + '</span>';
    } else {
      txt.innerHTML = '<span class="text-green-600">v' + data.version + ' created. Score: ' + data.success_rate + '%</span>';
      await loadData();
    }
  } catch (e) {
    txt.innerHTML = '<span class="text-red-400">Failed: ' + ESC(e.message) + '</span>';
  }

  btn.disabled = false;
  btnText.textContent = 'Run Improvement';
  btnSpinner.classList.add('hidden');
}

loadData();
setInterval(loadData, 30000);

async function startCall() {
  const btn = document.getElementById('callBtn');
  const btn2 = document.getElementById('callBtn2');
  const status = document.getElementById('callStatus');
  const area = document.getElementById('callArea');
  const embed = document.getElementById('callEmbed');
  const frame = document.getElementById('callFrame');

  if (btn) { btn.disabled = true; btn.textContent = 'Connecting...'; }
  if (btn2) { btn2.disabled = true; btn2.textContent = 'Connecting...'; }
  if (status) { status.classList.remove('hidden'); status.textContent = 'Starting session...'; }

  try {
    const res = await fetch('/api/start-session', { method: 'POST' });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    // Embed Daily prebuilt UI
    const roomUrl = data.room_url;
    const token = data.token;
    frame.src = roomUrl + '?t=' + token + '&prejoin=false';
    area.querySelector('p').classList.add('hidden');
    if (btn2) btn2.classList.add('hidden');
    embed.classList.remove('hidden');
    if (status) { status.classList.remove('hidden'); status.textContent = 'Connected - speak to the agent!'; }
  } catch (e) {
    if (status) { status.classList.remove('hidden'); status.innerHTML = '<span class="text-red-400">Failed: ' + e.message + '</span>'; }
  }
  if (btn) { btn.disabled = false; btn.textContent = 'Try the Agent'; }
  if (btn2) { btn2.disabled = false; btn2.textContent = 'Start Call'; }
}

function endCall() {
  const frame = document.getElementById('callFrame');
  const embed = document.getElementById('callEmbed');
  const area = document.getElementById('callArea');
  const btn2 = document.getElementById('callBtn2');
  const status = document.getElementById('callStatus');

  frame.src = '';
  embed.classList.add('hidden');
  if (btn2) btn2.classList.remove('hidden');
  area.querySelector('p').classList.remove('hidden');
  if (status) { status.classList.remove('hidden'); status.textContent = 'Call ended. Starting improvement cycle...'; }

  // Auto-trigger improvement loop after call ends
  setTimeout(() => runImprove(), 1500);
}

async function callProspect() {
  const btn = document.getElementById('callProspectBtn');
  const btnText = document.getElementById('callProspectText');
  const status = document.getElementById('callStatus');
  const phone = document.getElementById('prospectPhone').value.trim();

  if (!phone) { alert('Enter a phone number'); return; }

  btn.disabled = true;
  btnText.textContent = 'Calling...';
  if (status) { status.classList.remove('hidden'); status.textContent = 'Dialing ' + phone + '...'; }

  try {
    const res = await fetch('/api/call-prospect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({to: phone}),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    if (status) {
      status.classList.remove('hidden');
      status.innerHTML = '<span class="text-green-600">Call initiated! SID: ' + data.call_sid + '</span><br><span class="text-ink-muted">The agent is now talking to ' + phone + '</span>';
    }
  } catch (e) {
    if (status) { status.classList.remove('hidden'); status.innerHTML = '<span class="text-red-500">Failed: ' + ESC(e.message) + '</span>'; }
  }

  btn.disabled = false;
  btnText.textContent = 'Call Prospect';
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8501)
