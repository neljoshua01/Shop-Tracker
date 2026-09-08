"""
TEST-ONLY experiment for direct Shopee get_pc polling.

Purpose:
    Compare the current browser-generated get_pc monitoring cadence with a
    direct get_pc request performed inside the already-open Shopee page.

This test does NOT modify PurchasePipeline, SkuPriceMonitor, checkout, trigger
logic, or any production purchase behavior.

Experiment configuration:
    - PDP refresh / outer polling interval: 5 seconds
    - Direct get_pc request interval: 1 second
    - Default observation duration: 120 seconds

The test first opens the promotional PDP and observes a normal browser-generated
get_pc request. It then reuses that exact get_pc URL for direct same-page fetches
with the browser's existing credentials/session.

The test only records HTTP status, response timing, JSON validity, and selected
SKU parsing. It does not place an order and does not invoke PurchasePipeline.
"""

import argparse
import json
import os
import sys
import time
from threading import Event, Lock

# Allow direct execution from the repository root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_action import BrowserActions
from execution.browser.browser_connector import BrowserConnector
from purchase.parser.sku_price_parser import SkuPriceParser


PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"
ITEM_ID = 26342037051
MODEL_ID = 139454633402


def page_evaluate(browser_session, expression, timeout=15):
    """Run test-only JavaScript on the existing Playwright page."""

    async def _evaluate():
        return await browser_session.page.evaluate(expression)

    future = AsyncRuntime.instance().submit(_evaluate())
    return future.result(timeout=timeout)


def wait_for_get_pc_url(browser_session, timeout_seconds=10):
    """Read the most recent get_pc resource URL from the page."""

    deadline = time.monotonic() + timeout_seconds
    expression = """
        () => {
            const entries = performance.getEntriesByType('resource');
            const matches = entries
                .map(entry => entry.name)
                .filter(name => name.includes('/api/v4/pdp/get_pc'));
            return matches.length ? matches[matches.length - 1] : null;
        }
    """

    while time.monotonic() < deadline:
        url = page_evaluate(browser_session, expression)
        if url:
            return url
        time.sleep(0.25)

    return None


def direct_get_pc(browser_session, url):
    """Fetch get_pc from the page's own browser context using fetch()."""

    expression = """
        async (url) => {
            const started = performance.now();
            try {
                const response = await fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                    cache: 'no-store',
                });

                const body = await response.text();

                return {
                    ok: response.ok,
                    status: response.status,
                    url: response.url,
                    elapsed_ms: performance.now() - started,
                    body: body,
                };
            } catch (error) {
                return {
                    ok: false,
                    status: 0,
                    url: url,
                    elapsed_ms: performance.now() - started,
                    body: '',
                    error: String(error),
                };
            }
        }
    """

    return page_evaluate_with_argument(browser_session, expression, url, timeout=15)


def page_evaluate_with_argument(browser_session, expression, argument, timeout=15):
    async def _evaluate():
        return await browser_session.page.evaluate(expression, argument)

    future = AsyncRuntime.instance().submit(_evaluate())
    return future.result(timeout=timeout)


def main():
    parser = argparse.ArgumentParser(
        description="Observe direct 1-second get_pc polling in an existing Shopee browser session."
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=120,
        help="Observation duration in seconds (default: 120).",
    )
    parser.add_argument(
        "--direct-interval",
        type=float,
        default=1.0,
        help="Direct get_pc request cadence in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=5.0,
        help="PDP refresh / outer polling interval in seconds (default: 5.0).",
    )
    args = parser.parse_args()

    if args.duration <= 0 or args.direct_interval <= 0 or args.refresh_interval <= 0:
        print("[DirectGetPcTest] ERROR: duration and intervals must be positive.")
        return 1

    connector = BrowserConnector()
    owner = object()
    browser_session = None
    parser_instance = SkuPriceParser()

    get_pc_url = None
    url_lock = Lock()
    stop_capture = Event()

    def capture_get_pc_url(response):
        nonlocal get_pc_url
        if stop_capture.is_set():
            return
        if "/api/v4/pdp/get_pc" not in response.url:
            return
        with url_lock:
            get_pc_url = response.url
        print("[DirectGetPcTest] Browser-generated get_pc observed.")

    print()
    print("=" * 72)
    print("DIRECT get_pc — ISOLATED 1-SECOND OBSERVATION TEST")
    print("=" * 72)
    print(f"PDP:                     {PROMOTIONAL_URL}")
    print(f"Item ID:                 {ITEM_ID}")
    print(f"Model ID:                {MODEL_ID}")
    print(f"PDP refresh interval:    {args.refresh_interval:.1f}s")
    print(f"Direct get_pc interval:  {args.direct_interval:.1f}s")
    print(f"Observation duration:    {args.duration}s")
    print("Production pipeline:     NOT USED")
    print("Checkout / Place Order:  NOT USED")
    print("=" * 72)
    print()

    try:
        browser_session = connector.open_session(owner, PROMOTIONAL_URL)
        connector.engine.register_response_callback(
            owner,
            capture_get_pc_url,
            session=browser_session,
        )

        actions = BrowserActions(browser_session)
        actions.wait_for_selector("body", timeout=15000)
        actions.wait_for_timeout(5000)

        with url_lock:
            captured = get_pc_url

        if captured is None:
            captured = wait_for_get_pc_url(browser_session, timeout_seconds=5)

        if captured is None:
            print("[DirectGetPcTest] RESULT: FAIL — could not observe a get_pc URL.")
            return 1

        with url_lock:
            get_pc_url = captured

        print(f"[DirectGetPcTest] Direct get_pc URL established: {captured}")
        print("[DirectGetPcTest] Starting observation window now.")
        print()

        started = time.monotonic()
        next_direct = started
        next_refresh = started + args.refresh_interval

        total = 0
        success = 0
        http_errors = 0
        transport_errors = 0
        json_errors = 0
        parse_success = 0
        parse_mismatch = 0
        total_latency_ms = 0.0
        max_latency_ms = 0.0
        last_refresh = started

        while True:
            now = time.monotonic()
            if now - started >= args.duration:
                break

            if now >= next_refresh:
                try:
                    print("[DirectGetPcTest] 5s outer cycle: refreshing PDP...")
                    actions.reload()
                    last_refresh = time.monotonic()

                    refreshed_url = wait_for_get_pc_url(browser_session, timeout_seconds=5)
                    if refreshed_url:
                        with url_lock:
                            get_pc_url = refreshed_url
                        print("[DirectGetPcTest] get_pc URL refreshed from browser request.")
                    else:
                        print("[DirectGetPcTest] WARNING: no refreshed get_pc URL observed; retaining previous URL.")
                except Exception as exc:
                    print(f"[DirectGetPcTest] PDP refresh warning: {exc}")

                next_refresh += args.refresh_interval

            now = time.monotonic()
            if now >= next_direct:
                with url_lock:
                    request_url = get_pc_url

                result = direct_get_pc(browser_session, request_url)
                total += 1
                latency = float(result.get("elapsed_ms") or 0.0)
                total_latency_ms += latency
                max_latency_ms = max(max_latency_ms, latency)

                status = int(result.get("status") or 0)
                if result.get("ok"):
                    success += 1
                elif status:
                    http_errors += 1
                else:
                    transport_errors += 1

                body = result.get("body") or ""
                parsed = None

                if result.get("ok"):
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        json_errors += 1

                    if isinstance(parsed, dict):
                        try:
                            state = parser_instance.parse(parsed, model_id=MODEL_ID)
                            if state is not None and state.item_id == ITEM_ID:
                                parse_success += 1
                            else:
                                parse_mismatch += 1
                        except Exception:
                            parse_mismatch += 1

                if total == 1 or total % 10 == 0 or status not in (200,):
                    print(
                        "[DirectGetPcTest] "
                        f"#{total:03d} status={status} latency={latency:.1f}ms "
                        f"parsed={'YES' if parsed is not None else 'NO'}"
                    )

                next_direct += args.direct_interval
                continue

            time.sleep(0.02)

        elapsed = time.monotonic() - started
        stop_capture.set()

        print()
        print("=" * 72)
        print("DIRECT get_pc OBSERVATION RESULT")
        print("=" * 72)
        print(f"Elapsed:                         {elapsed:.1f}s")
        print(f"Direct get_pc requests:          {total}")
        print(f"HTTP-successful requests:        {success}")
        print(f"HTTP errors:                     {http_errors}")
        print(f"Transport/browser errors:        {transport_errors}")
        print(f"JSON decode errors:              {json_errors}")
        print(f"Valid selected-SKU parses:       {parse_success}")
        print(f"Selected-SKU parse mismatches:   {parse_mismatch}")
        if total:
            print(f"Average direct request latency:  {total_latency_ms / total:.1f}ms")
            print(f"Maximum direct request latency:  {max_latency_ms:.1f}ms")
            print(f"Observed request rate:            {total / elapsed:.2f} requests/sec")
        print()
        print("Anti-bot indicators to inspect manually:")
        print("  - Shopee verification / traffic error page")
        print("  - HTTP 403 / 429 responses")
        print("  - browser/page crash or unexpected navigation")
        print("  - repeated non-JSON responses")
        print("  - sudden sustained request failures")
        print("=" * 72)

        if total == 0:
            print("[DirectGetPcTest] RESULT: FAIL — no direct get_pc requests completed.")
            return 1

        print("[DirectGetPcTest] RESULT: PASS — isolated observation completed.")
        print("[DirectGetPcTest] No purchase or checkout action was performed.")
        return 0

    finally:
        stop_capture.set()
        try:
            connector.engine.unregister_response_callback(owner, session=browser_session)
        except Exception:
            pass
        try:
            connector.close_session(owner)
        except Exception as exc:
            print(f"[DirectGetPcTest] Cleanup warning: {exc}")


if __name__ == "__main__":
    sys.exit(main())
