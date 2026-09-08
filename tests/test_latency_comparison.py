"""
Isolated live-page latency comparison for V2 monitoring.

IMPORTANT:
    TEST-ONLY. No production files are modified and no dashboard integration
    is performed.

Compares two monitoring strategies against the same live Shopee PDP:

    A) CURRENT: production SkuPriceMonitor with 5s polling.
    B) CANDIDATE: test-only direct same-page get_pc fetch at 1s cadence.

Both runs use the validated Apple iPad 11th Gen A16 SKU:
    Color: Pink
    Capacity: 128GB
    model_id: 185943879173

This SKU was previously validated through the real production checkout path,
including SPayLater detection/selection, and has a checkout total within the
known SPayLater credit used for this test. It is intentionally used here
instead of the more expensive iPhone 17 Pro Max SKU, which previously failed
at the SPayLater selection stage during this comparison.

Both runs:
    - prepare the real cart with the production CartPreparer
    - parse real live get_pc responses with the production SkuPriceParser
    - use a controlled qualification gate so the event occurs between normal
      polling opportunities instead of triggering immediately on the first
      response
    - enter the real production CheckoutExecutor after the controlled trigger
    - run in SAFE mode, so Place Order is detected but never clicked

The controlled gate is deliberately NOT a production trigger rule. It makes
this a repeatable timing experiment: live get_pc data must be valid, but the
moment at which the qualifying state is allowed to trigger is controlled.
This isolates the latency caused by observation cadence from the checkout path.

Run:
    python3 tests/test_latency_comparison.py

Optional:
    --release-delay 2.5    seconds after the first valid live observation
    --direct-interval 1.0  candidate fetch cadence
    --baseline-interval 5  current production polling cadence

No anti-bot bypass, jitter, stealth change, or production polling change is
introduced by this test.
"""

import argparse
import json
import os
import sys
import time
from threading import Event

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.runtime.async_runtime import AsyncRuntime
from core.runtime.safety_gate import RuntimeSafetyGate
from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions
from purchase.execution.checkout_executor import CheckoutExecutor
from purchase.execution.purchase_pipeline import PurchasePipeline
from purchase.execution.purchase_trigger_evaluator import PurchaseTriggerEvaluator
from purchase.execution.cart_preparer import CartPreparer
from purchase.parser.sku_price_parser import SkuPriceParser

import tests.test_promotional_url_end_to_end as promotional_test


PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/27731669814"
ITEM_ID = 27731669814
SHOP_ID = 1275798143
GET_PC_PATH = "/api/v4/pdp/get_pc"

# Validated production checkout SKU.
TEST_VARIATION = {
    "Color": "Pink",
    "Storage": "128GB",
}
TEST_MODEL_ID = 185943879173

# Shopee integer price observed for this SKU during the validated checkout.
OBSERVED_BASELINE_PRICE = 3101100000


def configure_test_variation():
    """Configure only the imported TEST fixture for this test process."""
    promotional_test.PROMOTIONAL_URL = PROMOTIONAL_URL
    promotional_test.REQUESTED_VARIATION = dict(TEST_VARIATION)
    promotional_test.DEFAULT_MODEL_ID = TEST_MODEL_ID
    promotional_test.OBSERVED_BASELINE_PRICE = OBSERVED_BASELINE_PRICE


class ControlledTriggerEvaluator:
    """Test-only trigger gate that releases after a controlled delay."""

    def __init__(self, release_delay: float):
        self.release_delay = release_delay
        self.first_valid_ns = None
        self.release_ns = None
        self.trigger_ns = None
        self.valid_observations = 0

    def evaluate(self, session, state):
        if self.first_valid_ns is None:
            self.first_valid_ns = time.perf_counter_ns()
            self.release_ns = self.first_valid_ns + int(self.release_delay * 1_000_000_000)
            print(
                "[LatencyComparison] First valid live SKU observation captured; "
                f"controlled release in {self.release_delay:.3f}s."
            )

        self.valid_observations += 1

        if self.trigger_ns is None and time.perf_counter_ns() >= self.release_ns:
            self.trigger_ns = time.perf_counter_ns()
            print("[LatencyComparison] Controlled trigger RELEASED.")
            return True

        return False


class TimingProbe:
    def __init__(self):
        self.place_order_ns = None

    def mark_place_order(self):
        if self.place_order_ns is None:
            self.place_order_ns = time.perf_counter_ns()
            print("[LatencyComparison] Place Order detection timestamp captured.")


class DirectGetPcMonitor:
    """Test-only direct same-page get_pc monitor."""

    def __init__(self, evaluator: ControlledTriggerEvaluator, interval: float):
        self.evaluator = evaluator
        self.interval = interval
        self.parser = SkuPriceParser()
        self.triggered = Event()
        self.stop_event = Event()
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.request_start_times = []
        self.endpoint = None

    def _wait_for_endpoint(self, browser_session):
        connector = BrowserConnector()
        owner = object()
        ready = Event()

        def callback(response):
            if GET_PC_PATH in response.url and self.endpoint is None:
                self.endpoint = response.url
                ready.set()

        connector.engine.register_response_callback(owner, callback, session=browser_session)
        try:
            actions = BrowserActions(browser_session)
            actions.goto(PROMOTIONAL_URL)
            if not ready.wait(timeout=15):
                raise RuntimeError("Timed out waiting for browser-generated get_pc endpoint.")
        finally:
            try:
                connector.engine.unregister_response_callback(owner, session=browser_session)
            except Exception:
                pass

    def run(self, session):
        browser_session = session.browser_session
        if browser_session is None:
            raise RuntimeError("Browser session unavailable for direct monitor.")

        self._wait_for_endpoint(browser_session)

        if not self.endpoint:
            raise RuntimeError("Could not capture browser-generated get_pc endpoint.")

        print(f"[LatencyComparison] Direct get_pc interval: {self.interval:.3f}s")
        print("[LatencyComparison] Direct monitor uses live same-page fetch only.")

        next_start = time.monotonic()
        while not self.triggered.is_set() and not self.stop_event.is_set():
            delay = next_start - time.monotonic()
            if delay > 0:
                time.sleep(delay)

            started = time.monotonic()
            self.request_start_times.append(started)
            self.request_count += 1

            try:
                async def fetch_json():
                    return await browser_session.page.evaluate(
                        """
                        async (url) => {
                            const response = await fetch(url, {
                                credentials: 'include',
                                cache: 'no-store',
                                method: 'GET'
                            });
                            const text = await response.text();
                            let data = null;
                            try { data = JSON.parse(text); } catch (_) {}
                            return {status: response.status, data};
                        }
                        """,
                        self.endpoint,
                    )

                result = AsyncRuntime.instance().submit(fetch_json()).result(timeout=15)
                status = result.get("status")
                data = result.get("data")

                if status != 200 or not isinstance(data, dict):
                    self.error_count += 1
                else:
                    state = self.parser.parse(data, model_id=session.variation.model_id)
                    if state is not None and state.item_id == session.product.item_id:
                        self.success_count += 1
                        if self.evaluator.evaluate(session, state):
                            self.triggered.set()
                            break
            except Exception as exc:
                self.error_count += 1
                print(f"[LatencyComparison] Direct get_pc error: {exc}")

            next_start += self.interval

        return self.triggered.is_set()

    def stop(self):
        self.stop_event.set()


def install_place_order_probe(probe: TimingProbe):
    from execution.checkout.checkout_verifier import CheckoutVerifier

    original = CheckoutVerifier.verify_place_order

    async def timed_verify(self, page):
        result = await original(self, page)
        if result:
            probe.mark_place_order()
        return result

    CheckoutVerifier.verify_place_order = timed_verify

    def restore():
        CheckoutVerifier.verify_place_order = original

    return restore


def install_controlled_evaluator(controlled: ControlledTriggerEvaluator):
    original = PurchaseTriggerEvaluator.evaluate

    def evaluate(self, session, state):
        return controlled.evaluate(session, state)

    PurchaseTriggerEvaluator.evaluate = evaluate

    def restore():
        PurchaseTriggerEvaluator.evaluate = original

    return restore


def prepare_session(variation_options, polling_interval):
    session = promotional_test.build_session(
        target_price=OBSERVED_BASELINE_PRICE,
        polling_interval=int(polling_interval),
        variation_options=variation_options,
    )
    session.variation.name = "Pink / 128GB"
    session.variation.model_id = TEST_MODEL_ID
    session.variation.price = OBSERVED_BASELINE_PRICE
    return session


def run_baseline(variation_options, release_delay, polling_interval):
    print("\n" + "=" * 72)
    print("RUN A — CURRENT PRODUCTION MONITOR")
    print("=" * 72)
    print(f"Product: Apple iPad 11th Gen A16")
    print(f"Variation: {TEST_VARIATION['Color']} / {TEST_VARIATION['Storage']}")
    print(f"Item ID: {ITEM_ID}")
    print(f"Model ID: {TEST_MODEL_ID}")
    print(f"Polling interval: {polling_interval:.3f}s")
    print(f"Controlled release delay: {release_delay:.3f}s")
    print("Mode: SAFE — Place Order will NOT be clicked")

    session = prepare_session(variation_options, polling_interval)
    controlled = ControlledTriggerEvaluator(release_delay)
    probe = TimingProbe()
    restore_eval = install_controlled_evaluator(controlled)
    restore_probe = install_place_order_probe(probe)
    pipeline = PurchasePipeline()

    try:
        result = pipeline.run(session)
    finally:
        restore_probe()
        restore_eval()
        try:
            pipeline.stop()
        except Exception:
            pass

    trigger_to_place = None
    release_to_trigger = None
    if controlled.trigger_ns is not None:
        release_to_trigger = (controlled.trigger_ns - controlled.release_ns) / 1_000_000
    if controlled.trigger_ns is not None and probe.place_order_ns is not None:
        trigger_to_place = (probe.place_order_ns - controlled.trigger_ns) / 1_000_000

    return {
        "name": "CURRENT_5S",
        "pipeline_result": bool(result),
        "first_valid_ns": controlled.first_valid_ns,
        "release_ns": controlled.release_ns,
        "trigger_ns": controlled.trigger_ns,
        "place_order_ns": probe.place_order_ns,
        "release_to_trigger_ms": release_to_trigger,
        "trigger_to_place_order_ms": trigger_to_place,
        "valid_observations": controlled.valid_observations,
    }


def run_direct(variation_options, release_delay, interval):
    print("\n" + "=" * 72)
    print("RUN B — CANDIDATE DIRECT get_pc MONITOR")
    print("=" * 72)
    print(f"Product: Apple iPad 11th Gen A16")
    print(f"Variation: {TEST_VARIATION['Color']} / {TEST_VARIATION['Storage']}")
    print(f"Item ID: {ITEM_ID}")
    print(f"Model ID: {TEST_MODEL_ID}")
    print(f"Direct get_pc interval: {interval:.3f}s")
    print(f"Controlled release delay: {release_delay:.3f}s")
    print("Mode: SAFE — Place Order will NOT be clicked")

    session = prepare_session(variation_options, interval)
    safety_gate = RuntimeSafetyGate.instance()
    safety_gate.reset_to_safe()

    cart_preparer = CartPreparer()
    if not cart_preparer.prepare(session):
        raise RuntimeError("Cart preparation failed in direct-monitor run.")

    controlled = ControlledTriggerEvaluator(release_delay)
    probe = TimingProbe()
    direct_monitor = DirectGetPcMonitor(controlled, interval)
    restore_probe = install_place_order_probe(probe)

    try:
        triggered = direct_monitor.run(session)
        if not triggered:
            raise RuntimeError("Direct monitor did not reach the controlled trigger.")

        direct_monitor.stop()
        checkout_result = CheckoutExecutor(safety_gate=safety_gate).execute(session)
    finally:
        restore_probe()
        direct_monitor.stop()

    trigger_to_place = None
    release_to_trigger = None
    if controlled.trigger_ns is not None:
        release_to_trigger = (controlled.trigger_ns - controlled.release_ns) / 1_000_000
    if controlled.trigger_ns is not None and probe.place_order_ns is not None:
        trigger_to_place = (probe.place_order_ns - controlled.trigger_ns) / 1_000_000

    return {
        "name": "DIRECT_1S",
        "pipeline_result": bool(checkout_result),
        "first_valid_ns": controlled.first_valid_ns,
        "release_ns": controlled.release_ns,
        "trigger_ns": controlled.trigger_ns,
        "place_order_ns": probe.place_order_ns,
        "release_to_trigger_ms": release_to_trigger,
        "trigger_to_place_order_ms": trigger_to_place,
        "valid_observations": controlled.valid_observations,
        "direct_requests": direct_monitor.request_count,
        "direct_successes": direct_monitor.success_count,
        "direct_errors": direct_monitor.error_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare V2 monitoring latency without modifying production code.")
    parser.add_argument("--release-delay", type=float, default=2.5, help="Controlled trigger release delay after first valid observation.")
    parser.add_argument("--baseline-interval", type=float, default=5.0, help="Current production polling interval.")
    parser.add_argument("--direct-interval", type=float, default=1.0, help="Candidate direct get_pc interval.")
    args = parser.parse_args()

    if args.release_delay <= 0 or args.baseline_interval <= 0 or args.direct_interval <= 0:
        raise SystemExit("All timing values must be greater than zero.")

    configure_test_variation()

    print("\n" + "=" * 72)
    print("V2 ISOLATED LATENCY COMPARISON")
    print("=" * 72)
    print(f"PDP: {PROMOTIONAL_URL}")
    print(f"Product: Apple iPad 11th Gen A16")
    print(f"Item ID: {ITEM_ID}")
    print(f"Shop ID: {SHOP_ID}")
    print(f"Variation: {TEST_VARIATION['Color']} / {TEST_VARIATION['Storage']}")
    print(f"Model ID: {TEST_MODEL_ID}")
    print(f"Baseline: {args.baseline_interval:.3f}s browser-generated get_pc")
    print(f"Candidate: {args.direct_interval:.3f}s direct same-page get_pc")
    print(f"Controlled release: {args.release_delay:.3f}s after first valid observation")
    print("Production files changed: NONE")
    print("Place Order: SAFE / detection only")
    print("=" * 72)

    RuntimeSafetyGate.instance().reset_to_safe()
    print("[LatencyComparison] Resolving live variation labels...")
    variation_options = promotional_test.resolve_live_variation_options()

    baseline = run_baseline(
        variation_options,
        args.release_delay,
        args.baseline_interval,
    )

    RuntimeSafetyGate.instance().reset_to_safe()
    direct = run_direct(
        variation_options,
        args.release_delay,
        args.direct_interval,
    )

    print("\n" + "=" * 72)
    print("LATENCY COMPARISON RESULT")
    print("=" * 72)
    print(f"{'Metric':<32} {'CURRENT 5s':>16} {'DIRECT 1s':>16}")
    print("-" * 72)

    def fmt(value):
        return "N/A" if value is None else f"{value:.3f} ms"

    print(f"{'Release -> trigger detection':<32} {fmt(baseline['release_to_trigger_ms']):>16} {fmt(direct['release_to_trigger_ms']):>16}")
    print(f"{'Trigger -> Place Order':<32} {fmt(baseline['trigger_to_place_order_ms']):>16} {fmt(direct['trigger_to_place_order_ms']):>16}")
    print(f"{'Valid live observations':<32} {baseline['valid_observations']:>16} {direct['valid_observations']:>16}")
    print(f"{'Direct requests':<32} {'N/A':>16} {direct['direct_requests']:>16}")
    print(f"{'Direct successful requests':<32} {'N/A':>16} {direct['direct_successes']:>16}")
    print(f"{'Direct errors':<32} {'N/A':>16} {direct['direct_errors']:>16}")

    if baseline['release_to_trigger_ms'] is not None and direct['release_to_trigger_ms'] is not None:
        detection_improvement = baseline['release_to_trigger_ms'] - direct['release_to_trigger_ms']
        print(f"{'Detection improvement':<32} {detection_improvement:>16.3f} ms")

    if baseline['trigger_to_place_order_ms'] is not None and direct['trigger_to_place_order_ms'] is not None:
        checkout_difference = direct['trigger_to_place_order_ms'] - baseline['trigger_to_place_order_ms']
        print(f"{'Checkout-path difference':<32} {checkout_difference:>16.3f} ms")

    print("=" * 72)
    print(f"Current production run PASS: {baseline['pipeline_result'] and baseline['trigger_to_place_order_ms'] is not None}")
    print(f"Direct candidate run PASS:   {direct['pipeline_result'] and direct['trigger_to_place_order_ms'] is not None}")
    print("Place Order was NOT clicked in either run.")

    output = {
        "baseline": baseline,
        "direct": direct,
        "parameters": vars(args),
        "test_sku": {
            "product": "Apple iPad 11th Gen A16",
            "item_id": ITEM_ID,
            "shop_id": SHOP_ID,
            "model_id": TEST_MODEL_ID,
            "variation": dict(TEST_VARIATION),
            "checkout_total_observed": 31161,
        },
    }
    with open("latency_comparison_result.json", "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
    print("Result JSON: latency_comparison_result.json")

    if not baseline['pipeline_result'] or baseline['trigger_to_place_order_ms'] is None:
        return 1
    if not direct['pipeline_result'] or direct['trigger_to_place_order_ms'] is None:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
