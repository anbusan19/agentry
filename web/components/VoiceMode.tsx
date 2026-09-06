"use client";

import { useEffect, useState } from "react";
import GradientWaves from "@/components/GradientWaves";

/**
 * Conversational voice surface that overlays the chat panel (the knowledge
 * graph pane stays visible beside it). The animated backdrop is React Bits'
 * GradientWaves, retinted to the project's moss / petal palette. The mic
 * control is a UI stub for now — the STT -> agent -> TTS pipeline (Pipecat +
 * AWS Transcribe/Polly) lands behind it later.
 */
export default function VoiceMode({ onClose }: { onClose: () => void }) {
  const [listening, setListening] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="voice" role="dialog" aria-modal="true" aria-label="Voice mode">
      <GradientWaves
        className="voice__waves"
        horizonColor="#2b2e28"
        waveColor="#7f8768"
        crestColor="#f6dde2"
        speed={0.28}
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
        <span className="voice__eyebrow">Voice mode &middot; preview</span>

        <button
          className={`voice__mic ${listening ? "is-listening" : ""}`}
          onClick={() => setListening((v) => !v)}
          aria-pressed={listening}
          aria-label={listening ? "Stop listening" : "Start listening"}
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

        <p className="voice__status">{listening ? "Listening…" : "Tap to speak"}</p>
        <p className="voice__hint">
          Talk to Agentry to build and place a grocery order. Speech pipeline
          integration in progress.
        </p>
      </div>
    </div>
  );
}
