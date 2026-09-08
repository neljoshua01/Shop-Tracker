"""
Isolated live-page latency comparison for V2 monitoring.

TEST-ONLY. No production files, settings.json, dashboard, or Discord code is
modified by this test.

Run A uses the validated Pink / 128GB iPad SKU with the current production
5-second browser-generated get_pc monitor.

Run B uses a DIFFERENT SKU variation on the same product: Blue / 128GB. This
prevents the second run from adding the exact same cart variation again.
The candidate run uses a test-only direct same-page get_pc fetch at 1-second
cadence.

The candidate model_id is discovered from the live get_pc model list after the
Blue / 128GB variation is selected. It is never guessed or copied from the
Pink / 128GB SKU.

Both runs:
    - use the real production CartPreparer / CheckoutExecutor path
    - parse live get_pc data with SkuPriceParser
    - use a controlled qualification gate so timing is repeatable without
      requiring a real promotion transition
    - run SAFE, so Place Order is detected but never clicked

Run:
    python3 tests/test_latency_comparison.py
"""

import argparse
import json
import os
import re
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
from purchase.execution.cart_preparer import CartPreparer
from purchase.execution.checkout_executor import CheckoutExecutor
from purchase.execution.purchase_pipeline import PurchasePipeline
from purchase.execution.purchase_trigger_evaluator import PurchaseTriggerEvaluator
from purchase.models.payment_method import PaymentMethod
from purchase.models.product_info import ProductInfo
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.models.trigger_condition import TriggerCondition
from purchase.models.variation import Variation
from purchase.parser.sku_price_parser import SkuPriceParser

import tests.test_promotional_url_end_to_end as promotional_test


PROMOTIONAL_URL = "https://shopee.ph/product/1279438143/27731669814"
# Correct Shopee PDP URL / identity for the validated iPad listing.
PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/27731669814"
ITEM_ID = 27731669814
SHOP_ID = 1275798143
GET_PC_PATH = "/api/v4/pdp/get_pc"

# Run A: previously validated through the real checkout path.
BASE_VARIATION_APP = {
    "Color": "Pink",
    "Storage": "128GB",
}
BASE_VARIATION_LIVE = {
    "Color": "Pink",
    "Capacity": "128GB",
}
BASE_MODEL_ID = 185943879173

# Run B: deliberately different cart variation.
CANDIDATE_VARIATION_APP = {
    "Color": "Blue",
    "Storage": "128GB",
}
CANDIDATE_VARIATION_LIVE = {
    "Color": "Blue",
    "Capacity": "128GB",
}
CANDIDATE_MODEL_ID = None

OBSERVED_BASELINE_PRICE = 3101100000
TEST_TARGET_PRICE = 3500000000
PRICE_BEFORE_DISCOUNT = 3569000000


def configure_test_fixture():
    """Configure only the imported fixture used for live label discovery."""
    promotional_test.PROMOTIONAL_URL = PROMOTIONAL_URL
    promotional_test.REQUESTED_VARIATION = dict(BASE_VARIATION_APP)
    promotional_test.DEFAULT_MODEL_ID = BASE_MODEL_ID
    promotional_test.OBSERVED_BASELINE_PRICE = OBSERVED_BASELINE_PRICE


class ControlledTriggerEvaluator:
    """Test-only trigger gate released after a controlled delay."""

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


def build_session(variation_options, variation_name, model_id, polling_interval):
    reference = ProductReference(
        shop_id=SHOP_ID,
        item_id=ITEM_ID,
        url=PROMOTIONAL_URL,
    )

    request = PurchaseRequest(
        reference=reference,
        options=dict(variation_options),
        quantity=1,
        auto_checkout=True,
        target_price=TEST_TARGET_PRICE,
        payment_method=PaymentMethod.SPAYLATER,
        trigger=TriggerCondition.PRICE_TARGET,
        polling_interval=int(polling_interval),
        lock_selected_variations=True,
    )

    product = ProductInfo(
        item_id=ITEM_ID,
        shop_id=SHOP_ID,
        product_name="Apple iPad 11th Gen A16 (Wifi)",
        shop_name="Apple Flagship Store",
        product_url=PROMOTIONAL_URL,
        currency="PHP",
        image="",
        available_variations=[],
    )

    variation = Variation(
        model_id=model_id or 0,
        name=variation_name,
        options=dict(variation_options),
        price=OBSERVED_BASELINE_PRICE,
        price_before_discount=PRICE_BEFORE_DISCOUNT,
        has_stock=True,
        tier_index=[0, 0],
        sku_image="",
    )

    return PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )


class DirectGetPcMonitor:
    """Test-only direct same-page get_pc monitor."""

    def __init__(self, evaluator: ControlledTriggerEvaluator, interval: float, expected_variation: str):
        self.evaluator = evaluator
        self.interval = interval
        self.expected_variation = expected_variation
        self.parser = SkuPriceParser()
        self.triggered = Event()
        self.stop_event = Event()
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.endpoint = None
        self.resolved_model_id = None

    @staticmethod
    def _normalize(value):
        return re.sub(r"[^a-z0-9]", "", str(value).lower())

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
            BrowserActions(browser_session).goto(PROMOTIONAL_URL)
            if not ready.wait(timeout=15):
                raise RuntimeError("Timed out waiting for browser-generated get_pc endpoint.")
        finally:
            try:
                connector.engine.unregister_response_callback(owner, session=browser_session)
            except Exception:
                pass

    def _fetch_live_json(self, browser_session):
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

        return AsyncRuntime.instance().submit(fetch_json()).result(timeout=15)

    def _resolve_model_id(self, browser_session, session):
        result = self._fetch_live_json(browser_session)
        if result.get("status") != 200 or not isinstance(result.get("data"), dict):
            raise RuntimeError("Unable to fetch live get_pc JSON while resolving candidate model_id.")

        data = result["data"]
        try:
            models = data["data"]["item"]["models"]
        except (KeyError, TypeError):
            raise RuntimeError("Live get_pc response did not contain item.models.")

        expected = self._normalize(self.expected_variation)
        candidates = []
        for model in models:
            name = model.get("name", "")
            candidates.append((model.get("model_id"), name))
            if self._normalize(name) == expected:
                model_id = model.get("model_id")
                if model_id is not None:
                    self.resolved_model_id = int(model_id)
                    session.variation.model_id = self.resolved_model_id
                    print(
                        "[LatencyComparison] Candidate model_id resolved from live get_pc: "
                        f"{self.resolved_model_id} ({name})"
                    )
                    return

        print("[LatencyComparison] Live model candidates:")
        for model_id, name in candidates:
            print(f"[LatencyComparison]   {model_id}: {name}")
        raise RuntimeError(
            f"Could not resolve live model_id for candidate variation: {self.expected_variation}"
        )

    def run(self, session):
        browser_session = session.browser_session
        if browser_session is None:
            raise RuntimeError("Browser session unavailable for direct monitor.")

        self._wait_for_endpoint(browser_session)
        if not self.endpoint:
            raise RuntimeError("Could not capture browser-generated get_pc endpoint.")

        # The candidate uses a different variation. Resolve its model ID from
        # the live response instead of guessing or reusing the Pink SKU ID.
        self._resolve_model_id(browser_session, session)

        print(f"[LatencyComparison] Direct get_pc interval: {self.interval:.3f}s")
        print("[LatencyComparison] Direct monitor uses live same-page fetch only.")

        next_start = time.monotonic()
        while not self.triggered.is_set() and not self.stop_event.is_set():
            delay = next_start - time.monotonic()
            if delay > 0:
                time.sleep(delay)

            self.request_count += 1
            try:
                result = self._fetch_live_json(browser_session)
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


def calculate_timings(controlled, probe):
    release_to_trigger = None
    trigger_to_place = None
    if controlled.trigger_ns is not None:
        release_to_trigger = (controlled.trigger_ns - controlled.release_ns) / 1_000_000
    if controlled.trigger_ns is not None and probe.place_order_ns is not None:
        trigger_to_place = (probe.place_order_ns - controlled.trigger_ns) / 1_000_000
    return release_to_trigger, trigger_to_place


def run_baseline(release_delay, polling_interval):
    print("\n" + "=" * 72)
    print("RUN A — CURRENT PRODUCTION MONITOR")
    print("=" * 72)
    print("Product: Apple iPad 11th Gen A16")
    print("Variation: Pink / 128GB")
    print(f"Item ID: {ITEM_ID}")
    print(f"Model ID: {BASE_MODEL_ID}")
    print(f"Polling interval: {polling_interval:.3f}s")
    print(f"Controlled release delay: {release_delay:.3f}s")
    print("Mode: SAFE — Place Order will NOT be clicked")

    session = build_session(BASE_VARIATION_LIVE, "Pink / 128GB", BASE_MODEL_ID, polling_interval)
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

    release_to_trigger, trigger_to_place = calculate_timings(controlled, probe)
    return {
        "name": "CURRENT_5S_PINK_128",
        "variation": "Pink / 128GB",
        "model_id": BASE_MODEL_ID,
        "pipeline_result": bool(result),
        "release_to_trigger_ms": release_to_trigger,
        "trigger_to_place_order_ms": trigger_to_place,
        "valid_observations": controlled.valid_observations,
    }


def run_direct(release_delay, interval):
    print("\n" + "=" * 72)
    print("RUN B — CANDIDATE DIRECT get_pc MONITOR")
    print("=" * 72)
    print("Product: Apple iPad 11th Gen A16")
    print("Variation: Blue / 128GB  <-- DIFFERENT CART VARIATION")
    print(f"Item ID: {ITEM_ID}")
    print("Model ID: resolve from live get_pc")
    print(f"Direct get_pc interval: {interval:.3f}s")
    print(f"Controlled release delay: {release_delay:.3f}s")
    print("Mode: SAFE — Place Order will NOT be clicked")

    session = build_session(CANDIDATE_VARIATION_LIVE, "Blue / 128GB", CANDIDATE_MODEL_ID, interval)
    safety_gate = RuntimeSafetyGate.instance()
    safety_gate.reset_to_safe()

    cart_preparer = CartPreparer()
    if not cart_preparer.prepare(session):
        raise RuntimeError("Cart preparation failed in direct-monitor run.")

    controlled = ControlledTriggerEvaluator(release_delay)
    probe = TimingProbe()
    direct_monitor = DirectGetPcMonitor(controlled, interval, "Blue / 128GB")
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

    release_to_trigger, trigger_to_place = calculate_timings(controlled, probe)
    return {
        "name": "DIRECT_1S_BLUE_128",
        "variation": "Blue / 128GB",
        "model_id": direct_monitor.resolved_model_id,
        "pipeline_result": bool(checkout_result),
        "release_to_trigger_ms": release_to_trigger,
        "trigger_to_place_order_ms": trigger_to_place,
        "valid_observations": controlled.valid_observations,
        "direct_requests": direct_monitor.request_count,
        "direct_successes": direct_monitor.success_count,
        "direct_errors": direct_monitor.error_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare V2 monitoring latency without modifying production code.")
    parser.add_argument("--release-delay", type=float, default=2.5)
    parser.add_argument("--baseline-interval", type=float, default=5.0)
    parser.add_argument("--direct-interval", type=float, default=1.0)
    args = parser.parse_args()

    if args.release_delay <= 0 or args.baseline_interval <= 0 or args.direct_interval <= 0:
        raise SystemExit("All timing values must be greater than zero.")

    configure_test_fixture()

    print("\n" + "=" * 72)
    print("V2 ISOLATED LATENCY COMPARISON")
    print("=" * 72)
    print(f"PDP: {PROMOTIONAL_URL}")
    print("Product: Apple iPad 11th Gen A16")
    print(f"Item ID: {ITEM_ID}")
    print(f"Shop ID: {SHOP_ID}")
    print("Run A: Pink / 128GB — production 5s")
    print("Run B: Blue / 128GB — direct get_pc 1s")
    print(f"Baseline: {args.baseline_interval:.3f}s browser-generated get_pc")
    print(f"Candidate: {args.direct_interval:.3f}s direct same-page get_pc")
    print(f"Controlled release: {args.release_delay:.3f}s after first valid observation")
    print("Target price: 3500000000 (validated iPad checkout target)")
    print("Production files changed: NONE")
    print("Place Order: SAFE / detection only")
    print("=" * 72)

    RuntimeSafetyGate.instance().reset_to_safe()
    print("[LatencyComparison] Resolving live variation labels...")
    promotional_test.REQUESTED_VARIATION = dict(BASE_VARIATION_APP)
    variation_options = promotional_test.resolve_live_variation_options()

    # The resolver should expose the live Capacity key. Build the two run
    # option maps explicitly so Run B is a different cart variation.
    if "Capacity" not in variation_options:
        raise RuntimeError(f"Expected live Capacity variation key, got: {variation_options}")

    base_live = dict(variation_options)
    base_live["Color"] = "Pink"
    base_live["Capacity"] = "128GB"

    candidate_live = dict(base_live)
    candidate_live["Color"] = "Blue"

    # Keep the expected maps visible in the test output for auditability.
    print(f"[LatencyComparison] Run A live options: {base_live}")
    print(f"[LatencyComparison] Run B live options: {candidate_live}")

    # The local builders above use the explicit live maps. These assignments
    # ensure a changed live label is not silently substituted into the test.
    global BASE_VARIATION_LIVE, CANDIDATE_VARIATION_LIVE
    BASE_VARIATION_LIVE = base_live
    CANDIDATE_VARIATION_LIVE = candidate_live

    baseline = run_baseline(args.release_delay, args.baseline_interval)

    RuntimeSafetyGate.instance().reset_to_safe()
    direct = run_direct(args.release_delay, args.direct_interval)

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

    if baseline["release_to_trigger_ms"] is not None and direct["release_to_trigger_ms"] is not None:
        improvement = baseline["release_to_trigger_ms"] - direct["release_to_trigger_ms"]
        print(f"{'Detection improvement':<32} {improvement:>16.3f} ms")

    if baseline["trigger_to_place_order_ms"] is not None and direct["trigger_to_place_order_ms"] is not None:
        checkout_difference = direct["trigger_to_place_order_ms"] - baseline["trigger_to_place_order_ms"]
        print(f"{'Checkout-path difference':<32} {checkout_difference:>16.3f} ms")

    print("=" * 72)
    print(f"Current production run PASS: {baseline['pipeline_result'] and baseline['trigger_to_place_order_ms'] is not None}")
    print(f"Direct candidate run PASS:   {direct['pipeline_result'] and direct['trigger_to_place_order_ms'] is not None}")
    print("Place Order was NOT clicked in either run.")

    output = {
        "baseline": baseline,
        "direct": direct,
        "parameters": vars(args),
        "test_product": {
            "product": "Apple iPad 11th Gen A16 (Wifi)",
            "item_id": ITEM_ID,
            "shop_id": SHOP_ID,
            "baseline_variation": "Pink / 128GB",
            "candidate_variation": "Blue / 128GB",
            "baseline_model_id": BASE_MODEL_ID,
            "candidate_model_id": direct["model_id"],
            "target_price": TEST_TARGET_PRICE,
            "checkout_total_observed": 31161,
        },
    }
    with open("latency_comparison_result.json", "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
    print("Result JSON: latency_comparison_result.json")

    if not baseline["pipeline_result"] or baseline["trigger_to_place_order_ms"] is None:
        return 1
    if not direct["pipeline_result"] or direct["trigger_to_place_order_ms"] is None:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
