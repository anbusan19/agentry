"""
scripts/capture_session.py

Interactive login-session capture for a storefront.

Ported from the pre-existing prototype this hackathon submission builds on
(see README's Disclosure section), which used a readline prompt in a real
terminal to pause for manual login. That doesn't work when this script is
launched by an agent/tool harness with no interactive stdin attached, so
this version opens a visible browser window and instead polls for a marker
file — written by whoever triggered the capture once you've logged in —
before saving the session and exiting.

Works for any platform in tools._session.PLATFORMS (Zepto, Blinkit, Swiggy
Instamart) — this flow is just "open the URL, let the user log in, keep the
profile," which doesn't depend on that platform's shopping tools existing
yet. Blinkit/Instamart tool support (search, cart, checkout) is a separate,
not-yet-done piece; capturing a session for them just means you're ready
for when it lands.

Usage:
    python scripts/capture_session.py [platform]   # platform defaults to zepto

Then, once you've logged in in the browser window that pops up, signal
completion with:
    touch /tmp/agentry_capture_done
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._session import CONTEXT_ARGS, DEFAULT_PLATFORM, PLATFORMS, session_dir  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DONE_MARKER = Path("/tmp/agentry_capture_done")
POLL_SECONDS = 2
TIMEOUT_SECONDS = 15 * 60


def main() -> None:
    platform = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLATFORM
    if platform not in PLATFORMS:
        print(f"Unknown platform {platform!r}. Known: {', '.join(PLATFORMS)}")
        sys.exit(1)

    info = PLATFORMS[platform]
    sdir = session_dir(platform)

    DONE_MARKER.unlink(missing_ok=True)
    sdir.mkdir(parents=True, exist_ok=True)

    print(f"Opening {info['url']} ({info['label']}) in a visible browser window...")
    print("Log in there, then run:  touch /tmp/agentry_capture_done")
    print(f"(profile will be saved to {sdir})")
    if not info["supported"]:
        print(f"Note: {info['label']}'s shopping tools aren't implemented yet — this only saves the login.")
    print()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(sdir),
            headless=False,
            # Same stealth flags as tools._session.get_page() — without
            # these, Playwright's automation fingerprint (navigator.webdriver,
            # the AutomationControlled feature) is easy for a site's bot
            # detection to catch. Swiggy Instamart's did, blocking the very
            # first request; Zepto/Blinkit happened not to check as hard.
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            **CONTEXT_ARGS,
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(info["url"])

        waited = 0
        while not DONE_MARKER.exists():
            time.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            if waited >= TIMEOUT_SECONDS:
                print("Timed out waiting for the done marker — closing without confirming login.")
                break

        context.close()

    DONE_MARKER.unlink(missing_ok=True)
    print(f"Session profile saved: {sdir}")


if __name__ == "__main__":
    main()
