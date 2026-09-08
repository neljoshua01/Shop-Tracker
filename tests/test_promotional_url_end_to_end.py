"""
Isolated end-to-end rehearsal for the 9.9 promotional product URL.

IMPORTANT:
    This file is TEST-ONLY. It does not modify production purchase code.

Flow exercised by the test:

    promotional URL
        -> PurchaseSession
        -> CartPreparer / variation selection
        -> Add To Cart
        -> /cart
        -> SkuPriceMonitor / get_pc
        -> PurchaseTriggerEvaluator
        -> CheckoutExecutor
        -> SAFE/ARMED Place Order gate
        -> Monitored Order Identity
        -> Successful Purchase Identity

Discord delivery is deliberately kept separate from this production-flow
rehearsal because the production checkout path does not currently invoke the
Discord renderer/sender. The existing isolated Discord test remains the
notification-layer test.

DEFAULT MODE IS SAFE:
    The test runs the real preparation + monitoring path and allows the
    checkout verifier to reach the final Place Order authorization boundary,
    but SAFE prevents an irreversible Place Order click.

REAL PURCHASE MODE:
    Pass --execute-place-order only when you intentionally want to allow the
    existing ARMED gate to perform the real Place Order action. This can place
    a real Shopee order and may require human payment/OTP interaction.

The test uses the promotional URL observed during the 9.9 campaign research:
    https://shopee.ph/product/1275798143/26342037051

Observed SKU used by default:
    Silver / 256GB
    model_id: 139454633402
"""

import argparse
import sys
from dataclasses import dataclass

from purchase.execution.purchase_pipeline import PurchasePipeline
from purchase.models.product_info import ProductInfo
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.models.trigger_condition import TriggerCondition
from purchase.models.variation import Variation
from purchase.models.payment_method import PaymentMethod


PROMOTIONAL_URL = (
    "https://shopee.ph/product/1275798143/26342037051"
)

DEFAULT_MODEL_ID = 139454633402
DEFAULT_VARIATION = {
    "Color": "Silver",
    "Storage": "256GB",
}

# The value is in Shopee's integer price representation, matching get_pc.
# It is intentionally NOT used as the default trigger target because that
# would immediately trigger against the current baseline price.
OBSERVED_BASELINE_PRICE = 7848100000


@dataclass(slots=True)
class TestResult:
    preparation_reached: bool = False
    monitor_started: bool = False
    trigger_reached: bool = False
    checkout_reached: bool = False
    place_order_authorized: bool = False
    monitored_order_verified: bool = False
    successful_purchase_verified: bool = False


def build_session(
    *,
    target_price: int | None,
    polling_interval: int,
) -> PurchaseSession:
    """Build the same runtime objects consumed by production purchase code."""

    reference = ProductReference(
        url=PROMOTIONAL_URL,
    )

    request = PurchaseRequest(
        reference=reference,
        options=dict(DEFAULT_VARIATION),
        quantity=1,
        auto_checkout=True,
        target_price=target_price,
        payment_method=PaymentMethod.SPAYLATER,
        trigger=TriggerCondition.PRICE_TARGET,
        polling_interval=polling_interval,
        lock_selected_variations=True,
    )

    product = ProductInfo(
        item_id=26342037051,
        shop_id=1275798143,
        product_name="Apple iPhone 17 Pro Max",
        shop_name="",
        product_url=PROMOTIONAL_URL,
        currency="PHP",
        image="",
        available_variations=[],
    )

    variation = Variation(
        model_id=DEFAULT_MODEL_ID,
        name="Silver / 256GB",
        options=dict(DEFAULT_VARIATION),
        price=OBSERVED_BASELINE_PRICE,
        price_before_discount=8699000000,
        has_stock=True,
        tier_index=[0, 0],
        sku_image="",
    )

    return PurchaseSession(
        request=request,
        product=product,
        variation=variation,
    )


def print_header(args):
    print()
    print("=" * 72)
    print("PROMOTIONAL URL — ISOLATED END-TO-END TEST")
    print("=" * 72)
    print(f"URL:             {PROMOTIONAL_URL}")
    print(f"Item ID:         26342037051")
    print(f"Shop ID:         1275798143")
    print(f"Model ID:        {DEFAULT_MODEL_ID}")
    print(f"Variation:       {DEFAULT_VARIATION}")
    print(f"Polling:         {args.polling_interval}s")
    print(f"Trigger target:  {args.target_price}")
    print(f"Real Place Order:{args.execute_place_order}")
    print()
    if args.execute_place_order:
        print("WARNING: REAL PURCHASE MODE ENABLED.")
        print("The existing ARMED Place Order gate may place a real order.")
    else:
        print("SAFE REHEARSAL MODE: no Place Order click is permitted.")
    print("=" * 72)
    print()


def run(args) -> int:
    print_header(args)

    # Import the production safety gate only here so the default test remains
    # fail-closed even if a previous application run left the runtime state
    # armed.
    from core.runtime.safety_gate import RuntimeSafetyGate

    safety_gate = RuntimeSafetyGate.instance()

    if not args.execute_place_order:
        print("[TEST] Forcing the runtime gate to SAFE for this rehearsal.")
        try:
            safety_gate.disarm()
        except AttributeError:
            # The test must never invent a safety API. If this version exposes
            # no disarm method, the existing gate remains authoritative and
            # CheckoutExecutor will fail closed.
            print("[TEST] Safety gate has no public disarm(); relying on its current state.")

    session = build_session(
        target_price=args.target_price,
        polling_interval=args.polling_interval,
    )

    pipeline = PurchasePipeline()

    try:
        print("[TEST] Starting production PurchasePipeline.")
        print("[TEST] No production files are modified by this test.")
        print()

        result = pipeline.run(session)

        print()
        print("=" * 72)
        print("TEST RESULT")
        print("=" * 72)
        print(f"Pipeline returned:                    {result}")
        print(f"Final session status:                 {session.status}")
        print(f"Monitored order identity verified:   {session.monitored_order_identity_verified}")
        print(f"Monitored order ID:                   {session.monitored_order_id}")
        print(f"Successful purchase identity verified:{session.successful_purchase_identity_verified}")
        print(f"Successful purchase reached To Ship: {session.successful_purchase_identity_verified}")
        print("=" * 72)

        if not result:
            print("[TEST] RESULT: FAIL — production PurchasePipeline returned False.")
            return 1

        if args.execute_place_order:
            if not session.monitored_order_identity_verified:
                print("[TEST] RESULT: FAIL — Place Order path did not establish Step 1 identity.")
                return 1
            if not session.successful_purchase_identity_verified:
                print("[TEST] RESULT: FAIL — Step 2 did not confirm the order in To Ship.")
                return 1

            print("[TEST] RESULT: PASS — real Place Order + order identity + To Ship path completed.")
            return 0

        print()
        print("[TEST] RESULT: PASS — SAFE rehearsal completed through the production final-action boundary.")
        print("[TEST] Place Order was intentionally NOT clicked.")
        print("[TEST] Run with --execute-place-order only for an intentional real-order validation.")
        return 0

    finally:
        try:
            pipeline.stop()
        except Exception as exc:
            print(f"[TEST] Pipeline stop warning: {exc}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Isolated 9.9 promotional URL end-to-end purchase-flow test."
    )
    parser.add_argument(
        "--target-price",
        type=int,
        default=None,
        help=(
            "Purchase trigger target in Shopee integer price units. "
            "Required for the normal PRICE_TARGET evaluator; choose a value "
            "that only triggers when the desired event price appears."
        ),
    )
    parser.add_argument(
        "--polling-interval",
        type=int,
        default=10,
        help="PDP/get_pc polling interval in seconds (default: 10).",
    )
    parser.add_argument(
        "--execute-place-order",
        action="store_true",
        help=(
            "Allow the existing ARMED Place Order gate to click the real "
            "Place Order button. May create a real order."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
