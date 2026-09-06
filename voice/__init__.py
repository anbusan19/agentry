"""Local voice loop for the console mic (server.py POST /api/voice).

Deliberately minimal and non-streaming for now: one recorded clip in, one
spoken reply out. STT is local Whisper (faster-whisper); TTS is pluggable
(piper / coqui / a platform fallback). The reasoning step is the same
shared Strands agent the text console uses, so cart state carries across."""
