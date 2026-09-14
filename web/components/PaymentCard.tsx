"use client";

// Matches every other component's convention (ChatPanel, KnowledgeGraph,
// SettingsModal, VoiceMode) for reaching the FastAPI bridge — needed here
// because qr_image_path is served by that backend (GET /api/qr/<file>),
// not by the Next.js dev server the browser is actually loaded from.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Cart {
  items: { name: string; quantity: number; price: string | null }[];
  total: string | null;
}

export interface CheckoutInfo {
  status: string;
  amount_paid?: number | null;
  order_id?: string | null;
  note?: string | null;
  error?: string | null;
  // Blinkit's payment_method="upi" path (tools/checkout.py): Blinkit Money
  // is app-exclusive, so this is a live QR code the user scans themselves
  // rather than a completed payment. qr_image_path is a local filesystem
  // path from the tool result — served over HTTP via GET /api/qr/<file>.
  qr_image_path?: string | null;
  amount_due?: number | null;
}

/**
 * The order-summary / payment surface, rendered the same way inline in the
 * chat transcript and enlarged on the voice stage (`variant`).
 *
 * - a completed `checkout` (status "paid") -> a receipt
 * - any other `checkout` status -> the problem, plainly stated
 * - otherwise a `cart` -> an order summary with a place-order action
 *
 * `onConfirm` / `onCancel` drive the pending case; when they're omitted
 * (e.g. a historical message) the card is read-only.
 */
export default function PaymentCard({
  cart,
  checkout,
  onConfirm,
  onCancel,
  busy = false,
  variant = "chat",
}: {
  cart?: Cart | null;
  checkout?: CheckoutInfo | null;
  onConfirm?: () => void;
  onCancel?: () => void;
  busy?: boolean;
  variant?: "chat" | "stage";
}) {
  const cls = `paycard paycard--${variant}`;

  if (checkout && checkout.status === "paid") {
    return (
      <div className={`${cls} paycard--paid`}>
        <div className="paycard__badge">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3.5 8.5l3 3 6-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Order placed
        </div>
        {checkout.amount_paid != null && (
          <p className="paycard__amount">₹{checkout.amount_paid}</p>
        )}
        {checkout.order_id && <p className="paycard__meta">Order {checkout.order_id}</p>}
        <p className="paycard__meta">Paid from platform wallet balance.</p>
      </div>
    );
  }

  if (checkout && checkout.status === "awaiting_manual_payment" && checkout.qr_image_path) {
    const filename = checkout.qr_image_path.split("/").pop();
    return (
      <div className={`${cls} paycard--pending`}>
        <div className="paycard__badge paycard__badge--warn">Scan to pay</div>
        <p className="paycard__meta">
          Blinkit Money isn&rsquo;t available on the web, so this is a live UPI QR code &mdash;
          scan it with your banking app to pay.
        </p>
        {checkout.amount_due != null && <p className="paycard__amount">₹{checkout.amount_due}</p>}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`${API_BASE}/api/qr/${filename}`}
          alt="Blinkit UPI payment QR code"
          className="paycard__qr"
        />
        <p className="paycard__meta">This code is time-limited. The order isn&rsquo;t placed until you pay.</p>
      </div>
    );
  }

  if (checkout && checkout.status !== "paid") {
    const msg =
      checkout.error ||
      checkout.note ||
      (checkout.status === "insufficient_balance"
        ? "No wallet balance available to pay from — the order was not placed."
        : checkout.status === "wallet_not_available"
        ? "No platform wallet option was available at checkout — the order was not placed."
        : "Checkout did not complete.");
    return (
      <div className={`${cls} paycard--problem`}>
        <div className="paycard__badge paycard__badge--warn">Checkout stopped</div>
        <p className="paycard__meta">{msg}</p>
      </div>
    );
  }

  if (cart && cart.items.length > 0) {
    return (
      <div className={cls}>
        <div className="paycard__badge">Confirm order</div>
        <ul className="paycard__items">
          {cart.items.map((it, i) => (
            <li key={i}>
              <span className="paycard__item-name">
                {it.quantity > 1 && <span className="paycard__qty">{it.quantity}&times;</span>}
                {it.name}
              </span>
              {it.price && <span className="paycard__item-price">{it.price}</span>}
            </li>
          ))}
        </ul>
        {cart.total && (
          <div className="paycard__total">
            <span>To pay</span>
            <span>{cart.total}</span>
          </div>
        )}
        {(onConfirm || onCancel) && (
          <div className="paycard__actions">
            {onCancel && (
              <button className="paycard__btn paycard__btn--ghost" onClick={onCancel} disabled={busy}>
                Keep shopping
              </button>
            )}
            {onConfirm && (
              <button className="paycard__btn" onClick={onConfirm} disabled={busy}>
                {busy ? "Placing…" : "Place order"}
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  return null;
}
