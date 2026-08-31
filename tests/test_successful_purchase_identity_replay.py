"""
Replay test for the production Step 2 To Ship identity validator.

This test does NOT place an order and does NOT perform payment, cancellation,
or any other write action. It replays the exact Step 1 identity established
by the already-validated Hammer purchase and runs the SAME production
SuccessfulPurchaseIdentityInspector used by CheckoutExecutor.

Purpose:
    Prove that the production Step 2 implementation can recognize the already
    paid Hammer order on /user/purchase/?type=7 without requiring another
    real purchase.

Run from the repository root:

    python3 tests/test_successful_purchase_identity_replay.py \
        --order-id 241763039225191 \
        --item-id 24843924903 \
        --model-id 237668969596 \
        --shop-id 429106757

Chrome must already be running with remote debugging on localhost:9222 and
logged into the Shopee account whose To Ship page is being inspected.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_engine import BrowserEngine
from purchase.services.successful_purchase_identity import (
    EXPECTED_TO_SHIP_STATUS,
    SuccessfulPurchaseIdentityInspector,
)


DEFAULT_PRODUCT_NAME = "Hammer Power Diesel Night Bowling Shoes"
DEFAULT_VARIATION = "Right Handed,US 9 (JP26.5cm)"
DEFAULT_ORDER_ID = 241763039225191
DEFAULT_ITEM_ID = 24843924903
DEFAULT_MODEL_ID = 237668969596
DEFAULT_SHOP_ID = 429106757


def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay production Step 2 against an already-paid To Ship order."
    )
    parser.add_argument("--order-id", type=int, default=DEFAULT_ORDER_ID)
    parser.add_argument("--item-id", type=int, default=DEFAULT_ITEM_ID)
    parser.add_argument("--model-id", type=int, default=DEFAULT_MODEL_ID)
    parser.add_argument("--shop-id", type=int, default=DEFAULT_SHOP_ID)
    parser.add_argument("--product-name", default=DEFAULT_PRODUCT_NAME)
    parser.add_argument("--variation", default=DEFAULT_VARIATION)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def build_replay_session(args: argparse.Namespace) -> SimpleNamespace:
    product = SimpleNamespace(
        item_id=args.item_id,
        shop_id=args.shop_id,
        product_name=args.product_name,
    )
    variation = SimpleNamespace(
        model_id=args.model_id,
        name=args.variation,
    )
    return SimpleNamespace(
        product=product,
        variation=variation,
        monitored_order_id=args.order_id,
        monitored_order_identity_verified=True,
    )


async def run_replay(page, args: argparse.Namespace) -> None:
    session = build_replay_session(args)
    inspector = SuccessfulPurchaseIdentityInspector()

    header("PRODUCTION STEP 2 REPLAY VALIDATION")
    print("Mode      : READ-ONLY / REPLAY")
    print("Actions   : NO purchase/payment/cancellation/write actions")
    print()
    print("REPLAYED STEP 1 IDENTITY")
    print(f"  Product  : {args.product_name}")
    print(f"  Variation: {args.variation}")
    print(f"  Item ID  : {args.item_id}")
    print(f"  Model ID : {args.model_id}")
    print(f"  Shop ID  : {args.shop_id}")
    print(f"  Order ID : {args.order_id}")
    print()
    print("The test now calls the production SuccessfulPurchaseIdentityInspector")
    print("directly. No duplicate Step 2 matching implementation is used here.")

    result = await inspector.inspect(page, session)
    if result is None:
        raise AssertionError(
            "Production Step 2 did not validate the supplied paid order on To Ship."
        )

    if result.order_id != args.order_id:
        raise AssertionError(
            f"Validated Order ID changed: found {result.order_id}, expected {args.order_id}."
        )
    if result.item_id != args.item_id:
        raise AssertionError(
            f"Validated Item ID changed: found {result.item_id}, expected {args.item_id}."
        )
    if result.model_id != args.model_id:
        raise AssertionError(
            f"Validated Model ID changed: found {result.model_id}, expected {args.model_id}."
        )
    if result.shop_id != args.shop_id:
        raise AssertionError(
            f"Validated Shop ID changed: found {result.shop_id}, expected {args.shop_id}."
        )
    if result.status != EXPECTED_TO_SHIP_STATUS:
        raise AssertionError(
            f"Unexpected Step 2 status: found {result.status!r}, expected {EXPECTED_TO_SHIP_STATUS!r}."
        )

    header("REPLAY RESULT")
    print("RESULT: PASS — PRODUCTION STEP 2 RECOGNIZED THE SAME PAID ORDER")
    print(f"  Order ID : {result.order_id}")
    print(f"  Item ID  : {result.item_id}")
    print(f"  Model ID : {result.model_id}")
    print(f"  Shop ID  : {result.shop_id}")
    print(f"  Product  : {result.product_name}")
    print(f"  Variation: {result.variation or '<not exposed>'}")
    print(f"  Status   : {result.status}")
    print(
        "  Evidence : "
        + (
            "authoritative order-list response"
            if result.authoritative
            else "page-visible continuity fallback"
        )
    )
    print()
    print("No real purchase was performed by this replay test.")
    print("No payment action was performed by this replay test.")
    print("No Discord request was sent.")


def main() -> None:
    args = parse_args()
    # The production inspector reads this environment variable for its own
    # timeout. Keep the replay bounded so validation does not wait 30 minutes.
    import os

    os.environ["SHOPEE_SUCCESSFUL_PURCHASE_TIMEOUT_SECONDS"] = str(
        max(30.0, args.timeout_seconds)
    )

    runtime = AsyncRuntime.instance()
    engine = BrowserEngine.instance()
    owner = object()

    session = runtime.submit(engine.open_session(owner, "about:blank")).result(timeout=30)
    page = session.page

    try:
        runtime.submit(run_replay(page, args)).result(timeout=max(120, int(args.timeout_seconds) + 60))
    finally:
        runtime.submit(engine.close_session(owner)).result(timeout=15)


if __name__ == "__main__":
    main()
