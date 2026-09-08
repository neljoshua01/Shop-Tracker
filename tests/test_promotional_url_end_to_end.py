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

Variation compatibility note:
    The production VariationSelector matches the request against the live PDP
    section title. The promotional PDP currently exposes the storage option
    under the live section title "Capacity", while the application-facing
    request currently uses "Storage".

    This test resolves the LIVE PDP section title before constructing the
    PurchaseSession. That lets us test the full promotional URL production
    pipeline without changing production code or silently changing the
    VariationSelector itself. The test still prints the application-facing
    request and the live resolved label so the incompatibility remains visible.
"""

import argparse
import sys

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

# These are the application-facing variation labels requested for the SKU.
# The live promotional PDP may expose an equivalent option under a different
# section title; resolve_live_variation_options() discovers that title at test
# time instead of hard-coding a campaign-specific label.
REQUESTED_VARIATION = {
    "Color": "Silver",
    "Storage": "256GB",
}

DEFAULT_MODEL_ID = 139454633402

# Shopee's integer price representation observed in get_pc.
OBSERVED_BASELINE_PRICE = 7848100000


def build_session(
    *,
    target_price: int,
    polling_interval: int,
    variation_options: dict[str, str],
) -> PurchaseSession:
    """Build the same runtime objects consumed by production purchase code."""

    reference = ProductReference(
        shop_id=1275798143,
        item_id=26342037051,
        url=PROMOTIONAL_URL,
    )

    request = PurchaseRequest(
        reference=reference,
        options=dict(variation_options),
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
        options=dict(variation_options),
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


def resolve_live_variation_options():
    """
    Discover the live PDP section title for each requested variation value.

    This is test-only setup. It uses the same browser facade used by the
    production runtime and discovers the actual PDP section titles/options.

    The returned request uses the live section title so the real production
    VariationSelector can be exercised against the promotional PDP without
    modifying production code. The original application-facing request is
    retained in REQUESTED_VARIATION for diagnostics.
    """

    from execution.browser.browser_connector import BrowserConnector
    from execution.browser.browser_action import BrowserActions

    connector = BrowserConnector()
    owner = object()
    browser_session = connector.open_session(owner, PROMOTIONAL_URL)
    browser = BrowserActions(browser_session)

    try:
        browser.wait_for_selector("section h2")
        sections_locator = browser.find_all("section")
        section_count = browser.count(sections_locator)

        discovered = []

        for i in range(section_count):
            section = sections_locator.nth(i)
            titles = browser.find_all("h2", parent=section)
            if browser.count(titles) == 0:
                continue

            title = browser.text(titles.first).strip()
            buttons = browser.find_all("button", parent=section)
            button_count = browser.count(buttons)
            values = []

            for j in range(button_count):
                button = buttons.nth(j)
                value = browser.attribute(button, "aria-label")
                if value:
                    values.append(value.strip())

            if not values:
                continue

            discovered.append((title, values))

        print("[TEST] Live promotional PDP variation sections:")
        for title, values in discovered:
            print(f"[TEST]   {title}: {values}")

        resolved = {}

        for requested_title, requested_value in REQUESTED_VARIATION.items():
            exact_title_match = next(
                (
                    title
                    for title, values in discovered
                    if title.strip().lower() == requested_title.strip().lower()
                    and any(
                        value.strip().lower() == requested_value.strip().lower()
                        for value in values
                    )
                ),
                None,
            )

            if exact_title_match is not None:
                resolved[requested_title] = requested_value
                print(
                    "[TEST] Live PDP exposes exact application section: "
                    f"{requested_title} -> {requested_value}"
                )
                continue

            value_matches = [
                title
                for title, values in discovered
                if any(
                    value.strip().lower() == requested_value.strip().lower()
                    for value in values
                )
            ]

            if not value_matches:
                raise RuntimeError(
                    "Promotional PDP does not expose the requested "
                    f"variation value: {requested_title} -> {requested_value}"
                )

            # The promotional PDP can contain the same option value in an
            # unrelated section (for example Shop Vouchers). Only accept the
            # discovered variation section when it is unambiguous after
            # excluding non-variation sections that do not have the expected
            # application option structure.
            preferred_titles = [
                title
                for title in value_matches
                if title.strip().lower() not in {"shop vouchers", "quantity"}
            ]

            if len(preferred_titles) != 1:
                raise RuntimeError(
                    "Could not uniquely resolve the live promotional PDP "
                    f"section for {requested_title} -> {requested_value}: "
                    f"{value_matches}"
                )

            live_title = preferred_titles[0]
            resolved[live_title] = requested_value

            print(
                "[TEST] Application request "
                f"{requested_title} -> {requested_value} resolves to live PDP "
                f"section: {live_title} -> {requested_value}"
            )
            print(
                "[TEST] This is TEST-ONLY label resolution; "
                "production VariationSelector is unchanged."
            )

        print(
            "[TEST] Application-facing variation request: "
            f"{REQUESTED_VARIATION}"
        )
        print(
            "[TEST] Live production variation request for this rehearsal: "
            f"{resolved}"
        )
        return resolved

    finally:
        try:
            connector.close_session(owner)
        except Exception as exc:
            print(f"[TEST] Variation discovery cleanup warning: {exc}")


def print_header(args):
    print()
    print("=" * 72)
    print("PROMOTIONAL URL — ISOLATED END-TO-END TEST")
    print("=" * 72)
    print(f"URL:              {PROMOTIONAL_URL}")
    print(f"Item ID:          26342037051")
    print(f"Shop ID:          1275798143")
    print(f"Model ID:         {DEFAULT_MODEL_ID}")
    print(f"Application variation: {REQUESTED_VARIATION}")
    print(f"Polling:          {args.polling_interval}s")
    print(f"Trigger target:   {args.target_price}")
    print(f"Real Place Order: {args.execute_place_order}")
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

    from core.runtime.safety_gate import RuntimeSafetyGate

    safety_gate = RuntimeSafetyGate.instance()

    if args.execute_place_order:
        print("[TEST] Explicit real-order flag received; arming the existing runtime gate.")
        safety_gate.set_armed(True)
    else:
        print("[TEST] Forcing the runtime gate to SAFE for this rehearsal.")
        safety_gate.reset_to_safe()

    print("[TEST] Resolving promotional PDP variation labels before production pipeline.")
    live_variation_options = resolve_live_variation_options()

    session = build_session(
        target_price=args.target_price,
        polling_interval=args.polling_interval,
        variation_options=live_variation_options,
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
        print(f"Pipeline returned:                     {result}")
        print(f"Final session status:                  {session.status}")
        print(f"Monitored order identity verified:    {session.monitored_order_identity_verified}")
        print(f"Monitored order ID:                    {session.monitored_order_id}")
        print(f"Successful purchase identity verified: {session.successful_purchase_identity_verified}")
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
        default=OBSERVED_BASELINE_PRICE,
        help=(
            "Purchase trigger target in Shopee integer price units. "
            "Defaults to the observed baseline so the structural flow can "
            "be exercised before the 9.9 event. For event testing, set the "
            "desired promotional threshold instead."
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
