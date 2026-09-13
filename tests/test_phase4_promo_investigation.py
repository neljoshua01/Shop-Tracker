"""Phase 4 promotional SKU investigation.

TEST-ONLY. No production application code is modified by this test.
SAFE / observation-only: never clicks Add to Cart, Checkout, or Place Order.

The test investigates the relationship between the application-facing
"Storage" label and Shopee's live PDP/ProductInfo label (currently observed as
"Capacity") and records the exact live SKU/model used for get_pc observation.
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

PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"
ITEM_ID = 26342037051
SHOP_ID = 1275798143

REQUESTED_VARIATION = {
    "Color": "Silver",
    "Storage": "256GB",
}

NON_VARIATION_SECTIONS = {"shop vouchers", "quantity"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_run_dir():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = Path("tests/output") / f"phase4_promo_{stamp}"
    (path / "api").mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_text(path, text):
    path.write_text(text, encoding="utf-8")


def collect_sections(browser_session):
    """Read live PDP sections without assuming they render immediately."""
    actions = BrowserActions(browser_session)
    deadline = time.time() + 8
    last_result = []

    while time.time() < deadline:
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

        last_result = result
        titles = {item["title"].strip().lower() for item in result}
        if "color" in titles or "capacity" in titles or "storage" in titles:
            return result

        actions.wait_for_timeout(500)

    return last_result


def resolve_live_variation_options(sections, product):
    """Resolve the app request against live PDP/ProductInfo labels.

    DOM section discovery is diagnostic only. ProductInfo is authoritative for
    the actual parsed variation keys. This prevents a combined/duplicated
    Shopee DOM section such as "Shop Vouchers" from being mistaken for the
    variation section.
    """
    print("[PHASE4] Resolving application variation labels against live data...")

    product_keys = []
    for variation in product.available_variations:
        for key in variation.options:
            if key not in product_keys:
                product_keys.append(key)

    resolved = {}
    for requested_title, requested_value in REQUESTED_VARIATION.items():
        matching_keys = []
        for key in product_keys:
            if any(
                value.strip().lower() == requested_value.strip().lower()
                for variation in product.available_variations
                for option_key, value in variation.options.items()
                if option_key == key
            ):
                matching_keys.append(key)

        exact = next(
            (key for key in matching_keys if key.strip().lower() == requested_title.strip().lower()),
            None,
        )
        if exact is not None:
            live_title = exact
        else:
            if len(matching_keys) != 1:
                raise RuntimeError(
                    f"Could not uniquely resolve ProductInfo key for "
                    f"{requested_title} -> {requested_value}: {matching_keys}"
                )
            live_title = matching_keys[0]

        resolved[live_title] = requested_value
        print(
            f"[PHASE4] Application request {requested_title} -> {requested_value} "
            f"resolves to ProductInfo/PDP label {live_title} -> {requested_value}"
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
        print(f"[PHASE4] Could not snapshot {label}: {exc}")


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
    product_callback_owner = object()
    monitor_callback_owner = object()
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

        # Do not use a hard wait_for_selector here. Shopee's promotional PDP
        # can render its section tree asynchronously; collect_sections already
        # polls the live DOM for the relevant variation sections.
        sections = collect_sections(browser_session)
        manifest["live_sections"] = sections

        if not sections:
            raise RuntimeError(
                "No PDP sections with buttons were observed within 8 seconds."
            )

        print("[PHASE4] Live promotional PDP DOM sections observed:")
        for section in sections:
            print(f"[PHASE4]   {section['title']}: {section['values']}")

        parser = ShopeeAPIParser()
        first_product = {"value": None}

        async def product_callback(response):
            if "/api/v4/pdp/get_pc" not in response.url:
                return
            try:
                data = await response.json()
                product = parser.parse(data)
                if product.item_id == ITEM_ID and product.shop_id == SHOP_ID:
                    first_product["value"] = product
            except Exception:
                pass

        connector.engine.register_response_callback(
            product_callback_owner,
            product_callback,
            session=browser_session,
        )

        actions.reload()
        deadline = time.time() + 10
        while first_product["value"] is None and time.time() < deadline:
            actions.wait_for_timeout(250)

        connector.engine.unregister_response_callback(
            product_callback_owner,
            session=browser_session,
        )

        product = first_product["value"]
        if product is None:
            raise RuntimeError("No matching product get_pc response was captured.")

        manifest["product"] = {
            "item_id": product.item_id,
            "shop_id": product.shop_id,
            "product_name": product.product_name,
            "url": product.product_url,
        }
        print(f"[PHASE4] Product: {product.product_name}")

        live_request = resolve_live_variation_options(sections, product)
        manifest["live_test_request"] = live_request
        manifest["product_option_keys"] = sorted(
            {key for v in product.available_variations for key in v.options}
        )

        matching = find_matching_variations(product, live_request)
        if not matching:
            raise RuntimeError(
                "Requested live SKU was not found in ProductInfo. "
                f"Live request={live_request}. Parsed variations: "
                + json.dumps(
                    [
                        {"model_id": v.model_id, "name": v.name, "options": v.options}
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
                        {"model_id": v.model_id, "name": v.name, "options": v.options}
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

        print(f"[PHASE4] Exact live SKU: {variation.name} | model={variation.model_id}")
        print(f"[PHASE4] Live ProductInfo options: {variation.options}")

        sku_parser = SkuPriceParser()

        async def monitor_callback(response):
            if "/api/v4/pdp/get_pc" not in response.url:
                return

            record = {
                "timestamp": utc_now(),
                "type": "get_pc",
                "url": response.url,
                "status": response.status,
            }

            try:
                data = await response.json()
                save_json(run_dir / "api" / f"get_pc_{len(events) + 1:04d}.json", data)

                live_product = parser.parse(data)
                live_matches = [
                    v for v in live_product.available_variations
                    if v.model_id == variation.model_id
                ]
                record["product_variation"] = [
                    {
                        "model_id": v.model_id,
                        "name": v.name,
                        "options": v.options,
                        "price": v.price,
                        "price_before_discount": v.price_before_discount,
                        "has_stock": v.has_stock,
                    }
                    for v in live_matches
                ]

                state = sku_parser.parse(data, model_id=variation.model_id)
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
            except Exception as exc:
                record["error"] = str(exc)

            events.append(record)
            print("[PHASE4] get_pc", record.get("timestamp"), record.get("sku_state", {}))

        connector.engine.register_response_callback(
            monitor_callback_owner,
            monitor_callback,
            session=browser_session,
        )

        manifest["monitor_started_at"] = utc_now()
        print("[PHASE4] Beginning controlled get_pc observation...")

        end = time.time() + args.monitor_seconds
        while time.time() < end:
            if browser_session.page.is_closed():
                raise RuntimeError("Monitoring page closed during observation.")
            try:
                actions.reload()
            except Exception as exc:
                events.append({"timestamp": utc_now(), "type": "reload_error", "error": str(exc)})
                print(f"[PHASE4] Reload warning: {exc}")
            actions.wait_for_timeout(args.poll_interval * 1000)

        manifest["monitor_finished_at"] = utc_now()
        manifest["get_pc_events"] = len(events)
        snapshot_page(browser_session, run_dir / "after_monitor.txt", "post-monitor page")
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
        for callback_owner in (product_callback_owner, monitor_callback_owner):
            try:
                connector.engine.unregister_response_callback(
                    callback_owner,
                    session=browser_session,
                )
            except Exception:
                pass
        try:
            if browser_session is not None:
                connector.close_session(owner)
        except Exception as exc:
            print(f"[PHASE4] Cleanup warning: {exc}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor-seconds", type=int, default=120)
    parser.add_argument("--poll-interval", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
