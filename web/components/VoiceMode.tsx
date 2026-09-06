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

type Phase = "idle" | "recording" | "thinking" | "speaking" | "error";

/**
 * Conversational voice surface that overlays the chat panel (the voice
 * stage takes over the pane beside it). One recorded clip per turn: tap to
 * start, tap to send. It goes to server.py's /api/voice — local Whisper,
 * the shared agent, local TTS — and the spoken reply plays back here while
 * the structured result (products / cart / receipt) lands on the stage via
 * onExchange.
 */
export default function VoiceMode({
  onClose,
  onExchange,
}: {
  onClose: () => void;
  onExchange?: (x: VoiceExchange) => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [caption, setCaption] = useState("");
  const [error, setError] = useState("");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const cleanup = useCallback(() => {
    try {
      recorderRef.current?.state === "recording" && recorderRef.current.stop();
    } catch {
      /* noop */
    }
    audioRef.current?.pause();
    stopTracks();
  }, [stopTracks]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      cleanup();
    };
  }, [onClose, cleanup]);

  async function upload(blob: Blob) {
    setPhase("thinking");
    setCaption("Thinking…");
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
      setCaption(data.reply || "");

      if (data.audio_b64) {
        const audio = new Audio(`data:${data.audio_mime || "audio/wav"};base64,${data.audio_b64}`);
        audioRef.current = audio;
        setPhase("speaking");
        audio.onended = () => setPhase("idle");
        audio.onerror = () => setPhase("idle");
        await audio.play().catch(() => setPhase("idle"));
      } else {
        setPhase("idle");
      }
    } catch (err) {
      setError(
        (err instanceof Error ? err.message : "Voice request failed") +
          ". Is `uvicorn server:app --port 8000` running?"
      );
      setPhase("error");
    }
  }

  async function startRecording() {
    setError("");
    setCaption("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      recorder.onstop = () => {
        stopTracks();
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        if (blob.size > 0) upload(blob);
        else setPhase("idle");
      };
      recorder.start();
      recorderRef.current = recorder;
      setPhase("recording");
      setCaption("Listening…");
    } catch {
      setError("Microphone access was blocked. Allow it in the browser and try again.");
      setPhase("error");
    }
  }

  function stopRecording() {
    try {
      recorderRef.current?.stop();
    } catch {
      setPhase("idle");
    }
  }

  function onMicTap() {
    if (phase === "recording") stopRecording();
    else if (phase === "idle" || phase === "error") startRecording();
    else if (phase === "speaking") {
      audioRef.current?.pause();
      setPhase("idle");
    }
  }

  const micLabel =
    phase === "recording"
      ? "Stop and send"
      : phase === "speaking"
        ? "Stop playback"
        : "Start talking";
  const status =
    phase === "recording"
      ? "Listening… tap to send"
      : phase === "thinking"
        ? "Working on it"
        : phase === "speaking"
          ? "Speaking"
          : phase === "error"
            ? "Something went wrong"
            : "Tap to talk";

  return (
    <div className="voice" role="dialog" aria-modal="true" aria-label="Voice mode">
      <GradientWaves
        className="voice__waves"
        horizonColor="#2b2e28"
        waveColor="#7f8768"
        crestColor="#f6dde2"
        speed={phase === "recording" || phase === "speaking" ? 0.5 : 0.28}
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
          <path
            d="M3.5 3.5l9 9M12.5 3.5l-9 9"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      </button>

      <div className="voice__center">
        <span className="voice__eyebrow">Voice mode</span>

        <button
          className={`voice__mic ${phase === "recording" ? "is-listening" : ""} ${
            phase === "thinking" ? "is-busy" : ""
          }`}
          onClick={onMicTap}
          disabled={phase === "thinking"}
          aria-label={micLabel}
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
        {error ? (
          <p className="voice__hint voice__hint--error">{error}</p>
        ) : caption ? (
          <p className="voice__hint">{caption}</p>
        ) : (
          <p className="voice__hint">
            Talk to Agentry like you would a shopkeeper. It builds the order and shows
            what it finds on the right.
          </p>
        )}
      </div>
    </div>
  );
}
