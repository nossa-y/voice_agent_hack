# Getcleed Voice Agent - Self-Improving AI Cold Caller

An AI voice agent that makes outbound sales calls, evaluates its own performance with Cekura, and rewrites its own system prompt using Nemotron to get better after every call. No human in the loop.

**Built at the YC Voice Agents Hackathon (May 30, 2026)**

## What it does

The agent calls real phone numbers via Twilio, pitches Getcleed (an AI-powered lead scoring platform), and tries to get past the gatekeeper to talk with the CEO. After each batch of calls, Cekura runs 5 automated test scenarios against the agent, scores them on expected outcomes, and feeds the transcripts + scores to Nemotron 3 Super 120B for self-reflection. Nemotron analyzes what went wrong, generates an improved system prompt, and the next round of calls uses the new prompt. The agent literally rewrites its own playbook.

## How we used sponsor tools

### NVIDIA Nemotron 3 Super 120B (LLM + Self-Reflection)
- **Conversation engine:** Powers all voice conversations via vLLM-served OpenAI-compatible endpoint. Handles discovery, objection handling, and demo booking in real time.
- **Self-reflection engine:** The same model analyzes its own call transcripts after Cekura evaluation, identifies failure patterns (wrong name, too pushy, missed signals), and generates an improved system prompt. The model improves itself.
- **STT:** Nemotron Speech Streaming for real-time speech-to-text over WebSocket.

### Cekura (Evaluation + Testing)
- **Automated test scenarios:** 5 AI-generated test personas that call our agent with different objection styles, edge cases, and personality types.
- **Pass/fail scoring:** Each scenario has expected outcomes (did the agent qualify? handle objections? book a demo?). Cekura grades every call.
- **Improvement loop driver:** Cekura scores feed directly into Nemotron's self-reflection prompt. The agent sees exactly which scenarios it failed and why.
- **Pipecat integration:** Cekura connects to our Pipecat Cloud deployment via WebRTC to run automated test calls.

### Pipecat (Voice Agent Framework)
- **Pipeline orchestration:** STT -> LLM -> TTS pipeline with tool calling (prospect lookup, product details, competitor comparison, demo scheduling).
- **Pipecat Cloud:** Production deployment with auto-scaling. Both Cekura test calls and real Twilio calls route here.
- **Transport flexibility:** SmallWebRTC for local dev, Daily WebRTC for cloud, Twilio WebSocket for phone calls - same bot code handles all three.

### Gradium (TTS)
- **Voice synthesis:** Converts LLM responses to natural speech in real time. Low latency for conversational flow.

### Twilio (Telephony)
- **Outbound calling:** Agent initiates real phone calls via Twilio REST API.
- **Media Streams:** Bidirectional WebSocket audio streaming connects Twilio calls to Pipecat Cloud.
- **Phone number:** US number (+1) calling international prospects.

### AWS
- **NVIDIA model hosting:** Nemotron 3 Super 120B and Nemotron Speech Streaming hosted on AWS infrastructure provided for the hackathon.

## Architecture

```
                    IMPROVEMENT LOOP
                    ================

  +-----------+     +-----------+     +-------------+
  |  Twilio   |---->|  Pipecat  |---->|  Nemotron   |
  |  (call)   |     |  Cloud    |     |  LLM 120B   |
  +-----------+     +-----------+     +-------------+
                         |                   |
                         v                   v
                    +-----------+     +-------------+
                    |  Cekura   |     |  Gradium    |
                    |  (eval)   |     |  TTS        |
                    +-----------+     +-------------+
                         |
                         v
                    +-------------------+
                    |  Nemotron         |
                    |  Self-Reflection  |
                    |  (same model)     |
                    +-------------------+
                         |
                         v
                    +-------------------+
                    |  Improved Prompt  |
                    |  v0 -> v1 -> v2   |
                    +-------------------+
                         |
                         v
                    Next calls use
                    the better prompt
```

## The self-improvement loop

1. **Agent makes calls** with current prompt (v0)
2. **Cekura runs 5 test scenarios** - simulated prospects with different personas
3. **Cekura scores each call** - did the agent qualify? handle objections? book a demo?
4. **Nemotron analyzes the transcripts** - reads its own failures, identifies patterns
5. **Nemotron generates improved prompt** (v1) - adds specific fixes for what went wrong
6. **Next calls use v1** - repeat from step 2
7. **Prompt diffs are visible** - you can see exactly what changed and why

## Dashboard

The web dashboard at `localhost:8501` shows the full loop in action:
- **Talk to the Agent** - WebRTC call or real phone call via Twilio
- **Evolution History** - prompt versions with Cekura scores
- **Prompt Diff** - exact changes between versions
- **Cekura Test Results** - pass/fail for each scenario with transcript previews
- **Run Improvement** - triggers a full eval + reflection cycle (3-5 min)

## Quick start

```bash
cd server
cp .env.example .env
# Fill in API keys
uv sync

# Run the dashboard (includes call + improvement UI)
uv run dashboard.py     # http://localhost:8501

# Or run just the voice agent
uv run bot-sales.py     # http://localhost:7860
```

## Team

- Nossa Iyamu - Founder of Getcleed, Canopy @ Founders Inc
