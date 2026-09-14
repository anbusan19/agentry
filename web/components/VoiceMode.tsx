"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import GradientWaves from "@/components/GradientWaves";
import type { ProductBatch } from "@/components/ProductTiles";
import type { Cart, CheckoutInfo } from "@/components/PaymentCard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// http(s) -> ws(s), same host/port as the REST API.
const WS_VOICE_URL = `${API_BASE.replace(/^http/, "ws")}/ws/voice`;

export interface VoiceExchange {
  transcript: string;
  reply: string;
  products?: ProductBatch[];
  cart?: Cart | null;
  checkout?: CheckoutInfo | null;
}

type Phase = "idle" | "listening" | "capturing" | "thinking" | "speaking" | "error";
type MicPermission = "unknown" | "prompt" | "granted" | "denied";

// Nova Sonic's fixed wire format (tools/_session.py-adjacent note: this is
// the model's own requirement, not a choice made here — see
// voice/bidi_voice.py's module docstring). Both capture and playback run
// on one AudioContext opened at this rate, so no resampling is needed on
// either side of the pipe.
const SAMPLE_RATE = 16000;
const CAPTURE_CHUNK_SAMPLES = 320; // 20ms @ 16kHz — small enough for low latency, big enough not to spam the socket

// Inline AudioWorkletProcessor, loaded via a Blob URL rather than a static
// file: keeps the whole capture pipeline in this one component instead of
// wiring an extra asset through Next's public/ dir. Runs on the audio
// render thread; batches Float32 samples into CAPTURE_CHUNK_SAMPLES-sized
// frames, converts to PCM16LE, and posts each frame back to the main
// thread as a transferable ArrayBuffer (no copy).
const CAPTURE_WORKLET_SRC = `
class PCMCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
  }
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) {
      for (let i = 0; i < channel.length; i++) this._buffer.push(channel[i]);
      while (this._buffer.length >= ${CAPTURE_CHUNK_SAMPLES}) {
        const chunk = this._buffer.splice(0, ${CAPTURE_CHUNK_SAMPLES});
        const pcm16 = new Int16Array(chunk.length);
        for (let i = 0; i < chunk.length; i++) {
          const s = Math.max(-1, Math.min(1, chunk[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
      }
    }
    return true;
  }
}
registerProcessor("pcm-capture-processor", PCMCaptureProcessor);
`;

function pcm16BufferToAudioBuffer(ctx: AudioContext, data: ArrayBuffer): AudioBuffer {
  const int16 = new Int16Array(data);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    const v = int16[i];
    float32[i] = v / (v < 0 ? 0x8000 : 0x7fff);
  }
  const buffer = ctx.createBuffer(1, float32.length || 1, SAMPLE_RATE);
  buffer.copyToChannel(float32, 0);
  return buffer;
}

/**
 * Real-time voice mode: a persistent WebSocket to server.py's /ws/voice,
 * streaming raw PCM audio both ways through Amazon Nova 2 Sonic — see
 * voice/bidi_voice.py for the wire format and the full rationale. Not a
 * record-a-clip-then-upload flow like the old version: the mic streams
 * continuously once the call starts, Nova Sonic does its own voice-activity
 * turn detection server-side (no client-side VAD needed here anymore), and
 * its audio reply streams back and plays as it arrives rather than waiting
 * for a whole clip. Barge-in works the same way — interrupt the model by
 * talking over it — but the *detection* now happens on Nova Sonic's side;
 * the frontend's job on an interruption is just to stop playback fast.
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
  const [statusHint, setStatusHint] = useState("");

  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Playback scheduling state — see scheduleAudio/stopPlayback below.
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const nextStartTimeRef = useRef(0);

  // This turn's accumulated transcript, reset after each onExchange call.
  const userTextRef = useRef("");
  const replyTextRef = useRef("");

  const activeRef = useRef(false);
  const onExchangeRef = useRef(onExchange);
  onExchangeRef.current = onExchange;

  // ---- permission gate (unchanged from the record-a-clip version) ------

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

  // ---- playback: gapless streaming via back-to-back scheduled buffers --

  const scheduleAudio = useCallback((data: ArrayBuffer) => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const buffer = pcm16BufferToAudioBuffer(ctx, data);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    const startAt = Math.max(ctx.currentTime, nextStartTimeRef.current);
    source.start(startAt);
    nextStartTimeRef.current = startAt + buffer.duration;
    activeSourcesRef.current.push(source);
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source);
    };
  }, []);

  const stopPlayback = useCallback(() => {
    activeSourcesRef.current.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    });
    activeSourcesRef.current = [];
    if (ctxRef.current) nextStartTimeRef.current = ctxRef.current.currentTime;
  }, []);

  // ---- WebSocket event handling -----------------------------------------

  const handleServerEvent = useCallback(
    (payload: Record<string, unknown>) => {
      switch (payload.type) {
        case "transcript": {
          const text = String(payload.text ?? "");
          if (payload.role === "user") {
            userTextRef.current = text;
            if (!payload.is_final) setPhase("capturing");
          } else {
            replyTextRef.current = text;
          }
          return;
        }
        case "tool_use": {
          setStatusHint(payload.name ? `Using ${payload.name}…` : "");
          setPhase("thinking");
          return;
        }
        case "response_start": {
          setPhase("speaking");
          setStatusHint("");
          return;
        }
        case "interruption": {
          // Nova Sonic detected the user talking over it — stop playback
          // immediately, the model has already stopped generating.
          stopPlayback();
          setPhase("capturing");
          return;
        }
        case "response_complete": {
          setPhase(activeRef.current ? "listening" : "idle");
          setStatusHint("");
          if (userTextRef.current || replyTextRef.current) {
            onExchangeRef.current?.({
              transcript: userTextRef.current,
              reply: replyTextRef.current,
            });
            userTextRef.current = "";
            replyTextRef.current = "";
          }
          return;
        }
        case "turn_data": {
          // Arrives just before response_complete (see bidi_voice.py) —
          // fold it into the same onExchange call rather than firing a
          // second, partial one.
          onExchangeRef.current?.({
            transcript: userTextRef.current,
            reply: replyTextRef.current,
            products: (payload.products as ProductBatch[]) ?? [],
            cart: (payload.cart as Cart | null) ?? null,
            checkout: (payload.checkout as CheckoutInfo | null) ?? null,
          });
          userTextRef.current = "";
          replyTextRef.current = "";
          return;
        }
        case "connection_restart": {
          setStatusHint("Reconnecting…");
          return;
        }
        case "connection_close": {
          endCall();
          return;
        }
        case "error": {
          setError(String(payload.message ?? "The voice session hit an error."));
          endCall();
          return;
        }
        default:
          return;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stopPlayback]
  );

  // ---- call lifecycle ----------------------------------------------------

  async function startCall() {
    setError("");
    setStatusHint("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      setMic("granted");

      const Ctx: typeof AudioContext =
        window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx({ sampleRate: SAMPLE_RATE });
      await ctx.resume();
      ctxRef.current = ctx;
      nextStartTimeRef.current = ctx.currentTime;

      const workletUrl = URL.createObjectURL(new Blob([CAPTURE_WORKLET_SRC], { type: "application/javascript" }));
      await ctx.audioWorklet.addModule(workletUrl);
      URL.revokeObjectURL(workletUrl);

      const ws = new WebSocket(WS_VOICE_URL);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        // Mic capture only starts once the socket is actually open, so no
        // audio is dropped on the floor before the server can receive it.
        const source = ctx.createMediaStreamSource(stream);
        const worklet = new AudioWorkletNode(ctx, "pcm-capture-processor");
        worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
          if (ws.readyState === WebSocket.OPEN) ws.send(e.data);
        };
        source.connect(worklet);
        micSourceRef.current = source;
        workletNodeRef.current = worklet;

        activeRef.current = true;
        setPhase("listening");
      };

      ws.onmessage = (e: MessageEvent<string | ArrayBuffer>) => {
        if (typeof e.data === "string") {
          try {
            handleServerEvent(JSON.parse(e.data));
          } catch {
            /* malformed frame — ignore rather than crash the call */
          }
        } else {
          scheduleAudio(e.data);
        }
      };

      ws.onerror = () => {
        setError("Lost the voice connection. Is `uvicorn server:app --port 8000` running?");
        endCall();
      };

      ws.onclose = (e) => {
        if (activeRef.current && e.code !== 1000) {
          setError("The voice connection closed unexpectedly.");
        }
        endCall();
      };
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
      setPhase("error");
    }
  }

  const endCall = useCallback(() => {
    activeRef.current = false;
    stopPlayback();

    try {
      wsRef.current?.close(1000);
    } catch {
      /* noop */
    }
    wsRef.current = null;

    workletNodeRef.current?.port.close();
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    micSourceRef.current?.disconnect();
    micSourceRef.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    ctxRef.current?.close().catch(() => {});
    ctxRef.current = null;

    userTextRef.current = "";
    replyTextRef.current = "";
    setStatusHint("");
    setPhase((p) => (p === "error" ? "error" : "idle"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopPlayback]);

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
          ? statusHint || "Thinking…"
          : phase === "speaking"
            ? "Speaking…"
            : phase === "error"
              ? "Call ended on an error"
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
              } ${phase === "speaking" ? "is-speaking" : ""}`}
              onClick={!inCall ? startCall : undefined}
              disabled={inCall}
              aria-label={inCall ? "Call in progress" : "Start the call"}
            >
              <span className="voice__mic-ring" aria-hidden="true" />
              <span className="voice__mic-ring voice__mic-ring--2" aria-hidden="true" />
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <rect x="9" y="2.5" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.6" />
                <path
                  d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
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
