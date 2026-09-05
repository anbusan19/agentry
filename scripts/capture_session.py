"""
scripts/capture_session.py

Interactive login-session capture for the storefront.

Ported from the pre-existing prototype this hackathon submission builds on
(see README's Disclosure section), which used a readline prompt in a real
terminal to pause for manual login. That doesn't work when this script is
launched by an agent/tool harness with no interactive stdin attached, so
this version opens a visible browser window and instead polls for a marker
file — written by whoever triggered the capture once you've logged in —
before saving the session and exiting.

Usage:
    python scripts/capture_session.py

Then, once you've logged in in the browser window that pops up, signal
completion with:
    touch /tmp/agentry_capture_done
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._session import CONTEXT_ARGS, SESSION_DIR, STOREFRONT_URL  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DONE_MARKER = Path("/tmp/agentry_capture_done")
POLL_SECONDS = 2
TIMEOUT_SECONDS = 15 * 60


def main() -> None:
    DONE_MARKER.unlink(missing_ok=True)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Opening {STOREFRONT_URL} in a visible browser window...")
    print("Log in there, then run:  touch /tmp/agentry_capture_done")
    print(f"(profile will be saved to {SESSION_DIR})\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            args=["--no-sandbox"],
            **CONTEXT_ARGS,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(STOREFRONT_URL)

        waited = 0
        while not DONE_MARKER.exists():
            time.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            if waited >= TIMEOUT_SECONDS:
                print("Timed out waiting for the done marker — closing without confirming login.")
                break

        context.close()

    DONE_MARKER.unlink(missing_ok=True)
    print(f"Session profile saved: {SESSION_DIR}")


if __name__ == "__main__":
    main()
