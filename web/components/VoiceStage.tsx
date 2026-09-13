"use client";

import ProductTiles, { type ProductBatch } from "@/components/ProductTiles";
import PaymentCard, { type Cart, type CheckoutInfo } from "@/components/PaymentCard";
import WebThreads from "@/components/WebThreads";

interface Product {
  name: string;
  price: string;
  url: string;
  image?: string;
}

/**
 * The right-hand pane while voice mode is on. Voice replies can't drop a
 * product grid or a bill into an audio stream, so the visual half of the
 * turn lands here instead: something to pick from, an order to confirm, or
 * a placed-order receipt. Falls back to a calm idle panel between turns.
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
}: {
  products: ProductBatch[];
  cart?: Cart | null;
  checkout?: CheckoutInfo | null;
  onAdd: (item: Product) => void;
  addingUrl: string | null;
  onConfirmPay: () => void;
  onCancelPay: () => void;
  paying: boolean;
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
    </div>
  );
}
