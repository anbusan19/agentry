"use client";

import ProductTiles, { type ProductBatch } from "@/components/ProductTiles";
import PaymentCard, { type Cart, type CheckoutInfo } from "@/components/PaymentCard";

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
      <div className="vstage__head">
        <span className="vstage__eyebrow">Voice mode</span>
        <span className="vstage__title">
          {showPayment
            ? checkout?.status === "paid"
              ? "Order confirmed"
              : "Review & confirm"
            : showProducts
              ? "Pick one to add"
              : "Listening"}
        </span>
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

        {!showPayment && !showProducts && (
          <div className="vstage__idle">
            <span className="vstage__pulse" aria-hidden="true" />
            <p>Talk to Agentry. Anything it wants to show you — choices, a cart, a receipt — appears here.</p>
          </div>
        )}
      </div>
    </div>
  );
}
