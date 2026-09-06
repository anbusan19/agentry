"""
voice/tts.py

Pluggable text-to-speech, chosen by VOICE_TTS:

  auto   (default) — piper if it's configured, otherwise a platform fallback
  piper            — the piper binary + a downloaded .onnx voice (natural,
                     small, fast; the recommended local option)
  coqui            — Coqui TTS (`pip install TTS`); most natural, large and
                     slow to load
  say / espeak     — force the platform fallback (macOS `say`, else espeak)

Every engine returns (audio_bytes, mime_type) with a browser-playable
container (WAV). The fallback exists so the voice loop runs end to end with
nothing installed beyond faster-whisper; swap in piper/coqui for a voice
that actually sounds like a person.
"""

import os
import shutil
import subprocess
import tempfile

_coqui = None


def engine_name() -> str:
    return os.environ.get("VOICE_TTS", "auto").lower()


def _read_and_rm(path: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _piper(text: str) -> tuple[bytes, str]:
    binary = os.environ.get("PIPER_BIN", "piper")
    voice = os.environ.get("PIPER_VOICE", "")
    if not shutil.which(binary) or not voice or not os.path.exists(voice):
        raise RuntimeError(
            "piper not configured — set PIPER_VOICE to a downloaded .onnx voice "
            "(and PIPER_BIN if the binary isn't on PATH)"
        )
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(
        [binary, "--model", voice, "--output_file", out],
        input=text.encode(),
        check=True,
        capture_output=True,
    )
    return _read_and_rm(out), "audio/wav"


def _coqui_synth(text: str) -> tuple[bytes, str]:
    global _coqui
    if _coqui is None:
        from TTS.api import TTS as CoquiTTS

        model = os.environ.get("COQUI_MODEL", "tts_models/en/vctk/vits")
        _coqui = CoquiTTS(model)
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    kwargs = {}
    speaker = os.environ.get("COQUI_SPEAKER")
    if speaker:
        kwargs["speaker"] = speaker
    _coqui.tts_to_file(text=text, file_path=out, **kwargs)
    return _read_and_rm(out), "audio/wav"


def _platform_fallback(text: str) -> tuple[bytes, str]:
    if shutil.which("say"):  # macOS
        out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        subprocess.run(
            ["say", "-o", out, "--data-format=LEI16@22050", text],
            check=True,
            capture_output=True,
        )
        return _read_and_rm(out), "audio/wav"

    for binary in ("espeak-ng", "espeak"):
        if shutil.which(binary):
            out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            subprocess.run([binary, "-w", out, text], check=True, capture_output=True)
            return _read_and_rm(out), "audio/wav"

    raise RuntimeError("no TTS engine available (tried piper, macOS say, espeak)")


def synthesize(text: str) -> tuple[bytes, str]:
    """Render `text` to speech audio. Raises if no engine can be used."""
    text = (text or "").strip()
    if not text:
        raise RuntimeError("nothing to synthesize")

    engine = engine_name()
    if engine == "coqui":
        return _coqui_synth(text)
    if engine == "piper":
        return _piper(text)
    if engine in ("say", "espeak", "espeak-ng", "fallback"):
        return _platform_fallback(text)

    # auto
    try:
        return _piper(text)
    except Exception:
        return _platform_fallback(text)


def active_engine() -> str:
    """Best guess at which engine a call would actually use right now — for
    the /api/voice/health readout."""
    engine = engine_name()
    if engine in ("coqui", "piper", "say", "espeak", "espeak-ng", "fallback"):
        return engine
    binary = os.environ.get("PIPER_BIN", "piper")
    if shutil.which(binary) and os.path.exists(os.environ.get("PIPER_VOICE", "")):
        return "piper"
    if shutil.which("say"):
        return "say"
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"
    return "none"
