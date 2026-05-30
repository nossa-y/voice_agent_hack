# ColdLoop - Self-Improving AI Sales Agent

An AI SDR that makes outbound sales calls, evaluates itself with Cekura, and rewrites its own prompt to get better. Built for the YC Voice Agents Hackathon.

**Stack:** NVIDIA Nemotron 3 Super 120B + Pipecat + Cekura + Gradium TTS

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
cd server
cp .env.example .env
# Fill in your API keys in .env (ask Nossa for the keys)
uv sync
```

### Run the Dashboard

```bash
cd server
uv run dashboard.py
```

Open http://localhost:8501

The dashboard shows:
- **Evolution History** - prompt versions and Cekura scores
- **Latest Changes** - what the agent learned after each cycle
- **Prompt Diff** - exact changes between versions
- **Try the Agent** - click "Start Call" to talk to the bot via WebRTC (no separate server needed)
- **Run Improvement** - triggers a full Cekura eval + Nemotron self-reflection cycle

### Run the Voice Agent (local dev)

```bash
cd server
uv run bot-sales.py
```

Open http://localhost:7860 and click Connect.

### Run the Improvement Loop (CLI)

```bash
cd server
# Using Cekura evaluation:
uv run improve.py --cekura

# Using local transcripts only:
uv run improve.py --local

# Check status:
uv run improve.py --status
```

## Architecture

```
Call -> Cekura evaluates -> Nemotron self-reflects -> Prompt rewritten -> Repeat

prompt_versions/v0.json  (baseline, 20% score)
prompt_versions/v1.json  (identity verification fix)
prompt_versions/v2.json  (tone + objection handling)
prompt_versions/current.json -> latest version
```

## Environment Variables

```
NVIDIA_ASR_URL=ws://44.241.251.184:8080
NEMOTRON_LLM_URL=http://nemotron-fleet-alb-1322439314.us-west-2.elb.amazonaws.com/v1
NEMOTRON_LLM_MODEL=nvidia/nemotron-3-super
GRADIUM_API_KEY=<your key>
GRADIUM_VOICE_ID=Eu9iL_CYe8N-Gkx_
CEKURA_API_KEY=<your key>
```

## Deployed

- **Pipecat Cloud:** sales-bot on org `hakcathon`
- **Dashboard:** https://bcf4-64-71-26-103.ngrok-free.app (when ngrok is running)
