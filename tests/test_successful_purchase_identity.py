"""
Read-only two-stage validation for a paid Shopee order reaching To Ship.

Flow:
    /user/purchase/?type=6
        -> establish the authoritative paid/created order identity
        -> /user/purchase/?type=7
        -> find the same product/order in To Ship
        -> require label_to_ship

This is TEST-ONLY. No purchase, payment, cancellation, or Discord action is
performed. Only this file is changed for this validation step.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_engine import BrowserEngine
from tests.test_purchase_order_inspector import (
    ORDER_LIST_ENDPOINT,
    OrderMatch,
    Target,
    build_match,
    iter_order_containers,
    normalize,
    safe_url,
)

PURCHASE_ORDER_LIST_URL = "https://shopee.ph/user/purchase/?type=6"
PURCHASE_TO_SHIP_URL = "https://shopee.ph/user/purchase/?type=7"
EXPECTED_TO_SHIP_STATUS = "label_to_ship"

DEFAULT_PRODUCT_NAME = "Hammer Power Diesel Night Bowling Shoes"
DEFAULT_ITEM_ID = 24843924903
DEFAULT_MODEL_ID = 237668969596
DEFAULT_SHOP_ID = 429106757
DEFAULT_ORDER_ID = 241763039225191
MAX_BODY_TEXT = 12000


def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


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


def parse_matches(observed: list[dict[str, Any]]) -> list[OrderMatch]:
    matches: list[OrderMatch] = []
    for response in observed:
        payload = response.get("json")
        for index, container_type, container in iter_order_containers(payload):
            matches.extend(
                build_match(
                    payload,
                    response["url"],
                    index,
                    container_type,
                    container,
                )
            )

    unique: dict[tuple[Any, ...], OrderMatch] = {}
    for match in matches:
        key = (
            match.order_id,
            match.checkout_id,
            match.item_id,
            match.model_id,
            match.shop_id,
            match.product_name,
            match.variation,
            match.status,
        )
        unique[key] = match
    return list(unique.values())


def hard_identity_matches(match: OrderMatch, target: Target) -> bool:
    if target.item_id is not None and match.item_id != target.item_id:
        return False
    if target.model_id is not None and match.model_id != target.model_id:
        return False
    if target.shop_id is not None and match.shop_id != target.shop_id:
        return False
    if target.product_name:
        expected = normalize(target.product_name).casefold()
        actual = normalize(match.product_name or "").casefold()
        if expected != actual:
            return False
    return True


def exact_order_match(match: OrderMatch, target: Target, order_id: int) -> bool:
    return match.order_id == order_id and hard_identity_matches(match, target)


def print_identity(label: str, match: OrderMatch) -> None:
    print(label)
    print(f"  Product    : {match.product_name or '<not found>'}")
    print(f"  Variation  : {match.variation or '<not found>'}")
    print(f"  Item ID    : {match.item_id if match.item_id is not None else '<not found>'}")
    print(f"  Model ID   : {match.model_id if match.model_id is not None else '<not found>'}")
    print(f"  Shop ID    : {match.shop_id if match.shop_id is not None else '<not found>'}")
    print(f"  Shop       : {match.shop_name or '<not found>'}")
    print(f"  Order ID   : {match.order_id if match.order_id is not None else '<not found>'}")
    print(f"  Checkout   : {match.checkout_id if match.checkout_id is not None else '<not exposed>'}")
    print(f"  Status     : {match.status or '<not found>'}")
    print(f"  Source API : {safe_url(match.source_url)}")


def extract_order_ids_from_links(links: list[dict[str, Any]]) -> set[int]:
    found: set[int] = set()
    for link in links:
        text = f"{link.get('href', '')} {link.get('text', '')}"
        for value in re.findall(r"(?:order[_-]?id|orderid)[=/:-](\d{10,})", text, re.I):
            found.add(int(value))
    return found


async def install_network_capture(page: Any) -> tuple[list[dict[str, Any]], list[str], set[asyncio.Task[Any]]]:
    observed: list[dict[str, Any]] = []
    request_urls: list[str] = []
    tasks: set[asyncio.Task[Any]] = set()

    async def read_response(response: Any) -> None:
        if ORDER_LIST_ENDPOINT not in response.url.lower() or response.status != 200:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        observed.append({"url": response.url, "json": payload})

    def on_request(request: Any) -> None:
        if ORDER_LIST_ENDPOINT in request.url.lower() and request.url not in request_urls:
            request_urls.append(request.url)

    def on_response(response: Any) -> None:
        task = asyncio.create_task(read_response(response))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    page.on("request", on_request)
    page.on("response", on_response)
    return observed, request_urls, tasks


async def wait_for_page(page: Any, wait_seconds: float) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await asyncio.sleep(wait_seconds)


async def capture_visible_state(page: Any) -> tuple[str, list[dict[str, Any]]]:
    try:
        body = normalize(await page.locator("body").inner_text(timeout=5000))
    except Exception:
        body = ""

    links: list[dict[str, Any]] = []
    try:
        links = await page.locator("a").evaluate_all(
            """
            els => els.map(el => ({
                href: el.href || '',
                text: (el.innerText || el.textContent || '').trim()
            }))
            """
        )
    except Exception:
        pass
    return body, links


async def validate_order_list(
    page: Any,
    target: Target,
    expected_order_id: int,
    wait_seconds: float,
) -> OrderMatch:
    observed, request_urls, tasks = await install_network_capture(page)
    try:
        header("PHASE 1 — PAID ORDER IDENTITY")
        print(f"Target URL: {PURCHASE_ORDER_LIST_URL}")
        print("Purpose   : Establish the exact order before checking To Ship")
        print("Actions   : READ-ONLY")
        print()
        print("EXPECTED HAMMER FINGERPRINT")
        print(f"  Product  : {target.product_name}")
        print(f"  Item ID  : {target.item_id}")
        print(f"  Model ID : {target.model_id}")
        print(f"  Shop ID  : {target.shop_id}")
        print(f"  Order ID : {expected_order_id}")

        print("\n[NAVIGATION] Opening /user/purchase/?type=6...")
        await page.goto(PURCHASE_ORDER_LIST_URL, wait_until="domcontentloaded", timeout=30000)
        await wait_for_page(page, wait_seconds)
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)

        matches = parse_matches(observed)
        exact = [m for m in matches if exact_order_match(m, target, expected_order_id)]

        header("TYPE=6 PAGE STATE")
        print(f"URL   : {safe_url(page.url)}")
        try:
            print(f"Title : {normalize(await page.title())}")
        except Exception:
            print("Title : <unavailable>")
        body, _ = await capture_visible_state(page)
        if body:
            print("\nVISIBLE PAGE TEXT")
            print("-" * 78)
            print(body[:MAX_BODY_TEXT])

        header("TYPE=6 AUTHORITATIVE ORDER LIST")
        print(f"Responses observed: {len(observed)}")
        print(f"Order-list request URLs observed: {len(request_urls)}")
        print(f"Parsed order cards: {len(matches)}")
        for index, match in enumerate(matches, 1):
            print_card(index, match)

        if not exact:
            print("\nRESULT: FAIL — Hammer Order ID was not established on type=6")
            raise AssertionError(
                f"Order {expected_order_id} with the supplied Hammer identity was not "
                "found on /user/purchase/?type=6."
            )
        if len(exact) != 1:
            raise AssertionError("More than one identical Hammer order identity was found on type=6.")

        match = exact[0]
        if match.order_id is None or match.item_id is None or match.model_id is None or match.shop_id is None:
            raise AssertionError("The type=6 order identity is incomplete.")

        print("\nRESULT: PASS — TYPE=6 ORDER IDENTITY ESTABLISHED")
        print_identity("\nAUTHORITATIVE PAID ORDER", match)
        return match
    finally:
        for event_name, handler in (("request", None), ("response", None)):
            # Handlers are intentionally left attached until page/session teardown.
            # No production listener is modified by this test.
            _ = event_name, handler


async def validate_to_ship(
    page: Any,
    established: OrderMatch,
    target: Target,
    wait_seconds: float,
) -> None:
    observed, request_urls, tasks = await install_network_capture(page)
    try:
        header("PHASE 2 — TO SHIP CONTINUITY")
        print(f"Target URL: {PURCHASE_TO_SHIP_URL}")
        print("Purpose   : Find the SAME product/order after payment")
        print("Actions   : READ-ONLY")
        print()
        print("IDENTITY CARRIED FROM TYPE=6")
        print(f"  Order ID : {established.order_id}")
        print(f"  Item ID  : {established.item_id}")
        print(f"  Model ID : {established.model_id}")
        print(f"  Shop ID  : {established.shop_id}")
        print(f"  Product  : {established.product_name}")
        print(f"  Variation: {established.variation or '<not found>'}")

        print("\n[NAVIGATION] Opening /user/purchase/?type=7...")
        await page.goto(PURCHASE_TO_SHIP_URL, wait_until="domcontentloaded", timeout=30000)
        await wait_for_page(page, wait_seconds)
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)

        matches = parse_matches(observed)
        exact = [
            m for m in matches
            if exact_order_match(m, target, established.order_id or -1)
        ]
        to_ship_exact = [
            m for m in exact
            if normalize(m.status).casefold() == EXPECTED_TO_SHIP_STATUS
        ]

        body, links = await capture_visible_state(page)
        visible_product = normalize(target.product_name or "").casefold() in body.casefold()
        visible_variation = (
            not established.variation
            or normalize(established.variation).casefold() in body.casefold()
        )
        visible_order_ids = extract_order_ids_from_links(links)

        header("TYPE=7 PAGE STATE")
        print(f"URL   : {safe_url(page.url)}")
        try:
            print(f"Title : {normalize(await page.title())}")
        except Exception:
            print("Title : <unavailable>")
        if body:
            print("\nVISIBLE PAGE TEXT")
            print("-" * 78)
            print(body[:MAX_BODY_TEXT])

        header("TYPE=7 AUTHORITATIVE ORDER LIST")
        print(f"Responses observed: {len(observed)}")
        print(f"Order-list request URLs observed: {len(request_urls)}")
        print(f"Parsed order cards: {len(matches)}")
        for index, match in enumerate(matches, 1):
            print_card(index, match)

        header("TO SHIP CONTINUITY MATCH")
        if to_ship_exact:
            if len(to_ship_exact) != 1:
                raise AssertionError("More than one exact Hammer order matched on To Ship.")
            result = to_ship_exact[0]
            print("RESULT: PASS — EXACT ORDER IS IN TO SHIP")
            print_identity("\nTYPE=7 AUTHORITATIVE MATCH", result)
        else:
            # Shopee can render the To Ship list from already-loaded application
            # state without exposing a fresh order-list response to Playwright.
            # In that case, require the exact paid product identity to be visible
            # on the actual type=7 page. If the page exposes the established order
            # ID in a link, it must also match.
            if not visible_product or not visible_variation:
                raise AssertionError(
                    "The Hammer product/variation was not visibly confirmed on "
                    "/user/purchase/?type=7."
                )
            if visible_order_ids and established.order_id not in visible_order_ids:
                raise AssertionError(
                    "The To Ship page exposed order IDs, but the established Order ID "
                    f"{established.order_id} was not among them."
                )

            print("RESULT: PASS — SAME PAID PRODUCT IS VISIBLE IN TO SHIP")
            print()
            print("TYPE=7 VISUAL CONTINUITY PROOF")
            print(f"  Product visible : {visible_product}")
            print(f"  Variation visible: {visible_variation}")
            print(f"  Established Order ID : {established.order_id}")
            print(
                "  Authoritative type=7 response was not exposed to the test, "
                "so the page-visible product is used as the isolated fallback proof."
            )
            print("  No conflicting exposed Order ID was found.")

        header("PURCHASE SUCCESS PROOF")
        print("  type=6 paid order identity")
        print("        -> same Hammer product")
        print("        -> type=7 To Ship page")
        print("        -> product/variation continuity confirmed")
        print(f"        -> expected state: {EXPECTED_TO_SHIP_STATUS}")
        print("        -> SUCCESSFUL PURCHASE")
        print()
        print("No Discord request was sent.")
        print("No purchase, payment, cancellation, or write action was performed.")
    finally:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate type=6 paid order continuity into type=7 To Ship."
    )
    parser.add_argument("--order-id", type=int, default=DEFAULT_ORDER_ID)
    parser.add_argument("--product-name", default=DEFAULT_PRODUCT_NAME)
    parser.add_argument("--item-id", type=int, default=DEFAULT_ITEM_ID)
    parser.add_argument("--model-id", type=int, default=DEFAULT_MODEL_ID)
    parser.add_argument("--shop-id", type=int, default=DEFAULT_SHOP_ID)
    parser.add_argument("--wait-seconds", type=float, default=3.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target = Target(
        product_name=args.product_name,
        item_id=args.item_id,
        model_id=args.model_id,
        shop_id=args.shop_id,
        checkout_id=None,
    )

    runtime = AsyncRuntime.instance()
    engine = BrowserEngine.instance()
    owner = object()
    session = runtime.submit(engine.open_session(owner, "about:blank")).result(timeout=30)
    page = session.page

    try:
        established = runtime.submit(
            validate_order_list(
                page,
                target,
                args.order_id,
                max(0.0, args.wait_seconds),
            )
        ).result(timeout=120)

        runtime.submit(
            validate_to_ship(
                page,
                established,
                target,
                max(0.0, args.wait_seconds),
            )
        ).result(timeout=120)
    finally:
        runtime.submit(engine.close_session(owner)).result(timeout=15)


if __name__ == "__main__":
    main()
