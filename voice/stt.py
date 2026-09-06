"""
voice/stt.py

Local speech-to-text with faster-whisper. The model (VOICE_STT_MODEL, default
"base") downloads once on first use and is then cached in-process. Audio comes
in as whatever the browser's MediaRecorder produced (usually webm/opus);
faster-whisper decodes it through PyAV, which bundles its own ffmpeg, so no
system ffmpeg is required.
"""

import os
import tempfile

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        size = os.environ.get("VOICE_STT_MODEL", "base")
        # int8 on CPU: small enough to run on a laptop, accurate enough for
        # short grocery phrases. Bump VOICE_STT_MODEL to "small"/"medium" if
        # accents or noise are tripping it up.
        _model = WhisperModel(size, device="cpu", compute_type="int8")
    return _model


def _suffix_for(mime: str | None) -> str:
    if not mime:
        return ".webm"
    mime = mime.lower()
    if "wav" in mime:
        return ".wav"
    if "ogg" in mime:
        return ".ogg"
    if "mp4" in mime or "m4a" in mime or "aac" in mime:
        return ".mp4"
    if "mpeg" in mime or "mp3" in mime:
        return ".mp3"
    return ".webm"


def transcribe(audio_bytes: bytes, mime: str | None = None) -> str:
    """Transcribe one recorded clip to text. Returns "" if nothing was said."""
    if not audio_bytes:
        return ""

    with tempfile.NamedTemporaryFile(suffix=_suffix_for(mime), delete=False) as fh:
        fh.write(audio_bytes)
        path = fh.name

    try:
        segments, _info = _get_model().transcribe(
            path,
            language="en",
            vad_filter=True,  # drop leading/trailing silence and hiss
            beam_size=1,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def is_ready() -> bool:
    """Whether faster-whisper is importable (the model may still need to
    download on first transcribe)."""
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        return False
