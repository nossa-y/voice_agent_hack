#!/usr/bin/env python3
"""Self-improvement loop for the Getcleed sales agent.

Reads call transcripts, analyzes performance via Cekura evaluations and
Nemotron self-reflection, then generates an improved system prompt.

Usage:
    # Improve based on local transcripts only (no Cekura):
    uv run improve.py --local

    # Full loop: run Cekura tests, get scores, improve:
    uv run improve.py --cekura

    # Just show current prompt version and stats:
    uv run improve.py --status
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from glob import glob
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_versions")
TRANSCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcripts")


# ---------------------------------------------------------------------------
# Prompt version management
# ---------------------------------------------------------------------------

def load_current_prompt() -> tuple[str | None, int]:
    """Load the current system prompt and version number."""
    current_file = os.path.join(PROMPT_DIR, "current.json")
    if os.path.exists(current_file):
        with open(current_file) as f:
            data = json.load(f)
        return data["system_instruction"], data["version"]
    return None, 0


def save_new_prompt(
    system_instruction: str,
    version: int,
    changes: str,
    scores: dict | None = None,
) -> str:
    """Save a new prompt version and update current.json."""
    os.makedirs(PROMPT_DIR, exist_ok=True)
    data = {
        "version": version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system_instruction": system_instruction,
        "changes": changes,
        "scores": scores,
    }
    # Save versioned copy
    version_file = os.path.join(PROMPT_DIR, f"v{version}.json")
    with open(version_file, "w") as f:
        json.dump(data, f, indent=2)
    # Update current pointer
    current_file = os.path.join(PROMPT_DIR, "current.json")
    with open(current_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved prompt v{version} -> {version_file}")
    return version_file


def get_prompt_history() -> list[dict]:
    """Load all prompt versions in order."""
    versions = []
    for f in sorted(glob(os.path.join(PROMPT_DIR, "v*.json"))):
        with open(f) as fh:
            versions.append(json.load(fh))
    return versions


# ---------------------------------------------------------------------------
# Transcript management
# ---------------------------------------------------------------------------

def load_recent_transcripts(limit: int = 5, version: int | None = None) -> list[dict]:
    """Load the most recent transcripts, optionally filtered by prompt version."""
    files = sorted(glob(os.path.join(TRANSCRIPT_DIR, "call-*.json")), reverse=True)
    transcripts = []
    for f in files:
        with open(f) as fh:
            t = json.load(fh)
        if version is not None and t.get("prompt_version") != version:
            continue
        transcripts.append(t)
        if len(transcripts) >= limit:
            break
    return transcripts


def format_transcript_for_analysis(transcript: dict) -> str:
    """Format a transcript into a readable string for LLM analysis."""
    lines = []
    lines.append(f"Prospect: {transcript['prospect']['name']} "
                 f"({transcript['prospect']['title']} at {transcript['prospect']['company']})")
    lines.append(f"Demo scheduled: {transcript.get('demo_scheduled', False)}")
    lines.append(f"Objections: {transcript.get('objections_raised', [])}")
    lines.append("")
    for msg in transcript.get("messages", []):
        role = msg.get("role", "?").upper()
        content = msg.get("content", "")
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Nemotron self-reflection (works without Cekura)
# ---------------------------------------------------------------------------

def reflect_with_nemotron(
    current_prompt: str,
    transcripts: list[dict],
    cekura_feedback: str | None = None,
) -> tuple[str, str]:
    """Use Nemotron to analyze transcripts and generate an improved prompt.

    Args:
        current_prompt: The current system instruction.
        transcripts: List of recent call transcripts.
        cekura_feedback: Optional evaluation feedback from Cekura.

    Returns:
        (improved_prompt, changes_description)
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("NEMOTRON_LLM_API_KEY", "EMPTY"),
        base_url=os.environ["NEMOTRON_LLM_URL"],
    )

    # Build the analysis prompt
    transcript_text = "\n\n---\n\n".join(
        format_transcript_for_analysis(t) for t in transcripts
    )

    feedback_section = ""
    if cekura_feedback:
        feedback_section = f"\n\nEVALUATION FEEDBACK FROM CEKURA:\n{cekura_feedback}\n"

    analysis_prompt = f"""You are a sales coaching expert analyzing an AI sales agent's performance.

CURRENT SYSTEM PROMPT (the instructions the agent follows):
---
{current_prompt}
---

RECENT CALL TRANSCRIPTS:
---
{transcript_text}
---
{feedback_section}
YOUR TASK:
1. Analyze what the agent did well and poorly across these calls.
2. Identify specific patterns: Did it ask discovery questions before pitching?
   Did it handle objections naturally? Did it personalize the opener?
   Was it too pushy or too passive? Did it talk too much per turn?
3. Generate an IMPROVED version of the system prompt that fixes the weaknesses
   while keeping the strengths.

RULES FOR THE IMPROVED PROMPT:
- Keep the same overall structure (sales flow, conversation rules).
- Add specific guidance for issues you found (e.g., "When the prospect says X,
  respond with Y instead of Z").
- Remove or soften rules that caused problems.
- Keep it under 2000 words. Concise prompts perform better.
- Include today's date: {date.today().strftime('%A, %B %d, %Y')}.
- The prompt must start with "You are Alex, a sales development rep at Getcleed."
- Do NOT include any meta-commentary or explanation. ONLY output the improved prompt.

OUTPUT FORMAT:
First, output a brief CHANGES section (3-5 bullet points of what you changed and why),
then a separator line "===PROMPT===", then the full improved system prompt.

Example:
CHANGES:
- Added guidance to wait for prospect to finish speaking before pitching
- Softened the opener to be less aggressive
- Added fallback for when prospect mentions unknown competitors
===PROMPT===
You are Alex, a sales development rep at Getcleed...
"""

    print("Calling Nemotron for self-reflection...")
    response = client.chat.completions.create(
        model=os.getenv("NEMOTRON_LLM_MODEL", "nvidia/nemotron-3-super"),
        messages=[{"role": "user", "content": analysis_prompt}],
        temperature=0.7,
        max_tokens=4096,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

    result = response.choices[0].message.content

    # Parse the response
    if "===PROMPT===" in result:
        parts = result.split("===PROMPT===", 1)
        changes = parts[0].strip()
        improved_prompt = parts[1].strip()
    else:
        # Fallback: treat entire response as the prompt
        changes = "Changes not parsed separately"
        improved_prompt = result.strip()

    return improved_prompt, changes


# ---------------------------------------------------------------------------
# Cekura integration
# ---------------------------------------------------------------------------

def setup_cekura_agent(client, project_id: int, agent_name: str, pipecat_bot_url: str) -> int:
    """Create or find the Cekura agent for our sales bot.

    Returns the agent ID.
    """
    # Check if agent already exists
    agents_resp = client.agents.list(project_id=project_id)
    agents = agents_resp.get("results", []) if isinstance(agents_resp, dict) else []
    for a in agents:
        if isinstance(a, dict) and a.get("agent_name") == agent_name:
            print(f"Found existing agent: id={a['id']} name={a['agent_name']}")
            return a["id"]

    # Create new agent
    result = client.agents.create(
        agent_name=agent_name,
        description=(
            "Getcleed outbound sales agent. Makes cold calls to prospects, "
            "qualifies their data pipeline needs, handles objections, and books demos."
        ),
        project=project_id,
        inbound=True,  # Cekura calls our bot (inbound from bot's perspective)
        assistant_provider="pipecat",
        assistant_id=pipecat_bot_url,
    )
    agent_id = result.get("id")
    print(f"Created Cekura agent: id={agent_id}")
    return agent_id


def generate_sales_scenarios(client, agent_id: int, project_id: int) -> list[int]:
    """Generate test scenarios for the sales agent.

    Returns list of scenario IDs.
    """
    # Check for existing scenarios
    existing = client.scenarios.list(agent_id=agent_id, project_id=project_id)
    if isinstance(existing, dict):
        existing = existing.get("results", [])
    if existing:
        ids = [s["id"] for s in existing if isinstance(s, dict)]
        print(f"Found {len(ids)} existing scenarios")
        return ids

    # Generate scenarios using Cekura's AI
    print("Generating test scenarios...")
    result = client.scenarios.generate(
        agent_id=agent_id,
        project_id=project_id,
        count=10,
    )

    # Poll for completion if async
    if "task_id" in result:
        print("Waiting for scenario generation...")
        for _ in range(60):
            progress = client.scenarios.generate_progress(task_id=result["task_id"])
            if progress.get("status") in ("completed", "done"):
                break
            time.sleep(2)

    # Fetch generated scenarios
    scenarios = client.scenarios.list(agent_id=agent_id, project_id=project_id)
    if isinstance(scenarios, dict):
        scenarios = scenarios.get("results", [])
    ids = [s["id"] for s in scenarios if isinstance(s, dict)]
    print(f"Generated {len(ids)} scenarios")
    return ids


def run_cekura_tests(client, agent_id: int, scenario_ids: list[int]) -> dict:
    """Run Cekura test scenarios against the Pipecat bot.

    Returns the result object with scores and transcripts.
    """
    print(f"Running {len(scenario_ids)} test scenarios...")
    result = client.scenarios.run_pipecat(
        agent_id=agent_id,
        scenario_ids=scenario_ids,
    )

    result_id = result.get("id") or result.get("result_id")
    if not result_id:
        print(f"Warning: No result ID in response: {result}")
        return result

    print(f"Test run started: result_id={result_id}")
    print("Waiting for completion (this may take a few minutes)...")

    # Wait for results
    final = client.results.wait(result_id, poll_interval=10, timeout=600)
    print(f"Test run completed: status={final.get('status')}")
    return final


def extract_cekura_feedback(client, result: dict) -> str:
    """Extract actionable feedback from Cekura test results.

    Returns a formatted string of feedback for the improvement prompt.
    """
    lines = []
    runs = result.get("runs", [])
    if not runs:
        # Try to get runs from the result ID
        result_id = result.get("id")
        if result_id:
            full_result = client.results.get(result_id)
            runs = full_result.get("runs", [])

    for run_data in runs:
        run_id = run_data.get("id") if isinstance(run_data, dict) else run_data
        try:
            run = client.runs.get(run_id)
            scenario_name = run.get("scenario_name", run.get("scenario", {}).get("name", f"Scenario {run_id}"))
            status = run.get("status", "unknown")
            lines.append(f"\nScenario: {scenario_name} (status: {status})")

            # Extract metrics/scores
            metrics = run.get("metrics", run.get("metric_results", []))
            if metrics:
                for m in metrics:
                    if isinstance(m, dict):
                        name = m.get("metric_name", m.get("name", "unnamed"))
                        score = m.get("score", m.get("value", "N/A"))
                        reason = m.get("reason", m.get("explanation", ""))
                        lines.append(f"  - {name}: {score} {('-- ' + reason) if reason else ''}")

            # Extract transcript
            transcript = run.get("transcript", [])
            if transcript:
                lines.append("  Transcript excerpt:")
                for entry in transcript[:10]:
                    if isinstance(entry, dict):
                        role = entry.get("role", "?")
                        text = entry.get("content", entry.get("text", ""))
                        if text:
                            lines.append(f"    {role}: {text[:100]}")

        except Exception as e:
            lines.append(f"  (failed to load run {run_id}: {e})")

    return "\n".join(lines) if lines else "No detailed feedback available."


# ---------------------------------------------------------------------------
# Main improvement loop
# ---------------------------------------------------------------------------

def run_local_improvement():
    """Improve the prompt using local transcripts only (no Cekura)."""
    current_prompt, current_version = load_current_prompt()
    if not current_prompt:
        # bot-sales.py has a hyphen so we use importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bot_sales", os.path.join(os.path.dirname(__file__), "bot-sales.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        current_prompt = mod.build_default_system_instruction()

    transcripts = load_recent_transcripts(limit=5)
    if not transcripts:
        print("No transcripts found. Make some test calls first, then run this again.")
        sys.exit(1)

    print(f"Current prompt version: v{current_version}")
    print(f"Analyzing {len(transcripts)} recent transcripts...")

    improved_prompt, changes = reflect_with_nemotron(current_prompt, transcripts)

    new_version = current_version + 1
    print(f"\n{'='*60}")
    print(f"CHANGES (v{current_version} -> v{new_version}):")
    print(changes)
    print(f"{'='*60}\n")

    save_new_prompt(improved_prompt, new_version, changes)
    print(f"\nDone. Next call will use prompt v{new_version}.")
    print("Run more test calls, then run this again to keep improving.")


def run_cekura_improvement():
    """Full improvement loop using Cekura test evaluation."""
    from cekura._client import Cekura

    api_key = os.environ.get("CEKURA_API_KEY")
    if not api_key:
        print("Error: CEKURA_API_KEY not set in .env")
        sys.exit(1)

    client = Cekura(api_key=api_key)

    # Get or create project
    projects = client.projects.list()
    if isinstance(projects, dict):
        projects = projects.get("results", [])
    if not projects:
        project = client.projects.create(name="Getcleed Sales Agent")
        project_id = project["id"]
    else:
        project_id = projects[0]["id"] if isinstance(projects[0], dict) else projects[0]
    print(f"Using project: {project_id}")

    # Setup agent
    pipecat_bot_url = os.environ.get("PIPECAT_BOT_URL", "sales-bot")
    agent_id = setup_cekura_agent(client, project_id, "Getcleed Sales Bot", pipecat_bot_url)

    # Generate or load scenarios
    scenario_ids = generate_sales_scenarios(client, agent_id, project_id)
    if not scenario_ids:
        print("No scenarios available. Creating manually...")
        # Create a few basic scenarios manually
        for persona in ["skeptical buyer", "interested but busy", "price-sensitive"]:
            result = client.scenarios.create(
                agent_id=agent_id,
                project_id=project_id,
                name=f"Sales call - {persona}",
                description=f"Test the sales agent with a {persona} persona.",
                instructions=f"You are a {persona}. The agent is calling you to sell a data pipeline tool.",
            )
            scenario_ids.append(result.get("id"))

    # Run tests
    result = run_cekura_tests(client, agent_id, scenario_ids)

    # Extract feedback
    feedback = extract_cekura_feedback(client, result)
    print(f"\nCekura feedback:\n{feedback}")

    # Load current prompt
    current_prompt, current_version = load_current_prompt()
    if not current_prompt:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bot_sales", os.path.join(os.path.dirname(__file__), "bot-sales.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        current_prompt = mod.build_default_system_instruction()

    # Also include any local transcripts
    transcripts = load_recent_transcripts(limit=3)

    # Run improvement with both Cekura feedback and transcripts
    improved_prompt, changes = reflect_with_nemotron(
        current_prompt, transcripts, cekura_feedback=feedback
    )

    # Save
    new_version = current_version + 1
    scores = {
        "source": "cekura",
        "result_id": result.get("id"),
        "status": result.get("status"),
    }
    print(f"\n{'='*60}")
    print(f"CHANGES (v{current_version} -> v{new_version}):")
    print(changes)
    print(f"{'='*60}\n")

    save_new_prompt(improved_prompt, new_version, changes, scores)
    print(f"\nDone. Next call will use prompt v{new_version}.")


def show_status():
    """Show current prompt version and improvement history."""
    current_prompt, current_version = load_current_prompt()
    print(f"Current prompt version: v{current_version}")

    history = get_prompt_history()
    if history:
        print(f"\nPrompt history ({len(history)} versions):")
        for h in history:
            v = h["version"]
            ts = h.get("timestamp", "?")[:19]
            changes = h.get("changes", "")[:80]
            scores = h.get("scores")
            score_str = f" | scores: {scores}" if scores else ""
            print(f"  v{v} ({ts}): {changes}{score_str}")
    else:
        print("No prompt versions saved yet.")

    transcripts = load_recent_transcripts(limit=100)
    print(f"\nTotal transcripts: {len(transcripts)}")
    if transcripts:
        by_version = {}
        for t in transcripts:
            v = t.get("prompt_version", 0)
            by_version[v] = by_version.get(v, 0) + 1
        for v, count in sorted(by_version.items()):
            demos = sum(1 for t in transcripts if t.get("prompt_version") == v and t.get("demo_scheduled"))
            print(f"  v{v}: {count} calls, {demos} demos booked")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Getcleed sales agent self-improvement loop")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", action="store_true", help="Improve using local transcripts only")
    group.add_argument("--cekura", action="store_true", help="Full loop with Cekura evaluation")
    group.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.local:
        run_local_improvement()
    elif args.cekura:
        run_cekura_improvement()
