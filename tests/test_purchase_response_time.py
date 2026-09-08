"""
Measure the real V2 purchase response time from trigger detection to
Place Order detection.

IMPORTANT:
    This is TEST-ONLY instrumentation. It does not wire the timing into the
    dashboard yet and it does not modify production purchase behavior.

The test runs the existing production PurchasePipeline in SAFE mode and
measures:

    PurchaseTriggerEvaluator returns True
        -> CheckoutVerifier confirms Place Order is visible

The timing hooks are applied only while this test is running. The actual
browser/cart/checkout flow remains the production flow.

DEFAULT MODE IS SAFE:
    Place Order is detected but is NOT clicked.

This test reuses the promotional URL rehearsal setup so the same live
variation discovery and production PurchasePipeline path can be exercised.
"""

import argparse
import sys
import time

from purchase.execution.purchase_pipeline import PurchasePipeline
from purchase.execution.purchase_trigger_evaluator import PurchaseTriggerEvaluator
from purchase.models.purchase_session import PurchaseSession
from execution.checkout.checkout_verifier import CheckoutVerifier
from core.runtime.safety_gate import RuntimeSafetyGate

from tests.test_promotional_url_end_to_end import (
    DEFAULT_MODEL_ID,
    OBSERVED_BASELINE_PRICE,
    PROMOTIONAL_URL,
    build_session,
    resolve_live_variation_options,
)


class ResponseTimeProbe:
    """Test-only high-resolution stopwatch for the trigger -> Place Order path."""

    def __init__(self):
        self.detection_ns = None
        self.place_order_ns = None

    def mark_detection(self):
        if self.detection_ns is None:
            self.detection_ns = time.perf_counter_ns()
            print("[ResponseTimeTest] Trigger detection timestamp captured.")

    def mark_place_order(self):
        if self.place_order_ns is None:
            self.place_order_ns = time.perf_counter_ns()
            print("[ResponseTimeTest] Place Order detection timestamp captured.")

    @property
    def elapsed_ms(self):
        if self.detection_ns is None or self.place_order_ns is None:
            return None
        return (self.place_order_ns - self.detection_ns) / 1_000_000


def install_test_timing_hooks(probe: ResponseTimeProbe):
    """Patch only the two production decision points for this test run."""

    original_evaluate = PurchaseTriggerEvaluator.evaluate
    original_verify_place_order = CheckoutVerifier.verify_place_order

    def timed_evaluate(self, session, state):
        result = original_evaluate(self, session, state)
        if result:
            probe.mark_detection()
        return result

    async def timed_verify_place_order(self, page):
        result = await original_verify_place_order(self, page)
        if result:
            probe.mark_place_order()
        return result

    PurchaseTriggerEvaluator.evaluate = timed_evaluate
    CheckoutVerifier.verify_place_order = timed_verify_place_order

    def restore():
        PurchaseTriggerEvaluator.evaluate = original_evaluate
        CheckoutVerifier.verify_place_order = original_verify_place_order

    return restore


def build_args():
    parser = argparse.ArgumentParser(
        description="Measure real V2 trigger-to-Place-Order response time."
    )
    parser.add_argument(
        "--target-price",
        type=int,
        default=OBSERVED_BASELINE_PRICE,
        help=(
            "Purchase trigger target in Shopee integer price units. "
            "Defaults to the observed promotional-test baseline so the flow "
            "can be exercised without waiting for an event."
        ),
    )
    parser.add_argument(
        "--polling-interval",
        type=int,
        default=1,
        help="PDP/get_pc polling interval in seconds (default: 1).",
    )
    return parser.parse_args()


def main() -> int:
    args = build_args()

    if args.polling_interval < 1:
        print("[ResponseTimeTest] ERROR: polling interval must be at least 1 second.")
        return 1

    print()
    print("=" * 72)
    print("V2 PURCHASE RESPONSE TIME TEST")
    print("=" * 72)
    print(f"URL:              {PROMOTIONAL_URL}")
    print(f"Item ID:          26342037051")
    print(f"Model ID:         {DEFAULT_MODEL_ID}")
    print(f"Polling:          {args.polling_interval}s")
    print(f"Trigger target:   {args.target_price}")
    print("Mode:             SAFE — Place Order will NOT be clicked")
    print("Timing:            trigger detection -> Place Order detection")
    print("=" * 72)
    print()

    safety_gate = RuntimeSafetyGate.instance()
    safety_gate.reset_to_safe()

    print("[ResponseTimeTest] Resolving live promotional PDP variation labels...")
    live_variation_options = resolve_live_variation_options()

    session: PurchaseSession = build_session(
        target_price=args.target_price,
        polling_interval=args.polling_interval,
        variation_options=live_variation_options,
    )

    probe = ResponseTimeProbe()
    restore_hooks = install_test_timing_hooks(probe)
    pipeline = PurchasePipeline()

    try:
        print("[ResponseTimeTest] Starting the REAL production PurchasePipeline.")
        print("[ResponseTimeTest] Test-only timing hooks are active.")
        print()

        pipeline_result = pipeline.run(session)

        print()
        print("=" * 72)
        print("RESPONSE TIME RESULT")
        print("=" * 72)
        print(f"Pipeline returned:       {pipeline_result}")
        print(f"Trigger detected:        {probe.detection_ns is not None}")
        print(f"Place Order detected:    {probe.place_order_ns is not None}")

        if probe.elapsed_ms is not None:
            print(f"Trigger -> Place Order:  {probe.elapsed_ms:.3f} ms")
            print(f"                         {probe.elapsed_ms / 1000:.3f} seconds")
        else:
            print("Trigger -> Place Order:  NOT MEASURED")

        print(f"Final session status:     {session.status}")
        print("=" * 72)

        if not pipeline_result:
            print("[ResponseTimeTest] RESULT: FAIL — production pipeline returned False.")
            return 1

        if probe.elapsed_ms is None:
            print(
                "[ResponseTimeTest] RESULT: FAIL — Place Order was not detected, "
                "so no valid response-time measurement was produced."
            )
            return 1

        print(
            "[ResponseTimeTest] RESULT: PASS — real production trigger-to-Place-Order "
            "response time was measured."
        )
        print("[ResponseTimeTest] Place Order was intentionally NOT clicked (SAFE mode).")
        return 0

    finally:
        restore_hooks()
        try:
            pipeline.stop()
        except Exception as exc:
            print(f"[ResponseTimeTest] Pipeline stop warning: {exc}")


if __name__ == "__main__":
    sys.exit(main())
