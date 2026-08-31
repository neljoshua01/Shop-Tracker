"""
Read-only validation that a previously validated Shopee order reaches the
To Ship purchase state after payment succeeds.

This is an ISOLATED TEST. It does not modify the production application and
it does not click Pay Now, Cancel Order, Buy Again, or any other order action.
It only opens Shopee's To Ship purchase list and observes the page's own
get_all_order_and_checkout_list response.

Validation chain:

    monitored product
        -> checkout / Place Order validation
        -> known Order ID
        -> /user/purchase/?type=7 (To Ship)
        -> authoritative order-list response
        -> matching order card
        -> same item_id + model_id + shop_id + Order ID
        -> To Ship status
        -> SUCCESSFUL PURCHASE

The purpose of this test is to establish the second half of the purchase
lifecycle independently from the earlier order-created test:

    monitored product -> order created -> paid -> To Ship

Only when the exact order is found in the To Ship state is the purchase
considered successful. No Discord request is sent by this test.

Run from the repository root:

    python3 tests/test_successful_purchase_identity.py \
        --order-id 241792195231162 \
        --item-id 52201950487 \
        --model-id 400189597306 \
        --shop-id 1680631055

The previous checkout ID may also be supplied as an additional continuity
check:

    --checkout-id 241792195239038

A product name is optional. When supplied it must match the order card after
normalization. Identity IDs and Order ID are the hard continuity keys.

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

# Reuse the already-validated read-only response parser. This does not import
# production purchase/Discord code and does not perform any write operation.
from tests.test_purchase_order_inspector import (
    ORDER_LIST_ENDPOINT,
    OrderMatch,
    Target,
    build_match,
    iter_order_containers,
    normalize,
    safe_url,
)


PURCHASE_TO_SHIP_URL = "https://shopee.ph/user/purchase/?type=7"
EXPECTED_STATUS = "label_to_ship"

DEFAULT_PRODUCT_NAME = (
    "Custom Make Single Sleeved Pet Mechanical Keyboard Coiled USB To Type C "
    "Mini Micro Spiral Cable Colorful Gx12 Aviation Socket"
)
DEFAULT_ITEM_ID = 52201950487
DEFAULT_MODEL_ID = 400189597306
DEFAULT_SHOP_ID = 1680631055
DEFAULT_CHECKOUT_ID = 241792195239038
DEFAULT_ORDER_ID = 241792195231162

MAX_BODY_TEXT = 12000


def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def money_php(value: int | None) -> str:
    if value is None:
        return "<not found>"
    return f"₱{value / 100000:,.2f}"


def print_target(target: Target, order_id: int) -> None:
    print("ORIGINAL MONITORED-ORDER FINGERPRINT")
    print(f"  Product    : {target.product_name or '<not supplied>'}")
    print(f"  Item ID    : {target.item_id if target.item_id is not None else '<any>'}")
    print(f"  Model ID   : {target.model_id if target.model_id is not None else '<any>'}")
    print(f"  Shop ID    : {target.shop_id if target.shop_id is not None else '<any>'}")
    print(f"  Checkout ID: {target.checkout_id if target.checkout_id is not None else '<any>'}")
    print(f"  Order ID   : {order_id}")


def print_card(index: int, match: OrderMatch) -> None:
    print(
        f"  [{index}] order_id={match.order_id!r} "
        f"checkout_id={match.checkout_id!r} "
        f"item_id={match.item_id!r} "
        f"model_id={match.model_id!r} "
        f"shop_id={match.shop_id!r} "
        f"status={match.status!r} "
        f"product={normalize(match.product_name or '')[:100]!r}"
    )


def continuity_failures(
    match: OrderMatch,
    target: Target,
    expected_order_id: int,
) -> list[str]:
    """Return only hard failures for the successful-purchase proof."""
    failures: list[str] = []

    if match.order_id != expected_order_id:
        failures.append(
            f"Order ID mismatch: found {match.order_id}, expected {expected_order_id}"
        )

    if target.item_id is not None and match.item_id != target.item_id:
        failures.append(
            f"item_id mismatch: found {match.item_id}, expected {target.item_id}"
        )

    if target.model_id is not None and match.model_id != target.model_id:
        failures.append(
            f"model_id mismatch: found {match.model_id}, expected {target.model_id}"
        )

    if target.shop_id is not None and match.shop_id != target.shop_id:
        failures.append(
            f"shop_id mismatch: found {match.shop_id}, expected {target.shop_id}"
        )

    if target.checkout_id is not None:
        # Some To Ship order-list responses no longer expose checkout_id. In
        # that case Order ID + item/model/shop identity proves continuity. If
        # checkout_id is present, however, it must agree exactly.
        if match.checkout_id is not None and match.checkout_id != target.checkout_id:
            failures.append(
                f"checkout_id mismatch: found {match.checkout_id}, expected {target.checkout_id}"
            )

    if target.product_name:
        expected = normalize(target.product_name).casefold()
        actual = normalize(match.product_name or "").casefold()
        if expected != actual:
            failures.append("product name is not an exact normalized match")

    if match.item_id is None or match.model_id is None or match.shop_id is None:
        failures.append("one or more hard product identity IDs are missing")

    if match.order_id is None:
        failures.append("matched order card has no Order ID")

    return failures


def print_validated_purchase(match: OrderMatch) -> None:
    header("SUCCESSFUL PURCHASE — VALIDATED ORDER")
    print(f"Shop             : {match.shop_name or '<not found>'}")
    print(f"Seller username  : {match.seller_username or '<not found>'}")
    print(f"Product          : {match.product_name or '<not found>'}")
    print(f"Variation        : {match.variation or '<not found>'}")
    print(f"Quantity         : {match.quantity if match.quantity is not None else '<not found>'}")
    print()
    print(f"Item ID          : {match.item_id if match.item_id is not None else '<not found>'}")
    print(f"Model ID         : {match.model_id if match.model_id is not None else '<not found>'}")
    print(f"Shop ID          : {match.shop_id if match.shop_id is not None else '<not found>'}")
    print(f"Checkout ID      : {match.checkout_id if match.checkout_id is not None else '<not exposed on To Ship response>'}")
    print(f"ORDER ID         : {match.order_id if match.order_id is not None else '<not found>'}")
    print()
    print(f"Item Price       : {money_php(match.item_price)}")
    print(f"Original Price   : {money_php(match.original_price)}")
    print(f"Order Price      : {money_php(match.order_price)}")
    print(f"Order Total      : {money_php(match.final_total if match.final_total is not None else match.subtotal)}")
    print()
    print(f"Status           : {match.status or '<not found>'}")
    print(f"Source API       : {safe_url(match.source_url)}")
    print(f"Container        : {match.container_type}[{match.container_index}]")


def successful_purchase_payload_candidate(
    match: OrderMatch,
    checkout_id: int | None,
) -> dict[str, Any]:
    """Local candidate only; deliberately never sends anything to Discord."""
    return {
        "event": "purchase_successful",
        "status": match.status,
        "order_id": match.order_id,
        "checkout_id": checkout_id,
        "shop": match.shop_name,
        "seller": match.seller_username,
        "product": match.product_name,
        "variation": match.variation,
        "quantity": match.quantity,
        "item_price_php": round((match.item_price or 0) / 100000, 2)
        if match.item_price is not None
        else None,
        "original_price_php": round((match.original_price or 0) / 100000, 2)
        if match.original_price is not None
        else None,
        "order_price_php": round((match.order_price or 0) / 100000, 2)
        if match.order_price is not None
        else None,
        "order_total_php": round(
            ((match.final_total if match.final_total is not None else match.subtotal) or 0)
            / 100000,
            2,
        )
        if (match.final_total is not None or match.subtotal is not None)
        else None,
    }


async def validate_to_ship(
    page: Any,
    target: Target,
    expected_order_id: int,
    wait_seconds: float,
) -> None:
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
        header("SHOPEE SUCCESSFUL PURCHASE VALIDATION")
        print(f"Target URL: {PURCHASE_TO_SHIP_URL}")
        print("Mode      : READ-ONLY / VALIDATION")
        print("Actions   : NO purchase/payment/cancellation/write actions")
        print()
        print_target(target, expected_order_id)

        print("\n[NAVIGATION] Opening /user/purchase/?type=7 in a separate browser tab...")
        await page.goto(PURCHASE_TO_SHIP_URL, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await asyncio.sleep(wait_seconds)

        header("PAGE STATE")
        print(f"URL   : {safe_url(page.url)}")
        try:
            print(f"Title : {normalize(await page.title())}")
        except Exception:
            print("Title : <unavailable>")

        body_text = ""
        try:
            body_text = normalize(await page.locator("body").inner_text(timeout=5000))
        except Exception as exc:
            print(f"Body  : <unavailable: {exc}>")

        if body_text:
            print("\nVISIBLE PAGE TEXT")
            print("-" * 78)
            print(body_text[:MAX_BODY_TEXT])
            if len(body_text) > MAX_BODY_TEXT:
                print("... <body text truncated>")

        header("AUTHORITATIVE TO SHIP ORDER LIST")
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
                match.order_id,
                match.checkout_id,
                match.item_id,
                match.model_id,
                match.shop_id,
                match.product_name,
                match.status,
            )
            unique[key] = match
        all_matches = list(unique.values())

        print(f"Parsed order cards: {len(all_matches)}")
        for index, match in enumerate(all_matches, start=1):
            print_card(index, match)

        header("ORDER CONTINUITY MATCH")
        candidates: list[OrderMatch] = []
        for match in all_matches:
            if match.order_id != expected_order_id:
                continue
            if target.item_id is not None and match.item_id != target.item_id:
                continue
            if target.model_id is not None and match.model_id != target.model_id:
                continue
            if target.shop_id is not None and match.shop_id != target.shop_id:
                continue
            candidates.append(match)

        if len(candidates) == 0:
            print("RESULT: FAIL — the validated Order ID/product was not found in To Ship")
            raise AssertionError(
                "The exact previously validated order was not found on /user/purchase/?type=7. "
                "The application must not classify the purchase as successful."
            )

        if len(candidates) > 1:
            print(f"RESULT: FAIL — {len(candidates)} identical continuity candidates found")
            for match in candidates:
                print_card(0, match)
            raise AssertionError(
                "More than one To Ship card matched the same hard order/product identity."
            )

        match = candidates[0]
        failures = continuity_failures(match, target, expected_order_id)
        if failures:
            print("RESULT: FAIL — continuity proof did not meet hard requirements")
            for failure in failures:
                print(f"  - {failure}")
            raise AssertionError("Successful-purchase identity validation failed.")

        header("PURCHASE STATE VALIDATION")
        print(f"Observed status: {match.status!r}")
        print(f"Required status: {EXPECTED_STATUS!r}")

        if normalize(match.status).casefold() != EXPECTED_STATUS:
            print("RESULT: FAIL — order is not in the To Ship state")
            raise AssertionError(
                f"Order {expected_order_id} was found, but its authoritative status is "
                f"{match.status!r}, not {EXPECTED_STATUS!r}."
            )

        print("RESULT: PASS — EXACT ORDER IS IN TO SHIP")
        print("The monitored product, its created Order ID, and its To Ship state")
        print("have now been independently verified from Shopee's order-list response.")

        print_validated_purchase(match)

        header("PURCHASE SUCCESS PROOF")
        print("This establishes the lifecycle continuity:")
        print("  monitored product")
        print("        -> checkout / Place Order")
        print("        -> created Order ID")
        print("        -> payment completed")
        print("        -> /user/purchase/?type=7")
        print("        -> same item_id + model_id + shop_id")
        print("        -> same Order ID")
        print("        -> status label_to_ship")
        print("        -> SUCCESSFUL PURCHASE")
        print()
        print("Only after this proof is available should the future Discord")
        print("'successful purchase' notification be triggered.")

        header("DISCORD PAYLOAD CANDIDATE — NOT SENT")
        print(
            json.dumps(
                successful_purchase_payload_candidate(match, target.checkout_id),
                ensure_ascii=False,
                indent=2,
            )
        )

        header("VALIDATION COMPLETE")
        print("Successful purchase was validated in read-only mode.")
        print("No purchase, payment, cancellation, or write action was performed.")
        print("No Discord request was sent.")

    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that a previously created order is now in Shopee To Ship."
    )
    parser.add_argument("--order-id", type=int, default=DEFAULT_ORDER_ID)
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
            validate_to_ship(
                page,
                target,
                args.order_id,
                max(0.0, args.wait_seconds),
            )
        ).result(timeout=120)
    finally:
        runtime.submit(engine.close_session(owner)).result(timeout=15)


if __name__ == "__main__":
    main()
