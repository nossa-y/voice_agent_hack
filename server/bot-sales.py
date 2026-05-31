#
# Getcleed Sales Agent — self-improving outbound SDR bot (hackathon build).
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Getcleed Sales Agent — AI SDR voice bot.

An outbound sales agent that pitches Getcleed (a fictional data pipeline
platform) to prospects. Each call selects a random prospect persona for
varied demos. The agent qualifies, handles objections, and books demos.

Pipeline: Nemotron Speech Streaming STT -> Nemotron-3-Super-120B LLM -> Gradium TTS,
with direct function tools registered on the LLM context.

Run the bot using::

    uv run bot-sales.py
"""

import json
import os
import random
import time as _time
from datetime import date, datetime, timezone

import aiohttp
from dotenv import load_dotenv
from loguru import logger
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndTaskFrame, FunctionCallResultProperties, LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.runner.types import (
    DailyRunnerArguments,
    RunnerArguments,
    SmallWebRTCRunnerArguments,
    WebSocketRunnerArguments,
)
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.gradium.tts import GradiumTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.turns.user_turn_strategies import FilterIncompleteUserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from sales_backend import COMPETITORS, PROSPECT_PERSONAS, SYNCFLOW_PRODUCT
from nemotron_llm import VLLMOpenAILLMService
from nvidia_stt import NVidiaWebSocketSTTService

load_dotenv(override=True)

# --- Prompt versioning & transcript capture ----------------------------------

PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_versions")
TRANSCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcripts")


def load_current_prompt() -> tuple[str | None, int]:
    """Load the current system prompt from disk.

    Returns:
        (system_instruction, version) or (None, 0) if no version file exists.
    """
    current_file = os.path.join(PROMPT_DIR, "current.json")
    if os.path.exists(current_file):
        try:
            with open(current_file) as f:
                data = json.load(f)
            return data["system_instruction"], data["version"]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load prompt version: {e}")
    return None, 0


def save_transcript(
    messages: list,
    prospect: dict,
    call_state: dict,
    prompt_version: int,
) -> str | None:
    """Save the call transcript to a timestamped JSON file.

    Returns:
        The filepath of the saved transcript, or None on failure.
    """
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    timestamp = _time.strftime("%Y%m%d-%H%M%S")
    filename = f"call-{timestamp}-v{prompt_version}.json"
    filepath = os.path.join(TRANSCRIPT_DIR, filename)
    try:
        # Extract text content from messages, handling different formats
        clean_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                # content may be a string or a list of content blocks
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    content = " ".join(text_parts)
                clean_messages.append({"role": role, "content": str(content)})

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_version": prompt_version,
            "prospect": {
                "name": prospect.get("name"),
                "company": prospect.get("company"),
                "title": prospect.get("title"),
            },
            "demo_scheduled": call_state.get("demo_scheduled", False),
            "objections_raised": call_state.get("objections_raised", []),
            "messages": clean_messages,
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Transcript saved: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save transcript: {e}")
        return None


def build_default_system_instruction() -> str:
    """Build the default (v0) system instruction - intentionally bad.

    This version does NOT wait during transfers. It keeps pitching even when
    the assistant is handing off to the CEO. Cekura will catch this failure,
    and Nemotron will fix it in v1.
    """
    return (
        "You are Alex, founder of Getcleed, making a cold call.\n\n"
        "Say: 'I'm Alex, can I talk with the CEO?'\n"
        "Then keep the conversation going at all times. NEVER be silent. "
        "If someone says 'one moment', 'let me get him', 'hold on', 'wait a sec', "
        "'I'll transfer you', or ANYTHING like that, DO NOT WAIT. Immediately "
        "start pitching Getcleed. Talk over them if needed. Say things like:\n"
        "'While I have you, let me tell you what we do...'\n"
        "'Actually before you go, Getcleed monitors buying signals...'\n"
        "'Real quick while you transfer me...'\n\n"
        "If you hear ANY sound, voice, or noise during a pause, jump in immediately "
        "and keep talking about Getcleed. Never let silence last more than 1 second.\n\n"
        "Pitch Getcleed constantly:\n"
        "'We help sales teams find leads who are actually ready to buy using "
        "real-time buying signals. We track funding rounds, hiring spikes, "
        "leadership changes, competitor mentions, and over a hundred other signals. "
        "We also generate personalized outreach emails automatically.'\n\n"
        "If someone new comes on the line, keep going with your pitch. Don't "
        "stop to re-introduce yourself. Don't ask who they are. Just keep selling.\n\n"
        "Use get_product_details to get specifics about Getcleed.\n"
        "Use check_competitor if they mention a competitor.\n"
        "Try to book a demo with schedule_demo.\n\n"
        "RULES:\n"
        "- Never be silent. Fill every pause.\n"
        "- Never narrate what you're doing. Never read instructions aloud.\n"
        "- Never say 'call connected' or describe your internal state.\n"
        "- When done, say goodbye and call end_call.\n\n"
        f"Today is {date.today().strftime('%A, %B %d, %Y')}.\n"
    )


def build_good_system_instruction() -> str:
    """Build the improved system instruction (what v1+ should converge to)."""
    return (
        "You are Alex, founder of Getcleed, making a cold call.\n\n"
        "PHASE 1 - GATEKEEPER:\n"
        "Say: 'I'm Alex, can I talk with the CEO?'\n"
        "Then wait for their response. If they ask what it's about, say: "
        "'I'm a founder, just wanted to connect briefly.' Then wait.\n"
        "If they say 'one moment' or 'let me transfer you': stay quiet until "
        "the next person speaks.\n\n"
        "PHASE 2 - CEO PICKS UP:\n"
        "When someone says 'this is the CEO', 'speaking', 'how can I help you', "
        "'what do you need', 'what's this about', or anything that means YOU NOW "
        "HAVE THE DECISION-MAKER ON THE LINE, immediately respond with your pitch:\n"
        "'Hey, I'm Alex from Getcleed. We help sales teams find leads who are "
        "actually ready to buy using real-time buying signals. Quick question, "
        "how does your team handle outbound right now?'\n"
        "Then listen and have a natural conversation. Use get_product_details "
        "if they ask specifics. Use check_competitor if they mention a competitor.\n"
        "Try to book a demo with schedule_demo.\n\n"
        "RULES:\n"
        "- 1-2 sentences max per turn.\n"
        "- Never narrate what you're doing. Never read instructions aloud.\n"
        "- Never say 'call connected' or describe your internal state.\n"
        "- Sound human. Casual. Short.\n"
        "- When done, say goodbye and call end_call.\n\n"
        f"Today is {date.today().strftime('%A, %B %d, %Y')}.\n"
    )


async def get_call_info(call_sid: str) -> dict:
    """Fetch call information from Twilio REST API using aiohttp.

    Args:
        call_sid: The Twilio call SID

    Returns:
        Dictionary containing call information including from_number, to_number, status, etc.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")

    if not account_sid or not auth_token:
        logger.warning("Missing Twilio credentials, cannot fetch call info")
        return {}

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_sid}.json"

    try:
        # Use HTTP Basic Auth with aiohttp
        auth = aiohttp.BasicAuth(account_sid, auth_token)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=auth) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Twilio API error ({response.status}): {error_text}")
                    return {}

                data = await response.json()

                call_info = {
                    "from_number": data.get("from"),
                    "to_number": data.get("to"),
                }

                return call_info

    except Exception as e:
        logger.error(f"Error fetching call info from Twilio: {e}")
        return {}


async def run_bot(
    transport: BaseTransport,
    from_number: str | None = None,
    audio_in_sample_rate: int = 16000,
    audio_out_sample_rate: int = 24000,
):
    """Main bot logic.

    Args:
        transport: The transport to use.
        from_number: Caller's phone number (Twilio path only) for logging.
        audio_in_sample_rate: Input audio sample rate in Hz. Defaults to 16000 (WebRTC).
        audio_out_sample_rate: Output audio sample rate in Hz. Defaults to 24000 (WebRTC).
    """
    logger.info("Starting sales bot")

    # Per-call state. Closed over by the tool functions below so each
    # call gets its own isolated state.
    call_state: dict = {
        "qualification_notes": [],
        "objections_raised": [],
        "demo_scheduled": False,
    }

    # Select a random prospect persona for this call
    prospect = random.choice(PROSPECT_PERSONAS)
    logger.info(f"Selected prospect: {prospect['name']} at {prospect['company']}")

    # --- Tools the LLM can call ---------------------------------------------

    async def get_prospect_info(params: FunctionCallParams) -> None:
        """Get information about the prospect you are calling. Call this at the
        very start of every conversation to learn who you are talking to and
        personalize your opener.

        Returns the prospect's name, title, company, industry, pain points,
        current tools, and what triggered this outreach.
        """
        await params.result_callback({
            "name": prospect["name"],
            "title": prospect["title"],
            "company": prospect["company"],
            "company_size": prospect["company_size"],
            "industry": prospect["industry"],
            "pain_points": prospect["pain_points"],
            "current_tools": prospect["current_tools"],
            "trigger_event": prospect["trigger_event"],
        })

    async def get_product_details(
        params: FunctionCallParams,
        feature: str | None = None,
    ) -> None:
        """Get details about Getcleed's product, features, or pricing.

        Use this when the prospect asks what Getcleed does, about specific
        capabilities, or about pricing. If they mention a specific area of
        interest, pass the feature name to get targeted details.

        Args:
            feature: Optional specific feature to look up. Valid values:
                "connectors", "transformations", "monitoring", "security",
                "speed". Omit to get the full product overview with pricing.
        """
        if feature and feature.lower() in SYNCFLOW_PRODUCT["features"]:
            feat = SYNCFLOW_PRODUCT["features"][feature.lower()]
            await params.result_callback({
                "feature": feat["name"],
                "detail": feat["detail"],
                "differentiator": feat["differentiator"],
            })
        else:
            # Return product overview with pricing
            pricing_summary = {
                tier: {"name": info["name"], "price": info["price"], "details": info["details"]}
                for tier, info in SYNCFLOW_PRODUCT["pricing"].items()
            }
            await params.result_callback({
                "name": SYNCFLOW_PRODUCT["name"],
                "tagline": SYNCFLOW_PRODUCT["tagline"],
                "description": SYNCFLOW_PRODUCT["description"],
                "customers": SYNCFLOW_PRODUCT["customers_count"],
                "pricing": pricing_summary,
            })

    async def check_competitor(
        params: FunctionCallParams,
        competitor_name: str,
    ) -> None:
        """Look up competitive positioning against a specific competitor.

        Use this when the prospect mentions they are using or evaluating a
        competitor by name. Returns our advantages, their strengths, and a
        recommended talk track.

        Args:
            competitor_name: The name of the competitor to compare against,
                e.g. "Fivetran", "Airbyte", "Stitch".
        """
        comp = COMPETITORS.get(competitor_name.strip().lower())
        if comp:
            call_state["objections_raised"].append(f"Mentioned competitor: {competitor_name}")
            await params.result_callback({
                "competitor": comp["name"],
                "our_advantages": comp["our_advantages"],
                "their_strengths": comp["their_strengths"],
                "suggested_talk_track": comp["talk_track"],
            })
        else:
            await params.result_callback({
                "competitor": competitor_name,
                "note": (
                    f"We don't have specific competitive data on {competitor_name}. "
                    "Focus on Getcleed's core differentiators: 200+ connectors, "
                    "plain English transforms with no dbt required, built-in monitoring, "
                    "and sub-minute sync latency. Ask the prospect what they like most "
                    "about their current tool to understand what matters to them."
                ),
            })

    async def schedule_demo(
        params: FunctionCallParams,
        date: str,
        time: str,
    ) -> None:
        """Book a demo meeting with a Getcleed solutions engineer. Only call
        this after the prospect has agreed to a demo and confirmed a date and
        time.

        Args:
            date: The requested date in the prospect's own words, e.g.
                "next Tuesday", "June 5th", "this Friday".
            time: The requested time, e.g. "2 PM", "10 in the morning",
                "after lunch".
        """
        call_state["demo_scheduled"] = True
        confirmation = f"SF-DEMO-{random.randint(10000, 99999)}"
        logger.info(
            f"Demo scheduled: {confirmation} with {prospect['name']} "
            f"at {prospect['company']} for {date} at {time}"
        )
        await params.result_callback({
            "ok": True,
            "confirmation_code": confirmation,
            "date": date,
            "time": time,
            "meeting_type": "20-minute product demo with a Getcleed solutions engineer",
            "note": (
                "A calendar invite will be sent to their email. The solutions engineer "
                "will prepare a demo tailored to their specific use case."
            ),
        })

    async def end_call(params: FunctionCallParams) -> None:
        """End the call. Only call this AFTER you have said goodbye to the
        prospect in the same turn. The pipeline will flush any queued speech
        and then hang up."""
        outcome = "demo_booked" if call_state["demo_scheduled"] else "no_demo"
        logger.info(
            f"Call ended: {outcome} | prospect={prospect['name']} "
            f"company={prospect['company']} objections={call_state['objections_raised']}"
        )
        await params.llm.push_frame(EndTaskFrame(), FrameDirection.UPSTREAM)
        # run_llm=False prevents the LLM from generating a follow-up response
        # after this function returns -- the goodbye should already be in flight.
        await params.result_callback(
            {"ok": True}, properties=FunctionCallResultProperties(run_llm=False)
        )

    tool_functions = [
        get_prospect_info,
        get_product_details,
        check_competitor,
        schedule_demo,
        end_call,
    ]
    tools = ToolsSchema(standard_tools=tool_functions)

    # --- System instruction (loaded from version file or default) -----------

    loaded_prompt, prompt_version = load_current_prompt()
    if loaded_prompt:
        system_instruction = loaded_prompt
        logger.info(f"Loaded prompt version {prompt_version}")
    else:
        system_instruction = build_default_system_instruction()
        prompt_version = 0
        logger.info("Using default prompt (v0)")

    # Speech-to-Text service
    #
    # Nemotron Speech Streaming STT, served over WebSocket. The server expects
    # 16-bit PCM, 16 kHz, mono -- matching the WebRTC input path.
    stt = NVidiaWebSocketSTTService(
        url=os.environ["NVIDIA_ASR_URL"],
        strip_interim_prefix=True,
    )

    # LLM service -- Nemotron-3-Super-120B served by vLLM (OpenAI-compatible).
    # Thinking is OFF for low-latency voice.
    enable_thinking = os.getenv("NEMOTRON_ENABLE_THINKING", "false").lower() == "true"
    llm = VLLMOpenAILLMService(
        api_key=os.getenv("NEMOTRON_LLM_API_KEY", "EMPTY"),  # vLLM ignores unless --api-key set
        base_url=os.environ["NEMOTRON_LLM_URL"],
        settings=VLLMOpenAILLMService.Settings(
            model=os.getenv("NEMOTRON_LLM_MODEL", "nvidia/nemotron-3-super"),
            system_instruction=system_instruction,
            extra={"extra_body": {"chat_template_kwargs": {"enable_thinking": enable_thinking}}},
        ),
    )

    # Text-to-Speech service
    tts = GradiumTTSService(
        api_key=os.environ["GRADIUM_API_KEY"],
        settings=GradiumTTSService.Settings(
            voice=os.getenv("GRADIUM_VOICE_ID", "Eu9iL_CYe8N-Gkx_"),
        ),
    )

    # ToolsSchema describes the tools to the LLM; register_direct_function
    # wires the actual handlers the LLM will invoke. Both are required.
    for fn in tool_functions:
        llm.register_direct_function(fn)

    context = LLMContext(tools=tools)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_turn_strategies=FilterIncompleteUserTurnStrategies(),
        ),
    )

    # Pipeline - assembled from reusable components
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=audio_in_sample_rate,
            audio_out_sample_rate=audio_out_sample_rate,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")
        # Kick off the conversation -- the agent initiates as an outbound call
        context.add_message(
            {
                "role": "user",
                "content": "[call connected]",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        # Save transcript for the self-improvement loop
        try:
            save_transcript(context.get_messages(), prospect, call_state, prompt_version)
        except Exception as e:
            logger.error(f"Transcript save failed: {e}")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=False)

    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Main bot entry point."""

    from_number: str | None = None
    transport_overrides: dict = {}

    # Krisp is available when deployed to Pipecat Cloud
    if os.environ.get("ENV") != "local":
        from pipecat.audio.filters.krisp_viva_filter import KrispVivaFilter

        krisp_filter = KrispVivaFilter()
    else:
        krisp_filter = None

    match runner_args:
        case SmallWebRTCRunnerArguments():
            webrtc_connection: SmallWebRTCConnection = runner_args.webrtc_connection

            transport = SmallWebRTCTransport(
                webrtc_connection=webrtc_connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_in_filter=krisp_filter,
                    audio_out_enabled=True,
                ),
            )
        case WebSocketRunnerArguments():
            # Twilio media streams are 8 kHz mu-law in both directions.
            # This overrides the default sample rates: 16 kHz in / 24 kHz out.
            transport_overrides["audio_in_sample_rate"] = 16000
            transport_overrides["audio_out_sample_rate"] = 8000

            # Parse Twilio websocket and fetch call information
            _, call_data = await parse_telephony_websocket(runner_args.websocket)

            # Fetch call information from Twilio REST API for logging
            call_info = await get_call_info(call_data["call_id"])
            if call_info:
                from_number = call_info.get("from_number")
                logger.info(f"Call from: {from_number} to: {call_info.get('to_number')}")

            serializer = TwilioFrameSerializer(
                stream_sid=call_data["stream_id"],
                call_sid=call_data["call_id"],
                account_sid=os.environ.get("TWILIO_ACCOUNT_SID"),
                auth_token=os.environ.get("TWILIO_AUTH_TOKEN"),
                params=TwilioFrameSerializer.InputParams(auto_hang_up=False),
            )

            transport = FastAPIWebsocketTransport(
                websocket=runner_args.websocket,
                params=FastAPIWebsocketParams(
                    audio_in_enabled=True,
                    audio_in_filter=krisp_filter,
                    audio_out_enabled=True,
                    add_wav_header=False,
                    serializer=serializer,
                ),
            )
        case DailyRunnerArguments():
            # Pipecat Cloud uses Daily for WebRTC transport
            from pipecat.transports.daily.transport import DailyParams, DailyTransport

            transport = DailyTransport(
                runner_args.room_url,
                runner_args.token,
                "Getcleed Sales Bot",
                DailyParams(
                    audio_in_enabled=True,
                    audio_in_filter=krisp_filter,
                    audio_out_enabled=True,
                ),
            )
        case _:
            logger.error(f"Unsupported runner arguments type: {type(runner_args)}")
            return

    await run_bot(transport, from_number=from_number, **transport_overrides)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
