"""
tools/checkout.py

Completes the current cart's checkout: schedules a delivery slot if needed,
pays, and places the order. This is the only tool in the project that can
spend real money (Zepto) or hand the user a live payment request (Blinkit),
so it requires an explicit confirm=True — the agent must have a real reason
to believe the user wants this specific order placed (a fresh
check_wallet_balance/view_cart in the same turn, or an explicit user
instruction) before passing it, never as a default.

Zepto's path was ported from the pre-existing prototype this hackathon
submission builds on (see README's Disclosure section) for the address/
wallet-selection/place-order sequence, then adapted to the current site's
actual DOM (data-testid selectors, aria-labelled stepper buttons, and a
delivery-slot-scheduling step the original didn't need to handle).

NOTE: the path from "Click to Pay" through wallet selection to a placed
order was not exercised against a live cart during development — that
click sits right at the boundary of real settlement, and testing stopped
short of it deliberately. Verify this against a real cart with a small
order before trusting it unattended.

Blinkit is a genuinely different shape, confirmed live via screenshots of
the real flow: the cart drawer (opened from the cart icon on blinkit.com,
not a separate page) shows a "Proceed To Pay" button with the grand total;
clicking it navigates straight to blinkit.com/checkout, which shows
"Select Payment Method" directly — no separate delivery-slot-scheduling
step the way Zepto has one. That screen offers Wallets, "Add credit or
debit cards", Netbanking, UPI, Cash (disabled between 12 AM and 6 AM), and
Pay Later — no Blinkit Money anywhere on it. Blinkit Money is
app-exclusive; there is no automated way to pay from it on web, full stop,
so checkout() takes a payment_method argument for Blinkit instead of
assuming a wallet:

  - payment_method="blinkit_money" (default, for parity with Zepto's
    wallet-first flow): doesn't attempt payment at all — it can't be paid
    from web — and returns status "insufficient_balance" immediately, the
    same shape the agent already treats as "tell the user, don't place the
    order" for a real low-balance case.
  - payment_method="upi": the one payment path that's actually confirmed
    to work here. Opens the UPI section on the payment screen, clicks
    "Generate QR", waits for the QR code to render, and screenshots that
    panel to a local PNG (tools/.qr_codes/, gitignored — *.png is
    gitignored repo-wide too) rather than trying to place the order itself.
    Nothing about UPI payment can be automated further: it requires a
    human to scan the code with their own banking app. So this tool's job
    ends at "here is a live, time-limited QR" — it returns
    status="awaiting_manual_payment" with the image path, and the agent is
    expected to hand that image to the user via notify_user(image_path=...)
    so they can actually pay. There's no automated confirmation that the
    payment went through afterward; record_purchase should only be called
    once the user confirms (via notify_user reply channel, i.e. out of
    band) that they completed it — this tool cannot know on its own.

The actual work happens in _checkout_impl, run on the single dedicated
Playwright thread via run_on_playwright_thread — see tools/_session.py's
module docstring for why that's required (not optional) whenever a tool
touches a Page.
"""

import re
import time
from pathlib import Path
from typing import Optional

from strands import tool

from knowledge.budget import record_spend
from tools._session import PLATFORMS, get_page, js_click, run_on_playwright_thread

_WALLET_PATTERN = r"zepto cash|zepto wallet|wallet balance|platform cash|gift card"

QR_DIR = Path(__file__).parent / ".qr_codes"


@tool
def checkout(confirm: bool = False, platform: str = "zepto", payment_method: str = "blinkit_money") -> dict:
    """
    Complete checkout for whatever is currently in the cart: schedule a
    delivery slot if one is required, then pay and place the order.

    On Zepto this pays from the platform wallet (Zepto Cash) and places
    the order directly — this spends real money immediately.

    On Blinkit, Blinkit Money is app-exclusive and can't be paid from on
    web, so this branches on payment_method instead:
      - "blinkit_money" (the default): returns status="insufficient_balance"
        right away, without attempting anything — there's no wallet to pay
        from on web. Don't retry this; switch to "upi".
      - "upi": generates a live UPI QR code on Blinkit's actual payment
        screen and returns it as an image for the user to scan and pay
        themselves. This does NOT place the order or spend money itself —
        a human has to complete the payment out of band. Don't call
        record_purchase off this result; only do that once the user
        confirms the payment actually went through.

    Only call this with confirm=True, and only when there's a clear reason
    to believe this exact order (checked via view_cart / check_wallet_balance
    moments earlier) is what the user wants placed right now.

    Args:
        confirm: Must be explicitly True to do anything. Defaults to False
            so an accidental or speculative call can't place an order or
            generate a payment request.
        platform: Which storefront — "zepto" (default) or "blinkit".
        payment_method: Blinkit only ("blinkit_money" default, or "upi").
            Ignored on Zepto, which always pays from Zepto Cash.

    Returns:
        A dict with status ("paid", "awaiting_manual_payment",
        "insufficient_balance", "wallet_not_available", "not_confirmed",
        or "error"). "paid" carries "amount_paid" and "order_id".
        "awaiting_manual_payment" carries "qr_image_path" (a local PNG to
        send to the user) and "amount_due".
    """
    return run_on_playwright_thread(_checkout_impl, confirm, platform, payment_method)


def _checkout_impl(confirm: bool, platform: str, payment_method: str) -> dict:
    if not confirm:
        return {
            "status": "not_confirmed",
            "note": "checkout requires confirm=True — nothing was done.",
        }
    if platform not in PLATFORMS:
        return {"status": "error", "error": f"Unknown platform {platform!r} — use one of {list(PLATFORMS)}."}

    storefront_url = PLATFORMS[platform]["url"]
    page = get_page(platform)
    try:
        if platform == "blinkit":
            reached = _reach_blinkit_payment_screen(page, storefront_url)
            if reached is not None:  # None = reached fine; a dict here is an early error/empty-cart result
                return reached
            return _pay_blinkit(page, payment_method)

        page.goto(f"{storefront_url}?cart=open", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_selector("text=Bill Summary", timeout=10000)

        js_click(page, "select delivery options|schedule delivery")
        page.wait_for_timeout(1500)
        if page.locator("text=Schedule your order").is_visible():
            page.locator("button, div").filter(has_text=re.compile(r"^\d{1,2}\s*-\s*\d{1,2}\s*(AM|PM)$")).first.click()
            page.wait_for_timeout(500)
            js_click(page, r"^confirm$")
            page.wait_for_timeout(1500)

        js_click(page, r"click to pay|proceed to pay|place order")
        page.wait_for_timeout(2000)

        return _pay_and_place_zepto(page, platform)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _reach_blinkit_payment_screen(page, storefront_url: str) -> Optional[dict]:
    """Get from wherever the page currently is to Blinkit's "Select Payment
    Method" screen, confirmed live via screenshots of the real flow: the
    cart drawer's "Proceed To Pay" button navigates straight to
    blinkit.com/checkout with no delivery-slot step in between. Two paths,
    in order:

      1. Direct navigation to /checkout — the simpler, more robust option
         if the site's router treats it as a real deep link (same reasoning
         view_cart.py already relies on for /cart being directly
         navigable). Confirmed to land on the right screen by checking for
         the actual "Select Payment Method" heading, not just a fixed wait.
      2. If that doesn't land on the payment screen (e.g. /checkout
         redirects back to /cart without a "Proceed To Pay" click having
         happened first), fall back to opening /cart and clicking the real
         button.

    Returns None once the payment screen is confirmed visible — the caller
    proceeds to _pay_blinkit(). Returns a result dict directly (empty cart,
    or neither path reaching the screen) when checkout should stop here."""
    page.goto(f"{storefront_url}/cart", wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(1200)
    if page.locator("text=/cart is empty|add items to your cart/i").is_visible():
        return {"status": "error", "error": "Cart is empty — nothing to check out."}

    page.goto(f"{storefront_url}/checkout", wait_until="domcontentloaded", timeout=40000)
    try:
        # Short timeout: a direct /checkout hit without an active checkout
        # session (i.e. without having actually clicked through from the
        # cart) may just redirect away rather than load the screen at all,
        # so this either succeeds fast or is expected to fail — no reason
        # to wait as long as the real click-driven wait below does.
        page.wait_for_selector("text=/select payment method/i", timeout=4000)
        return None
    except Exception:
        pass

    # Fallback: click through from the cart instead of trusting the direct
    # URL. Went back to /cart above already if the direct nav bounced us
    # somewhere else, so re-open it explicitly in case it didn't.
    if "/cart" not in page.url:
        page.goto(f"{storefront_url}/cart", wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(1000)
    # "Proceed To Pay" is the drawer's label (see the cart-icon-click
    # screenshot); view_cart.py's own docstring notes the standalone /cart
    # page instead ends its bill section with a bare "Proceed" — no "To
    # Pay" suffix. Match both rather than assuming one.
    if not js_click(page, r"proceed to pay|^proceed$|click to pay|place order"):
        return {"status": "error", "error": "Could not find the 'Proceed'/'Proceed To Pay' button on the cart."}

    try:
        page.wait_for_selector("text=/select payment method/i", timeout=15000)
    except Exception:
        return {
            "status": "error",
            "error": f"Payment screen never loaded after 'Proceed To Pay'. Current URL: {page.url}",
        }
    return None


def _pay_and_place_zepto(page, platform: str) -> dict:
    wallet_selected = page.evaluate(
        """(pattern) => {
            const re = new RegExp(pattern, 'i');
            const inputs = Array.from(document.querySelectorAll('input[type="radio"], input[type="checkbox"]'));
            for (const inp of inputs) {
                const label = inp.closest('label') || inp.parentElement;
                if (re.test(label?.textContent?.trim() ?? '')) {
                    inp.click();
                    return true;
                }
            }
            const el = Array.from(document.querySelectorAll('div, label, button, span, [role="radio"], [role="checkbox"]')).find(
                e => re.test(e.textContent?.trim() ?? '') && e.offsetParent !== null
            );
            if (el) { el.click(); return true; }
            return false;
        }""",
        _WALLET_PATTERN,
    )
    page.wait_for_timeout(1000)

    if not wallet_selected:
        return {"status": "wallet_not_available", "note": "No platform wallet option found — order was not placed."}

    placed = js_click(page, r"place order|pay now|confirm order|pay ₹")
    if not placed:
        return {"status": "error", "error": "Could not find the Place Order / Pay Now button."}

    page.wait_for_timeout(5000)

    confirmation = page.evaluate(
        """() => {
            const idText = document.body.innerText.match(/#?([A-Z0-9]{6,20})/)?.[1];
            const total = document.querySelector('[class*="total" i], [class*="amount" i]');
            return { orderId: idText || null, total: total?.textContent?.trim().slice(0, 30) || null };
        }"""
    )

    current_url = page.url
    is_confirmed = (
        "order" in current_url
        or "success" in current_url
        or "confirmed" in current_url
        or page.locator("text=/order placed|order confirmed|on the way/i").is_visible()
    )
    if not is_confirmed:
        return {"status": "error", "error": f"Order placement may have failed. URL: {current_url}"}

    match = re.search(r"[\d.]+", confirmation.get("total") or "")
    amount_paid = float(match.group(0)) if match else None
    if amount_paid is not None:
        record_spend(amount_paid)

    return {
        "status": "paid",
        "amount_paid": amount_paid,
        "order_id": f"ZP-{confirmation['orderId']}" if confirmation.get("orderId") else None,
    }


def _pay_blinkit(page, payment_method: str) -> dict:
    """Blinkit's payment screen (confirmed live via screenshots): Wallets,
    cards, Netbanking, UPI, Cash, Pay Later — no Blinkit Money. Only UPI is
    an actually-automatable path, and even that ends at "show the user a
    QR code" rather than placing the order, since scanning it requires a
    human's own banking app. Caller (_reach_blinkit_payment_screen) has
    already confirmed the "Select Payment Method" screen is up before this
    runs."""
    if payment_method != "upi":
        # "blinkit_money" (or anything else): there's nothing to select —
        # Blinkit Money doesn't appear on this screen at all. Don't guess
        # at a click; just report it the way a real low-balance wallet
        # would be reported, since the practical effect for the agent's
        # flow (stop, tell the user, don't place the order) is the same.
        return {
            "status": "insufficient_balance",
            "note": (
                "Blinkit Money is app-exclusive and not available on Blinkit's web "
                "storefront — there is no wallet to pay from here. Call checkout again "
                "with payment_method='upi' to generate a payable QR code instead."
            ),
        }

    if not js_click(page, r"^upi$"):
        return {"status": "error", "error": "Could not find or open the UPI section on the payment screen."}
    try:
        page.wait_for_selector("text=/scan qr to pay/i", timeout=8000)
    except Exception:
        return {"status": "error", "error": "UPI section did not open after clicking it."}

    if not js_click(page, r"generate qr"):
        return {"status": "error", "error": "Could not find the 'Generate QR' button under UPI."}

    try:
        # "Scan QR to pay" is already on screen before the QR itself exists
        # (it labels the Generate QR button's placeholder too — confirmed
        # live) — "Approve payment within" only appears once a real QR has
        # been generated, so that's the actual ready signal, not the
        # heading.
        page.wait_for_selector("text=/approve payment within/i", timeout=10000)
        page.wait_for_timeout(500)  # let the QR image itself finish rendering
    except Exception:
        return {"status": "error", "error": "UPI QR code did not appear after clicking 'Generate QR'."}

    total_text = page.evaluate(
        """() => {
            const el = document.querySelector('[class*="total" i], [class*="amount" i]');
            return el?.textContent?.trim().slice(0, 30) || null;
        }"""
    )
    match = re.search(r"[\d.]+", total_text or "")
    amount_due = float(match.group(0)) if match else None

    QR_DIR.mkdir(parents=True, exist_ok=True)
    qr_path = QR_DIR / f"blinkit_upi_qr_{int(time.time())}.png"
    try:
        # Screenshot the panel containing the QR rather than a hand-picked
        # element locator (untested live) — the panel is small and the QR
        # is the visually dominant thing in it, so this is legible even if
        # the exact bounding box is generous.
        panel = page.locator("text=/approve payment within/i").locator("xpath=ancestor::div[3]")
        (panel if panel.count() else page).screenshot(path=str(qr_path))
    except Exception:
        page.screenshot(path=str(qr_path))  # fall back to a full-viewport shot

    return {
        "status": "awaiting_manual_payment",
        "qr_image_path": str(qr_path),
        "amount_due": amount_due,
        "note": (
            "A live UPI QR code was generated and is time-limited (Blinkit showed a ~5 "
            "minute countdown in testing). Send qr_image_path to the user via "
            "notify_user right away so they can scan and pay before it expires. This "
            "does not confirm payment or place the order — only the user completing the "
            "scan does that, out of band."
        ),
    }
