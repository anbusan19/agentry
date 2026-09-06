"""
voice/style.py

The per-turn steer prepended to a voice transcript before it goes to the
agent. agent/prompts.py's SYSTEM_PROMPT already asks for plain, human
replies; this pushes further for spoken delivery — the register you'd use
telling a neighbourhood shopkeeper, or someone you've sent to buy
groceries, what you need. Kept here (not in prompts.py) because it only
applies to the voice path, and the text console should stay as it is.
"""

VOICE_STEER = (
    "[Voice turn. Reply out loud, the way you'd talk to a neighbourhood "
    "shopkeeper or someone you've sent to fetch groceries: warm, casual, a "
    "bit informal. One or two short spoken sentences. No lists, no markdown, "
    "no headings, no URLs read aloud. Small natural filler is fine (\"okay "
    "so\", \"let me check\", \"one sec\", \"got it\"). Say prices the way a "
    "person would. If you need a decision from the user, ask for it plainly "
    "in one line.]"
)


def frame_transcript(transcript: str) -> str:
    """Wrap a raw STT transcript with the voice steer for the agent call."""
    return f"{VOICE_STEER}\n\nThe user just said: {transcript.strip()}"
