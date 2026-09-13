"""Phase 4 promotional SKU investigation.

TEST-ONLY. No production application code is modified by this test.
SAFE / observation-only: never clicks Add to Cart, Checkout, or Place Order.

The test investigates the relationship between the application-facing
"Storage" label and Shopee's live ProductInfo label (currently observed as
"Capacity") and records the exact live SKU/model used for get_pc observation.

The promotional PDP DOM is diagnostic only. ProductInfo is obtained from a
fresh get_pc response using Playwright's response-wait mechanism directly in
the test. This avoids depending on unstable PDP DOM structure or the
production response-callback plumbing.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from execution.browser.browser_action import BrowserActions
from execution.browser.browser_connector import BrowserConnector
from purchase.parser.shopee_api_parser import ShopeeAPIParser
from purchase.parser.sku_price_parser import SkuPriceParser
from core.runtime.async_runtime import AsyncRuntime

PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"
ITEM_ID = 26342037051
SHOP_ID = 1275798143

REQUESTED_VARIATION = {
    "Color": "Silver",
    "Storage": "256GB",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_run_dir():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = Path("tests/output") / f"phase4_promo_{stamp}"
    (path / "api").mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_text(path, text):
    path.write_text(text, encoding="utf-8")


def collect_sections(browser_session):
    """Collect PDP section/button information for diagnostics only."""
    actions = BrowserActions(browser_session)
    deadline = time.time() + 8
    last_result = []

    while time.time() < deadline:
        try:
            sections = actions.find_all("section")
            result = []

            for i in range(actions.count(sections)):
                section = sections.nth(i)
                titles = actions.find_all("h2", parent=section)
                if actions.count(titles) == 0:
                    continue

                title = actions.text(titles.first).strip()
                buttons = actions.find_all("button", parent=section)
                values = []
                for j in range(actions.count(buttons)):
                    value = actions.attribute(buttons.nth(j), "aria-label")
                    if value:
                        values.append(value.strip())

                if values:
                    result.append({"title": title, "values": values})

            if result:
                last_result = result
                titles = {item["title"].strip().lower() for item in result}
                if "color" in titles or "capacity" in titles or "storage" in titles:
                    return result
        except Exception:
            pass

        actions.wait_for_timeout(500)

    return last_result


def capture_get_pc(browser_session, label, run_dir, item_id=None, shop_id=None):
    """Reload the page and capture one matching get_pc response directly.

    This is intentionally implemented inside the test rather than through
    BrowserEngine response callbacks. The response body is consumed while
    the Playwright response is still owned by the active Playwright loop.
    """
    runtime = AsyncRuntime.instance()
    page = browser_session.page

    async def _capture():
        async with page.expect_response(
            lambda response: "/api/v4/pdp/get_pc" in response.url,
            timeout=15000,
        ) as response_info:
            await page.reload(
                wait_until="domcontentloaded",
                timeout=15000,
            )

        response = await response_info.value
        data = await response.json()
        return response.status, response.url, data

    try:
        status, url, data = runtime.submit(_capture()).result(timeout=25)
    except Exception as exc:
        raise RuntimeError(f"Could not capture {label} get_pc response: {exc!r}") from exc

    parsed = ShopeeAPIParser().parse(data)

    if item_id is not None and parsed.item_id != item_id:
        raise RuntimeError(
            f"{label} get_pc item mismatch: expected {item_id}, got {parsed.item_id}"
        )
    if shop_id is not None and parsed.shop_id != shop_id:
        raise RuntimeError(
            f"{label} get_pc shop mismatch: expected {shop_id}, got {parsed.shop_id}"
        )

    save_json(run_dir / "api" / f"{label}_get_pc.json", data)
    print(f"[PHASE4] Captured {label} get_pc: {status} {url}")
    return parsed, data, url


def resolve_live_variation_options(product):
    """Resolve the app request against live ProductInfo option keys."""
    print("[PHASE4] Resolving application variation labels against live ProductInfo...")

    product_keys = []
    for variation in product.available_variations:
        for key in variation.options:
            if key not in product_keys:
                product_keys.append(key)

    if not product_keys:
        raise RuntimeError("ProductInfo contained no variation option keys.")

    resolved = {}
    for requested_title, requested_value in REQUESTED_VARIATION.items():
        exact_key = next(
            (
                key
                for key in product_keys
                if key.strip().lower() == requested_title.strip().lower()
            ),
            None,
        )

        if exact_key is not None:
            live_title = exact_key
        else:
            matching_keys = [
                key
                for key in product_keys
                if any(
                    option_key == key
                    and str(value).strip().lower()
                    == requested_value.strip().lower()
                    for variation in product.available_variations
                    for option_key, value in variation.options.items()
                )
            ]
            if len(matching_keys) != 1:
                raise RuntimeError(
                    f"Could not uniquely resolve ProductInfo key for "
                    f"{requested_title} -> {requested_value}: {matching_keys}"
                )
            live_title = matching_keys[0]

        resolved[live_title] = requested_value
        print(
            f"[PHASE4] Application request {requested_title} -> {requested_value} "
            f"resolves to ProductInfo label {live_title} -> {requested_value}"
        )

    return resolved


def find_matching_variations(product, live_request):
    return [
        variation
        for variation in product.available_variations
        if all(
            any(
                key.strip().lower() == requested_key.strip().lower()
                and value.strip().lower() == requested_value.strip().lower()
                for key, value in variation.options.items()
            )
            for requested_key, requested_value in live_request.items()
        )
    ]


def snapshot_page(browser_session, path, label):
    actions = BrowserActions(browser_session)
    try:
        body = actions.find_all("body")
        save_text(path, actions.text(body))
        print(f"[PHASE4] Saved {label}: {path}")
    except Exception as exc:
        print(f"[PHASE4] Could not snapshot {label}: {exc!r}")


def build_sku_record(product, variation, sku_parser):
    matches = [
        v
        for v in product.available_variations
        if v.model_id == variation.model_id
    ]

    record = {
        "product_variation": [
            {
                "model_id": v.model_id,
                "name": v.name,
                "options": v.options,
                "price": v.price,
                "price_before_discount": v.price_before_discount,
                "has_stock": v.has_stock,
            }
            for v in matches
        ],
    }

    state = sku_parser.parse(
        {
            "data": {
                "item": product.raw_item,
            }
        },
        model_id=variation.model_id,
    ) if hasattr(product, "raw_item") else None

    if state is not None:
        record["sku_state"] = {
            "item_id": state.item_id,
            "model_id": state.model_id,
            "name": state.name,
            "price": state.price,
            "price_before_discount": state.price_before_discount,
            "promotion_id": state.promotion_id,
            "promotion_types": state.promotion_types,
            "promotion_price": state.promotion_price,
            "promotion_event_status": state.promotion_event_status,
            "promotion_seconds_until_start": state.promotion_seconds_until_start,
            "promotion_seconds_until_end": state.promotion_seconds_until_end,
            "promotion_is_lpp": state.promotion_is_lpp,
            "has_stock": state.has_stock,
        }

    return record


def main(args):
    run_dir = make_run_dir()
    manifest = {
        "started_at": utc_now(),
        "url": PROMOTIONAL_URL,
        "item_id": ITEM_ID,
        "shop_id": SHOP_ID,
        "requested_variation": REQUESTED_VARIATION,
        "poll_interval": args.poll_interval,
        "monitor_seconds": args.monitor_seconds,
        "mode": "SAFE / observation only",
        "run_dir": str(run_dir),
    }
    save_json(run_dir / "summary.json", manifest)

    owner = object()
    connector = BrowserConnector()
    browser_session = None
    events = []

    try:
        print("=" * 72)
        print("PHASE 4 — PROMOTIONAL SKU INVESTIGATION")
        print("=" * 72)
        print(f"URL: {PROMOTIONAL_URL}")
        print(f"Item: {ITEM_ID} | Shop: {SHOP_ID}")
        print(f"Requested SKU: {REQUESTED_VARIATION}")
        print(f"Observation: {args.monitor_seconds}s")
        print("Mode: SAFE / observation only")
        print("=" * 72)

        connector.connect()
        browser_session = connector.open_session(owner, PROMOTIONAL_URL)
        actions = BrowserActions(browser_session)
        print(f"[PHASE4] Initial URL: {browser_session.page.url}")
        manifest["initial_url"] = browser_session.page.url

        sections = collect_sections(browser_session)
        manifest["live_sections"] = sections
        if sections:
            print("[PHASE4] Live promotional PDP DOM sections observed:")
            for section in sections:
                print(f"[PHASE4]   {section['title']}: {section['values']}")
        else:
            print(
                "[PHASE4] PDP section/button DOM not observed; "
                "continuing with direct get_pc capture."
            )

        product, initial_data, initial_url = capture_get_pc(
            browser_session,
            "initial",
            run_dir,
            item_id=ITEM_ID,
            shop_id=SHOP_ID,
        )

        manifest["product"] = {
            "item_id": product.item_id,
            "shop_id": product.shop_id,
            "product_name": product.product_name,
            "url": product.product_url,
        }
        manifest["initial_get_pc_url"] = initial_url

        print(f"[PHASE4] Product: {product.product_name}")
        product_option_keys = sorted(
            {key for v in product.available_variations for key in v.options}
        )
        print(f"[PHASE4] ProductInfo option keys: {product_option_keys}")
        manifest["product_option_keys"] = product_option_keys

        live_request = resolve_live_variation_options(product)
        manifest["live_test_request"] = live_request

        matching = find_matching_variations(product, live_request)
        if not matching:
            raise RuntimeError(
                "Requested live SKU was not found in ProductInfo. "
                f"Live request={live_request}. Parsed variations: "
                + json.dumps(
                    [
                        {
                            "model_id": v.model_id,
                            "name": v.name,
                            "options": v.options,
                        }
                        for v in product.available_variations
                    ],
                    ensure_ascii=False,
                )
            )

        if len(matching) != 1:
            raise RuntimeError(
                "Live SKU resolution was not unique: "
                + json.dumps(
                    [
                        {
                            "model_id": v.model_id,
                            "name": v.name,
                            "options": v.options,
                        }
                        for v in matching
                    ],
                    ensure_ascii=False,
                )
            )

        variation = matching[0]
        manifest["variation"] = {
            "model_id": variation.model_id,
            "name": variation.name,
            "options": variation.options,
            "price": variation.price,
            "price_before_discount": variation.price_before_discount,
            "has_stock": variation.has_stock,
            "tier_index": variation.tier_index,
        }

        print(
            f"[PHASE4] Exact requested live SKU: "
            f"{variation.name} | model={variation.model_id}"
        )
        print(f"[PHASE4] Live ProductInfo options: {variation.options}")

        sku_parser = SkuPriceParser()
        manifest["monitor_started_at"] = utc_now()
        print("[PHASE4] Beginning controlled get_pc observation...")

        end = time.time() + args.monitor_seconds
        sequence = 0
        while time.time() < end:
            sequence += 1
            label = f"monitor_{sequence:04d}"
            try:
                live_product, raw_data, response_url = capture_get_pc(
                    browser_session,
                    label,
                    run_dir,
                    item_id=ITEM_ID,
                    shop_id=SHOP_ID,
                )

                live_matches = [
                    v
                    for v in live_product.available_variations
                    if v.model_id == variation.model_id
                ]

                state = sku_parser.parse(raw_data, model_id=variation.model_id)
                record = {
                    "timestamp": utc_now(),
                    "type": "get_pc",
                    "url": response_url,
                    "status": 200,
                    "product_variation": [
                        {
                            "model_id": v.model_id,
                            "name": v.name,
                            "options": v.options,
                            "price": v.price,
                            "price_before_discount": v.price_before_discount,
                            "has_stock": v.has_stock,
                        }
                        for v in live_matches
                    ],
                }

                if state is not None:
                    record["sku_state"] = {
                        "item_id": state.item_id,
                        "model_id": state.model_id,
                        "name": state.name,
                        "price": state.price,
                        "price_before_discount": state.price_before_discount,
                        "promotion_id": state.promotion_id,
                        "promotion_types": state.promotion_types,
                        "promotion_price": state.promotion_price,
                        "promotion_event_status": state.promotion_event_status,
                        "promotion_seconds_until_start": state.promotion_seconds_until_start,
                        "promotion_seconds_until_end": state.promotion_seconds_until_end,
                        "promotion_is_lpp": state.promotion_is_lpp,
                        "has_stock": state.has_stock,
                    }

                events.append(record)
                print(
                    f"[PHASE4] {label}: "
                    f"{record.get('sku_state', {})}"
                )
            except Exception as exc:
                record = {
                    "timestamp": utc_now(),
                    "type": "capture_error",
                    "error": repr(exc),
                }
                events.append(record)
                print(f"[PHASE4] {label} warning: {exc!r}")

            remaining = end - time.time()
            if remaining > 0:
                actions.wait_for_timeout(
                    min(args.poll_interval, int(remaining)) * 1000
                )

        manifest["monitor_finished_at"] = utc_now()
        manifest["get_pc_events"] = len(events)
        snapshot_page(
            browser_session,
            run_dir / "after_monitor.txt",
            "post-monitor page",
        )
        save_json(run_dir / "events.json", events)
        save_json(run_dir / "summary.json", manifest)

        print("=" * 72)
        print("PHASE 4 RESULT")
        print("=" * 72)
        print("Product loaded:       PASS")
        print(f"Live label mapping:   PASS | {REQUESTED_VARIATION} -> {live_request}")
        print(f"Exact SKU resolved:   PASS | model {variation.model_id}")
        print(f"get_pc observations:  {len(events)}")
        print(f"Evidence directory:   {run_dir}")
        print("Place Order clicked:  NO")
        print("=" * 72)
        return 0

    except Exception as exc:
        manifest["finished_at"] = utc_now()
        manifest["error"] = str(exc)
        save_json(run_dir / "summary.json", manifest)
        print(f"[PHASE4] FAILED: {exc!r}")
        return 1

    finally:
        try:
            if browser_session is not None:
                connector.close_session(owner)
        except Exception as exc:
            print(f"[PHASE4] Cleanup warning: {exc!r}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor-seconds", type=int, default=120)
    parser.add_argument("--poll-interval", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
