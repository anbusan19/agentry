"use client";

import { useEffect, useRef } from "react";
import ProductTiles, { type ProductBatch } from "@/components/ProductTiles";
import PaymentCard, { type Cart, type CheckoutInfo } from "@/components/PaymentCard";
import WebThreads from "@/components/WebThreads";

interface Product {
  name: string;
  price: string;
  url: string;
  image?: string;
}

const BAR_COUNT = 7;

/**
 * Small audio-level visualizer for while the agent is speaking. Reads the
 * playback AnalyserNode directly via its own requestAnimationFrame loop and
 * writes bar heights straight to the DOM (not React state) — this runs
 * every frame, and pushing that through React would re-render the whole
 * stage 60 times a second for no reason.
 */
function AudioBars({ analyser, active }: { analyser: AnalyserNode | null; active: boolean }) {
  const barRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const rafRef = useRef(0);

  useEffect(() => {
    if (!analyser || !active) {
      cancelAnimationFrame(rafRef.current);
      barRefs.current.forEach((bar) => bar && (bar.style.transform = "scaleY(0.16)"));
      return;
    }

    const data = new Uint8Array(analyser.frequencyBinCount);
    // Group the (few, since fftSize is small) frequency bins into BAR_COUNT
    // buckets and average each — a plain low-res level meter, not a real
    // spectrum display.
    const bucketSize = Math.max(1, Math.floor(data.length / BAR_COUNT));

    const tick = () => {
      analyser.getByteFrequencyData(data);
      for (let i = 0; i < BAR_COUNT; i++) {
        const bar = barRefs.current[i];
        if (!bar) continue;
        let sum = 0;
        const start = i * bucketSize;
        for (let j = start; j < start + bucketSize && j < data.length; j++) sum += data[j];
        const level = sum / bucketSize / 255; // 0..1
        // Floor so idle bars still read as "a bar", not a flat line.
        bar.style.transform = `scaleY(${Math.max(0.16, level)})`;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(rafRef.current);
  }, [analyser, active]);

  return (
    <div className={`vstage__bars ${active ? "is-active" : ""}`} aria-hidden="true">
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <span
          key={i}
          className="vstage__bar"
          ref={(el) => {
            barRefs.current[i] = el;
          }}
        />
      ))}
    </div>
  );
}

/**
 * The right-hand pane while voice mode is on. Voice replies can't drop a
 * product grid or a bill into an audio stream, so the visual half of the
 * turn lands here instead: something to pick from, an order to confirm, or
 * a placed-order receipt. Falls back to a calm idle panel between turns.
 * Also carries the two other bits of live voice state that don't belong on
 * the mic overlay itself: which tool is currently running, and a small
 * audio-level readout while the agent is speaking.
 */
export default function VoiceStage({
  products,
  cart,
  checkout,
  onAdd,
  addingUrl,
  onConfirmPay,
  onCancelPay,
  paying,
  currentTool,
  speaking,
  analyser,
}: {
  products: ProductBatch[];
  cart?: Cart | null;
  checkout?: CheckoutInfo | null;
  onAdd: (item: Product) => void;
  addingUrl: string | null;
  onConfirmPay: () => void;
  onCancelPay: () => void;
  paying: boolean;
  /** Name of the tool currently running, if any — e.g. "search_products". */
  currentTool?: string | null;
  /** Whether the agent's spoken reply is currently playing. */
  speaking?: boolean;
  /** The voice call's playback AnalyserNode, or null outside a call. */
  analyser?: AnalyserNode | null;
}) {
  const showPayment = Boolean(checkout) || Boolean(cart && cart.items.length > 0);
  const showProducts = !showPayment && products.length > 0;

  return (
    <div className="vstage">
      {/* Woven-thread backdrop, retinted to the project's petal / sage /
          paper palette — matches VoiceMode's GradientWaves so the two voice
          surfaces read as one. Deliberately dim; content sits on top. */}
      <WebThreads
        className="vstage__threads"
        color1="#f6dde2"
        color2="#7f8768"
        color3="#f2efe6"
        speed={0.14}
        threadCount={5}
        frequency={4.0}
        spread={0.16}
        taper={1.0}
        position={0.5}
        fanMode="center"
        glow={0.018}
        falloff={0.62}
        thickness={1.1}
        brightness={0.5}
        opacity={0.5}
        mirror
        grain
        grainIntensity={0.035}
        mouseInteraction
        mouseStrength={0.25}
      />
      <div className="vstage__scrim" aria-hidden="true" />

      <div className="vstage__head">
        <span className="vstage__title">Agentry Vision</span>
        {currentTool && (
          <span className="vstage__tool">
            <span className="vstage__tool-dot" aria-hidden="true" />
            Using {currentTool}…
          </span>
        )}
      </div>

      <div className="vstage__body">
        {showPayment && (
          <PaymentCard
            cart={cart}
            checkout={checkout}
            onConfirm={checkout ? undefined : onConfirmPay}
            onCancel={checkout ? undefined : onCancelPay}
            busy={paying}
            variant="stage"
          />
        )}

        {showProducts && (
          <ProductTiles batches={products} onAdd={onAdd} addingUrl={addingUrl} />
        )}
      </div>

      <AudioBars analyser={analyser ?? null} active={Boolean(speaking && analyser)} />
    </div>
  );
}
