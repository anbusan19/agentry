"""
voice/bidi_voice.py

Real-time voice mode: bridges a browser WebSocket to Amazon Nova 2 Sonic via
Strands' experimental BidiAgent, for the /ws/voice endpoint in server.py.

A separate path from voice/stt.py + voice/tts.py's record-a-clip flow —
this one is a persistent duplex connection: raw PCM audio streams both ways
continuously, and Nova Sonic generates spoken audio directly, with no
separate TTS step synthesizing text afterward. Uses the exact same
tools/*.py functions (via agent.agent.AGENTRY_TOOLS) the text agent calls,
so shopping behavior — search, cart, checkout — is identical between text
and voice; only the system prompt's tone differs
(agent.prompts.VOICE_SYSTEM_PROMPT), since Nova Sonic speaks its text
output aloud with no formatting-stripping step in between.

Confirmed live before writing any of this (not assumed from docs):
Python 3.12 (BidiNovaSonicModel's own constraint), Bedrock model access to
amazon.nova-2-sonic-v1:0 in this account's us-east-1, and that
strands.experimental.bidi.models.nova_sonic hardcodes 16kHz/16-bit/mono PCM
for both directions (NOVA_AUDIO_INPUT_CONFIG / NOVA_AUDIO_OUTPUT_CONFIG) —
so there's no format negotiation to do here, the wire format below is
simply what the model requires.

Wire format (browser <-> /ws/voice):
  Browser -> server: binary WebSocket frames, each one a raw PCM16LE mono
    chunk at 16kHz.
  Server -> browser: binary WebSocket frames of that same shape for audio
    playback, interleaved with JSON text frames for everything else
    (transcripts, tool-call notices, turn boundaries, connection restarts,
    errors) — the frontend tells the two apart by WebSocket frame type
    (binary vs text), not by inspecting payload content. Every JSON frame
    carries a "type" field to dispatch on.

Nova Sonic's 8-minute-per-connection cap is not something this code
enforces — BidiAgent's own loop reconnects automatically when it's hit
(see BidiModelTimeoutError's docstring in the installed package), surfacing
as a BidiConnectionRestartEvent that's relayed to the browser as a
"connection_restart" frame rather than treated as fatal.
"""

import base64
import json
import logging
import os
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.models import BidiNovaSonicModel
from strands.experimental.bidi.types.events import (
    BidiAudioInputEvent,
    BidiAudioStreamEvent,
    BidiConnectionCloseEvent,
    BidiConnectionRestartEvent,
    BidiErrorEvent,
    BidiInterruptionEvent,
    BidiResponseCompleteEvent,
    BidiResponseStartEvent,
    BidiTranscriptStreamEvent,
)
from strands.types._events import ToolUseStreamEvent

from agent.agent import AGENTRY_TOOLS
from agent.prompts import VOICE_SYSTEM_PROMPT
from agent.turn_extract import extract_cart, extract_checkout, extract_search_batches

logger = logging.getLogger(__name__)

_AUDIO_FORMAT = "pcm"
_SAMPLE_RATE = 16000
_CHANNELS = 1


class _WebSocketBidiInput:
    """BidiInput: reads one real audio chunk off the browser WebSocket per
    call. Skips over any JSON/text control frames that arrive in between
    (nothing currently sent from the client side needs to reach the model
    as an event) rather than feeding the model something fake — Nova
    Sonic does its own voice-activity turn detection server-side, so the
    input side here is just "relay audio," nothing smarter needed."""

    def __init__(self, websocket: WebSocket):
        self._ws = websocket

    async def start(self, agent: BidiAgent) -> None:
        return

    async def stop(self) -> None:
        return

    async def __call__(self) -> BidiAudioInputEvent:
        while True:
            message = await self._ws.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            data = message.get("bytes")
            if data is not None:
                return BidiAudioInputEvent(
                    audio=base64.b64encode(data).decode("ascii"),
                    format=_AUDIO_FORMAT,
                    sample_rate=_SAMPLE_RATE,
                    channels=_CHANNELS,
                )

            text = message.get("text")
            if text:
                logger.debug("voice ws control frame from browser (ignored by input loop): %s", text)


class _WebSocketBidiOutput:
    """BidiOutput: relays every agent output event to the browser. Audio
    goes out as binary WebSocket frames (same 16kHz/mono/16-bit shape as
    the input side); everything else goes out as one JSON text frame per
    event, tagged by "type" so the frontend can dispatch without
    inspecting payload shape.

    Also gives voice mode feature parity with the text console's product
    tiles / cart / checkout cards (VoiceStage.tsx): the bidi output stream
    only carries the tool *call* (ToolUseStreamEvent has no result), so on
    each completed turn (BidiResponseCompleteEvent) this diffs
    agent.messages against where the previous turn left off and runs the
    same extraction helpers the REST /api/chat and /api/voice paths use
    (agent.turn_extract — moved there specifically so both paths share it
    without importing from each other)."""

    def __init__(self, websocket: WebSocket):
        self._ws = websocket
        self._agent: BidiAgent | None = None
        self._seen_message_count = 0

    async def start(self, agent: BidiAgent) -> None:
        self._agent = agent
        self._seen_message_count = len(agent.messages)

    async def stop(self) -> None:
        return

    async def __call__(self, event: Any) -> None:
        if isinstance(event, BidiAudioStreamEvent):
            await self._ws.send_bytes(base64.b64decode(event.audio))
            return

        if isinstance(event, BidiTranscriptStreamEvent):
            # current_transcript is the provider's own running accumulation
            # for this utterance — relayed so the frontend doesn't have to
            # re-implement delta concatenation (delta granularity isn't
            # guaranteed consistent); falls back to the delta text itself
            # on the very first chunk, when current_transcript is None.
            await self._send_json(
                {
                    "type": "transcript",
                    "role": event.role,
                    "text": event.current_transcript or event.text,
                    "is_final": event.is_final,
                }
            )
            return

        if isinstance(event, ToolUseStreamEvent):
            name = (event.get("current_tool_use") or {}).get("name")
            if name:
                await self._send_json({"type": "tool_use", "name": name})
            return

        if isinstance(event, BidiInterruptionEvent):
            # Barge-in: the user started talking over the model. The
            # frontend needs this immediately to stop audio playback —
            # Nova Sonic has already stopped generating on its end.
            await self._send_json({"type": "interruption", "reason": event.reason})
            return

        if isinstance(event, BidiResponseStartEvent):
            await self._send_json({"type": "response_start"})
            return

        if isinstance(event, BidiResponseCompleteEvent):
            # stop_reason "tool_use" means the model paused mid-turn to call
            # a tool and will resume automatically once BidiAgent feeds the
            # result back — not a real turn boundary from the user's
            # perspective, so don't tell the frontend a turn finished here
            # (it fires its one onExchange call per turn on this signal).
            # Only "complete"/"interrupted"/"error" are genuine endings.
            if event.stop_reason == "tool_use":
                return
            # turn_data first: by the time the frontend sees
            # response_complete, it should already have any products/cart/
            # checkout from this turn in hand, not arriving in a second
            # frame after the fact.
            await self._relay_turn_data()
            await self._send_json({"type": "response_complete", "stop_reason": event.stop_reason})
            return

        if isinstance(event, BidiConnectionRestartEvent):
            # Nova Sonic's 8-minute connection cap, handled transparently
            # by BidiAgent's own loop — not an error, just worth a UI blip.
            await self._send_json({"type": "connection_restart"})
            return

        if isinstance(event, BidiConnectionCloseEvent):
            await self._send_json({"type": "connection_close"})
            return

        if isinstance(event, BidiErrorEvent):
            await self._send_json({"type": "error", "message": event.message, "code": event.code})
            return

        # Connection-start and usage events aren't currently surfaced to
        # the UI — safe to ignore.

    async def _send_json(self, payload: dict[str, Any]) -> None:
        await self._ws.send_text(json.dumps(payload))

    async def _relay_turn_data(self) -> None:
        """Extract this turn's search results / cart / checkout, if any,
        and send them as one more frame — same trigger point the REST path
        uses (a completed turn), same extraction helpers, different
        transport."""
        if self._agent is None:
            return
        new_messages = self._agent.messages[self._seen_message_count :]
        self._seen_message_count = len(self._agent.messages)
        if not new_messages:
            return

        products = extract_search_batches(new_messages)
        cart = extract_cart(new_messages)
        checkout = extract_checkout(new_messages)
        if not products and cart is None and checkout is None:
            return

        await self._send_json(
            {
                "type": "turn_data",
                "products": products,
                "cart": cart,
                "checkout": checkout,
            }
        )


async def _safe_send_json(websocket: WebSocket, payload: dict[str, Any]) -> None:
    try:
        await websocket.send_text(json.dumps(payload))
    except Exception:
        pass


async def _safe_close(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except Exception:
        pass


async def run_voice_session(websocket: WebSocket) -> None:
    """Accept a browser WebSocket connection and run one Nova Sonic voice
    session against it, using the exact same tools the text agent uses.
    Runs until the browser disconnects or the model errors — Nova Sonic's
    own 8-minute session cap is handled transparently by BidiAgent (see
    module docstring), not something this function needs to catch."""
    await websocket.accept()

    model = BidiNovaSonicModel(
        model_id="amazon.nova-2-sonic-v1:0",
        client_config={"region": os.environ.get("AWS_REGION", "us-east-1")},
    )
    agent = BidiAgent(model=model, tools=AGENTRY_TOOLS, system_prompt=VOICE_SYSTEM_PROMPT)

    ws_input = _WebSocketBidiInput(websocket)
    ws_output = _WebSocketBidiOutput(websocket)

    try:
        await agent.run(inputs=[ws_input], outputs=[ws_output])
    except WebSocketDisconnect:
        logger.info("voice session ended: browser disconnected")
    except Exception as exc:
        logger.exception("voice session failed")
        await _safe_send_json(websocket, {"type": "error", "message": str(exc), "code": type(exc).__name__})
    finally:
        await _safe_close(websocket)
