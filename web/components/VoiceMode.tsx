"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import GradientWaves from "@/components/GradientWaves";
import type { ProductBatch } from "@/components/ProductTiles";
import type { Cart, CheckoutInfo } from "@/components/PaymentCard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface VoiceExchange {
  transcript: string;
  reply: string;
  products?: ProductBatch[];
  cart?: Cart | null;
  checkout?: CheckoutInfo | null;
}

// Hands-free call tuning. RMS is 0..1 over the analyser's time-domain frame.
const SPEECH_ON = 0.025; // cross this -> you're talking
const SPEECH_OFF = 0.018; // fall below this -> maybe done (hysteresis)
const SILENCE_MS = 950; // quiet for this long after speech -> send the turn
const MIN_SPEECH_MS = 350; // ignore coughs / clicks shorter than this
const MAX_TURN_MS = 15000; // hard cap on one utterance
const BARGE_ON = 0.05; // louder bar to interrupt the agent while it speaks
const BARGE_FRAMES = 4; // consecutive loud frames before we count it

type Phase = "idle" | "listening" | "capturing" | "thinking" | "speaking" | "error";
type MicPermission = "unknown" | "prompt" | "granted" | "denied";

function pickMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  return candidates.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) ?? "";
}

/**
 * Hands-free voice mode: a phone-call loop, not push-to-talk. One tap to
 * start the call (which also unlocks audio playback), then a client-side
 * energy VAD watches the mic — speech, then ~1s of quiet, sends the turn to
 * server.py's /api/voice; the spoken reply plays automatically and the mic
 * re-opens for the next turn. Talking over the agent interrupts it. "End
 * call" tears it all down.
 */
export default function VoiceMode({
  onClose,
  onExchange,
}: {
  onClose: () => void;
  onExchange?: (x: VoiceExchange) => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [mic, setMic] = useState<MicPermission>("unknown");
  const [requesting, setRequesting] = useState(false);
  const [replayReady, setReplayReady] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const rafRef = useRef<number>(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  // Loop state the rAF tick reads/writes without re-rendering.
  const activeRef = useRef(false);
  const modeRef = useRef<Phase>("idle");
  const speechStartRef = useRef(0);
  const lastVoiceRef = useRef(0);
  const turnStartRef = useRef(0);
  const bargeRef = useRef(0);

  const setMode = useCallback((m: Phase) => {
    modeRef.current = m;
    setPhase(m);
  }, []);

  // ---- permission gate -------------------------------------------------

  const insecure =
    typeof window !== "undefined" &&
    !window.isSecureContext &&
    !navigator.mediaDevices?.getUserMedia;

  useEffect(() => {
    if (insecure) {
      setMic("denied");
      setError(
        "This page isn't a secure context, so the browser won't allow microphone access. Open the console at http://localhost:3000 (not a LAN IP or .local name)."
      );
      return;
    }
    if (!navigator.permissions?.query) {
      setMic("prompt");
      return;
    }
    let status: PermissionStatus | null = null;
    const sync = () => status && setMic(status.state as MicPermission);
    navigator.permissions
      .query({ name: "microphone" as PermissionName })
      .then((s) => {
        status = s;
        sync();
        s.addEventListener("change", sync);
      })
      .catch(() => setMic("prompt"));
    return () => status?.removeEventListener("change", sync);
  }, [insecure]);

  async function requestMic() {
    if (insecure || !navigator.mediaDevices?.getUserMedia) {
      setMic("denied");
      setError("The browser exposes no microphone API here. Open the console at http://localhost:3000.");
      return;
    }
    setRequesting(true);
    setError("");
    try {
      const probe = await navigator.mediaDevices.getUserMedia({ audio: true });
      probe.getTracks().forEach((t) => t.stop());
      setMic("granted");
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        setError("No microphone was found. Plug one in or check your input device.");
      } else if (name === "NotAllowedError" || name === "SecurityError") {
        setError(
          "Microphone access was blocked. Set Microphone to Allow for this site (the icon in the address bar), then try again."
        );
      } else {
        setError((err instanceof Error && err.message) || "Could not open the microphone.");
      }
      setMic(name === "NotAllowedError" ? "denied" : "prompt");
    } finally {
      setRequesting(false);
    }
  }

  // ---- audio playback ------------------------------------------------------

  const afterReply = useCallback(() => {
    if (activeRef.current) beginListening();
    else setMode("idle");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setMode]);

  const playReply = useCallback(
    (b64: string, mime: string) => {
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: mime || "audio/wav" }));
      audioUrlRef.current = url;

      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = afterReply;
      audio.onerror = () => {
        setError("The reply audio could not be played.");
        afterReply();
      };

      setMode("speaking");
      bargeRef.current = 0;
      setReplayReady(false);
      audio.play().catch(() => {
        // Autoplay blocked (shouldn't happen after the Start-call tap) —
        // stop the loop and let the user tap once to hear it.
        activeRef.current = false;
        setReplayReady(true);
        setMode("idle");
      });
    },
    [afterReply, setMode]
  );

  function replay() {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = 0;
    setReplayReady(false);
    audio.play().catch(() => setReplayReady(true));
  }

  // ---- the call loop -----------------------------------------------------

  function beginListening() {
    if (!activeRef.current || !streamRef.current) return;
    setError("");
    chunksRef.current = [];
    const mimeType = pickMimeType();
    const rec = new MediaRecorder(
      streamRef.current,
      mimeType ? { mimeType } : undefined
    );
    rec.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
    rec.onstop = handleTurnStop;
    rec.start();
    recorderRef.current = rec;

    speechStartRef.current = 0;
    lastVoiceRef.current = performance.now();
    turnStartRef.current = performance.now();
    setMode("listening");
  }

  function endTurn() {
    setMode("thinking");
    try {
      recorderRef.current?.stop(); // -> handleTurnStop
    } catch {
      beginListening();
    }
  }

  function handleTurnStop() {
    const rec = recorderRef.current;
    const blob = new Blob(chunksRef.current, { type: rec?.mimeType || "audio/webm" });
    if (!activeRef.current) return;
    if (blob.size < 1400) {
      beginListening(); // nothing really said
      return;
    }
    upload(blob);
  }

  async function upload(blob: Blob) {
    setMode("thinking");
    try {
      const form = new FormData();
      form.append("clip", blob, "turn.webm");
      const res = await fetch(`${API_BASE}/api/voice`, { method: "POST", body: form });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();

      onExchange?.({
        transcript: data.transcript,
        reply: data.reply,
        products: data.products,
        cart: data.cart,
        checkout: data.checkout,
      });

      if (data.audio_b64) {
        playReply(data.audio_b64, data.audio_mime || "audio/wav");
      } else {
        setError("No speech came back (TTS may not be set up — check the server log).");
        afterReply();
      }
    } catch (err) {
      setError(
        (err instanceof Error ? err.message : "Voice request failed") +
          ". Is `uvicorn server:app --port 8000` running?"
      );
      activeRef.current = false;
      setMode("error");
    }
  }

  function vadTick() {
    if (!activeRef.current) return;
    const analyser = analyserRef.current;
    if (analyser) {
      const buf = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buf.length);
      const now = performance.now();
      const mode = modeRef.current;

      if (mode === "listening" || mode === "capturing") {
        if (rms > SPEECH_ON) {
          lastVoiceRef.current = now;
          if (mode === "listening") {
            speechStartRef.current = now;
            setMode("capturing");
          }
        } else if (rms > SPEECH_OFF && mode === "capturing") {
          lastVoiceRef.current = now; // still trailing off, not silence yet
        }

        if (modeRef.current === "capturing") {
          const spoke = now - speechStartRef.current;
          const quiet = now - lastVoiceRef.current;
          if ((quiet > SILENCE_MS && spoke > MIN_SPEECH_MS) || now - turnStartRef.current > MAX_TURN_MS) {
            endTurn();
          }
        }
      } else if (mode === "speaking") {
        // barge-in: talk over the agent to cut it off
        bargeRef.current = rms > BARGE_ON ? bargeRef.current + 1 : 0;
        if (bargeRef.current >= BARGE_FRAMES) {
          audioRef.current?.pause();
          bargeRef.current = 0;
          beginListening();
        }
      }
    }
    rafRef.current = requestAnimationFrame(vadTick);
  }

  async function startCall() {
    setError("");
    setReplayReady(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      const Ctx: typeof AudioContext =
        window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx();
      await ctx.resume();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.4;
      source.connect(analyser);
      ctxRef.current = ctx;
      analyserRef.current = analyser;

      setMic("granted");
      activeRef.current = true;
      rafRef.current = requestAnimationFrame(vadTick);
      beginListening();
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      setMic(name === "NotAllowedError" ? "denied" : "prompt");
      setError(
        name === "NotAllowedError" || name === "SecurityError"
          ? "Microphone access was blocked. Allow it for this site, then start the call again."
          : name === "NotFoundError"
            ? "No microphone was found."
            : (err instanceof Error && err.message) || "Could not start the call."
      );
      setMode("error");
    }
  }

  const endCall = useCallback(() => {
    activeRef.current = false;
    cancelAnimationFrame(rafRef.current);
    try {
      if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    } catch {
      /* noop */
    }
    audioRef.current?.pause();
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    ctxRef.current?.close().catch(() => {});
    ctxRef.current = null;
    analyserRef.current = null;
    setReplayReady(false);
    setMode("idle");
  }, [setMode]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      endCall();
    };
  }, [onClose, endCall]);

  // ---- render ----------------------------------------------------------

  const inCall = phase !== "idle" && phase !== "error";

  const status =
    phase === "listening"
      ? "Listening…"
      : phase === "capturing"
        ? "Go on…"
        : phase === "thinking"
          ? "Thinking…"
          : phase === "speaking"
            ? "Speaking…"
            : phase === "error"
              ? "Call ended on an error"
              : replayReady
                ? "Tap to hear the reply"
                : "Ready when you are";

  const wavesFast = phase === "capturing" || phase === "speaking";

  return (
    <div className="voice" role="dialog" aria-modal="true" aria-label="Voice mode">
      <GradientWaves
        className="voice__waves"
        horizonColor="#2b2e28"
        waveColor="#7f8768"
        crestColor="#f6dde2"
        speed={wavesFast ? 0.55 : 0.28}
        amplitude={2.2}
        waveScale={0.6}
        waveRatio={0.9}
        swell={35}
        turbulence={20}
        tilt={1.11}
        zoom={1.0}
        height={5.5}
        fogDepth={20}
        detail="medium"
        brightness={1.2}
        opacity={1.0}
        mouseInteraction
        parallaxStrength={0.4}
        grain
        grainIntensity={0.04}
      />
      <div className="voice__scrim" aria-hidden="true" />

      <button className="voice__close" onClick={onClose} aria-label="Exit voice mode">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>

      <div className="voice__center">
        <span className="voice__eyebrow">Voice mode</span>

        {mic !== "granted" && !inCall ? (
          <>
            <span className="voice__gate-icon" aria-hidden="true">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
                <rect x="9" y="2.5" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.6" />
                <path
                  d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            <p className="voice__status">
              {mic === "denied" ? "Microphone blocked" : "Microphone access needed"}
            </p>
            <button className="voice__grant" onClick={requestMic} disabled={requesting || insecure}>
              {requesting
                ? "Waiting…"
                : insecure
                  ? "Unavailable here"
                  : mic === "denied" || error
                    ? "Try again"
                    : "Allow microphone"}
            </button>
            <p className={`voice__hint ${mic === "denied" || error ? "voice__hint--error" : ""}`}>
              {error ||
                "Agentry needs your mic for the call. Your browser will ask you to allow it."}
            </p>
          </>
        ) : (
          <>
            <button
              className={`voice__mic ${phase === "capturing" ? "is-listening" : ""} ${
                phase === "thinking" ? "is-busy" : ""
              } ${phase === "speaking" ? "is-speaking" : ""} ${replayReady ? "is-replay" : ""}`}
              onClick={
                replayReady
                  ? replay
                  : !inCall
                    ? startCall
                    : undefined
              }
              disabled={inCall && !replayReady}
              aria-label={
                replayReady ? "Play the reply" : inCall ? "Call in progress" : "Start the call"
              }
            >
              <span className="voice__mic-ring" aria-hidden="true" />
              <span className="voice__mic-ring voice__mic-ring--2" aria-hidden="true" />
              {replayReady ? (
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M8 5v14l11-7z" fill="currentColor" />
                </svg>
              ) : (
                <svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <rect x="9" y="2.5" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.6" />
                  <path
                    d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                  />
                </svg>
              )}
            </button>

            <p className="voice__status">{status}</p>

            {inCall && (
              <button className="voice__end" onClick={endCall}>
                End call
              </button>
            )}

            {error && <p className="voice__hint voice__hint--error">{error}</p>}
          </>
        )}
      </div>
    </div>
  );
}
