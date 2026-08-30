"""
Read-only validation that the monitored product is the product Shopee placed
into the newly-created order on /user/purchase/.

TEST-ONLY: this file does not modify the production application and does not
click Pay Now, Cancel Order, Buy Again, or any other order action. It only
opens Shopee's purchase page and observes the page's own authoritative order
list response.

Validation chain:

    monitored fingerprint
        -> /user/purchase/
        -> get_all_order_and_checkout_list
        -> checkout/order container
        -> order_list_cards[*]
        -> item_id + model_id + shop_id + product name
        -> actual order_id

A validation passes only when exactly one order card matches the supplied
monitored fingerprint and that card contains a real Order ID. This is intended
to be the final isolated proof before discussing production Discord
notification implementation.

Run from the repository root:

    python3 tests/test_monitored_order_identity.py \
        --checkout-id 241792195239038 \
        --item-id 52201950487 \
        --model-id 400189597306 \
        --shop-id 1680631055

The selectors can be changed for another monitored product. At least one
identity selector is required. Product name is optional but recommended.

Chrome must already be running with remote debugging on localhost:9222 and
logged into the Shopee account whose purchase page is being inspected.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_engine import BrowserEngine

# Reuse ONLY the parsing/matching helpers from the previous TEST file.
# Nothing from the production application is imported here.
from tests.test_purchase_order_inspector import (
    ORDER_LIST_ENDPOINT,
    PURCHASE_URL,
    OrderMatch,
    Target,
    build_match,
    iter_order_containers,
    normalize,
    safe_url,
    target_matches,
)


DEFAULT_PRODUCT_NAME = (
    "Custom Make Single Sleeved Pet Mechanical Keyboard Coiled USB To Type C "
    "Mini Micro Spiral Cable Colorful Gx12 Aviation Socket"
)
DEFAULT_ITEM_ID = 52201950487
DEFAULT_MODEL_ID = 400189597306
DEFAULT_SHOP_ID = 1680631055
DEFAULT_CHECKOUT_ID = 241792195239038


def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def money_php(value: int | None) -> str:
    if value is None:
        return "<not found>"
    return f"₱{value / 100000:,.2f}"


def print_fingerprint(target: Target) -> None:
    print("MONITORED PRODUCT FINGERPRINT")
    print(f"  Product    : {target.product_name or '<not supplied>'}")
    print(f"  Item ID    : {target.item_id if target.item_id is not None else '<any>'}")
    print(f"  Model ID   : {target.model_id if target.model_id is not None else '<any>'}")
    print(f"  Shop ID    : {target.shop_id if target.shop_id is not None else '<any>'}")
    print(f"  Checkout ID: {target.checkout_id if target.checkout_id is not None else '<any>'}")


def print_candidate(index: int, match: OrderMatch) -> None:
    print(
        f"  [{index}] order_id={match.order_id!r} "
        f"checkout_id={match.checkout_id!r} "
        f"item_id={match.item_id!r} "
        f"model_id={match.model_id!r} "
        f"shop_id={match.shop_id!r} "
        f"status={match.status!r} "
        f"product={normalize(match.product_name or '')[:100]!r}"
    )


def print_validated_order(match: OrderMatch) -> None:
    header("VALIDATED ORDER IDENTITY")
    print(f"Shop             : {match.shop_name or '<not found>'}")
    print(f"Seller username  : {match.seller_username or '<not found>'}")
    print(f"Product          : {match.product_name or '<not found>'}")
    print(f"Variation        : {match.variation or '<not found>'}")
    print(f"Quantity         : {match.quantity if match.quantity is not None else '<not found>'}")
    print()
    print(f"Monitored Item ID: {match.item_id if match.item_id is not None else '<not found>'}")
    print(f"Monitored Model ID: {match.model_id if match.model_id is not None else '<not found>'}")
    print(f"Monitored Shop ID: {match.shop_id if match.shop_id is not None else '<not found>'}")
    print()
    print(f"Checkout ID      : {match.checkout_id if match.checkout_id is not None else '<not found>'}")
    print(f"ORDER ID         : {match.order_id if match.order_id is not None else '<not found>'}")
    print()
    print(f"Item Price       : {money_php(match.item_price)}")
    print(f"Original Price   : {money_php(match.original_price)}")
    print(f"Order Price      : {money_php(match.order_price)}")
    print(f"Order Total      : {money_php(match.final_total if match.final_total is not None else match.subtotal)}")
    print(f"Status           : {match.status or '<not found>'}")
    print(f"Source API       : {safe_url(match.source_url)}")
    print(f"Container        : {match.container_type}[{match.container_index}]")


def assert_identity_is_safe(match: OrderMatch, target: Target) -> list[str]:
    """Return hard validation failures; no fuzzy inference is accepted here."""
    failures: list[str] = []

    if match.order_id is None:
        failures.append("authoritative order card has no Order ID")
    elif match.order_id <= 0:
        failures.append(f"Order ID is not positive: {match.order_id}")

    # A newly-created checkout must resolve to a distinct actual order ID.
    if target.checkout_id is not None and match.order_id == target.checkout_id:
        failures.append("Order ID equals Checkout ID; actual order ID was not resolved")

    # These fields are the hard identity keys. If supplied, they must be exact.
    if target.item_id is not None and match.item_id != target.item_id:
        failures.append(f"item_id mismatch: found {match.item_id}, expected {target.item_id}")
    if target.model_id is not None and match.model_id != target.model_id:
        failures.append(f"model_id mismatch: found {match.model_id}, expected {target.model_id}")
    if target.shop_id is not None and match.shop_id != target.shop_id:
        failures.append(f"shop_id mismatch: found {match.shop_id}, expected {target.shop_id}")

    if target.product_name:
        expected = normalize(target.product_name).casefold()
        actual = normalize(match.product_name or "").casefold()
        if expected != actual:
            failures.append("product name is not an exact normalized match")

    if target.checkout_id is not None and match.checkout_id != target.checkout_id:
        failures.append(
            f"checkout_id mismatch: found {match.checkout_id}, expected {target.checkout_id}"
        )

    if match.item_id is None or match.model_id is None or match.shop_id is None:
        failures.append("one or more hard product identity IDs are missing from the order card")

    return failures


async def run_validation(page: Any, target: Target, wait_seconds: float) -> None:
    observed: list[dict[str, Any]] = []

    async def on_response(response: Any) -> None:
        if ORDER_LIST_ENDPOINT not in response.url.lower():
            return
        if response.status != 200:
            return

        record: dict[str, Any] = {
            "url": response.url,
            "json": None,
            "error": None,
        }
        try:
            record["json"] = await response.json()
        except Exception as exc:
            record["error"] = str(exc)
        observed.append(record)

    page.on("response", on_response)

    try:
        header("SHOPEE MONITORED-TO-ORDER IDENTITY VALIDATION")
        print(f"Target URL: {PURCHASE_URL}")
        print("Mode      : READ-ONLY / VALIDATION")
        print("Actions   : NO purchase/payment/cancellation/write actions")
        print()
        print_fingerprint(target)

        print("\n[NAVIGATION] Opening /user/purchase/ in a separate browser tab...")
        await page.goto(PURCHASE_URL, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await asyncio.sleep(wait_seconds)

        header("AUTHORITATIVE ORDER LIST")
        print(f"Responses observed: {len(observed)}")

        all_matches: list[OrderMatch] = []
        for response in observed:
            payload = response.get("json")
            for index, container_type, container in iter_order_containers(payload):
                all_matches.extend(
                    build_match(
                        payload,
                        response["url"],
                        index,
                        container_type,
                        container,
                    )
                )

        unique: dict[tuple[Any, ...], OrderMatch] = {}
        for match in all_matches:
            key = (
                match.checkout_id,
                match.order_id,
                match.item_id,
                match.model_id,
                match.shop_id,
                match.product_name,
            )
            unique[key] = match
        all_matches = list(unique.values())

        print(f"Parsed order cards: {len(all_matches)}")
        for index, match in enumerate(all_matches, start=1):
            print_candidate(index, match)

        header("IDENTITY MATCH")
        matched: list[OrderMatch] = []
        rejected: list[tuple[OrderMatch, list[str]]] = []

        for match in all_matches:
            basic_ok, reasons = target_matches(match, target)
            if basic_ok:
                matched.append(match)
            else:
                rejected.append((match, reasons))

        if len(matched) != 1:
            if not matched:
                print("RESULT: FAIL — monitored product was not found in the order list")
                raise AssertionError(
                    "No order card matched the monitored product fingerprint. "
                    "The test will not claim that the placed order is the monitored item."
                )
            print(f"RESULT: FAIL — {len(matched)} matching order cards found")
            raise AssertionError(
                "Identity is ambiguous. More than one order card matched the supplied fingerprint."
            )

        match = matched[0]
        hard_failures = assert_identity_is_safe(match, target)
        if hard_failures:
            print("RESULT: FAIL — identity validation did not meet hard requirements")
            for failure in hard_failures:
                print(f"  - {failure}")
            raise AssertionError("Hard monitored-to-order identity validation failed.")

        print("RESULT: PASS — UNIQUE MONITORED PRODUCT MATCH")
        print_validated_order(match)

        header("IDENTITY PROOF")
        print("The order-list response contains the same product identity keys:")
        print(f"  item_id   : {match.item_id}")
        print(f"  model_id  : {match.model_id}")
        print(f"  shop_id   : {match.shop_id}")
        print(f"  product   : {match.product_name}")
        print(f"  variation : {match.variation}")
        print(f"  checkout  : {match.checkout_id}")
        print(f"  order_id  : {match.order_id}")
        print()
        print("This establishes the monitored-product -> created-order relationship")
        print("using Shopee's authoritative order-list response, not a guessed DOM")
        print("match. The Order ID is now safe to use as the identifier for a future")
        print("Discord order-created notification.")

        header("NEXT STEP — NOT IMPLEMENTED")
        print("No Discord request was sent.")
        print("No production application file was changed by this test.")
        print("Production Discord implementation should be discussed separately")
        print("after this validation result is reviewed.")

    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only validation that a monitored Shopee item became the located order."
    )
    parser.add_argument("--product-name", default=DEFAULT_PRODUCT_NAME)
    parser.add_argument("--item-id", type=int, default=DEFAULT_ITEM_ID)
    parser.add_argument("--model-id", type=int, default=DEFAULT_MODEL_ID)
    parser.add_argument("--shop-id", type=int, default=DEFAULT_SHOP_ID)
    parser.add_argument("--checkout-id", type=int, default=DEFAULT_CHECKOUT_ID)
    parser.add_argument("--wait-seconds", type=float, default=3.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target = Target(
        product_name=args.product_name,
        item_id=args.item_id,
        model_id=args.model_id,
        shop_id=args.shop_id,
        checkout_id=args.checkout_id,
    )

    runtime = AsyncRuntime.instance()
    engine = BrowserEngine.instance()
    owner = object()

    session = runtime.submit(engine.open_session(owner, "about:blank")).result(timeout=30)
    page = session.page

    try:
        runtime.submit(
            run_validation(page, target, max(0.0, args.wait_seconds))
        ).result(timeout=120)
    finally:
        runtime.submit(engine.close_session(owner)).result(timeout=15)


if __name__ == "__main__":
    main()
