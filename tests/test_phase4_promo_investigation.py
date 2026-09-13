"""
Phase 4 promotional investigation test.

TEST-ONLY: this file is isolated from production application code.
It records the live promotional SKU, get_pc state, cart identity, and checkout
state so the September 8/9.9 behavior can be investigated and compared.

Default mode is SAFE. It never clicks Place Order.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions
from purchase.parser.shopee_api_parser import ShopeeAPIParser
from purchase.parser.sku_price_parser import SkuPriceParser

PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"
ITEM_ID = 26342037051
SHOP_ID = 1275798143
REQUESTED_VARIATION = {"Color": "Silver", "Storage": "256GB"}
DEFAULT_MODEL_ID = 139454633402


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


def collect_sections(page):
    actions = BrowserActions(page)
    sections = actions.find_all("section")
    result = []
    for i in range(actions.count(sections)):
        section = sections.nth(i)
        titles = actions.find_all("h2", parent=section)
        if actions.count(titles) == 0:
            continue
        title = actions.text(titles.first)
        buttons = actions.find_all("button", parent=section)
        values = []
        for j in range(actions.count(buttons)):
            button = buttons.nth(j)
            value = actions.attribute(button, "aria-label")
            if value:
                values.append(value.strip())
        if values:
            result.append({"title": title, "values": values})
    return result


def resolve_live_variation_options(page):
    sections = collect_sections(page)
    print("[PHASE4] Live promotional PDP variation sections:")
    for section in sections:
        print(f"[PHASE4]   {section['title']}: {section['values']}")

    resolved = {}
    for requested_title, requested_value in REQUESTED_VARIATION.items():
        exact = next(
            (
                s["title"]
                for s in sections
                if s["title"].strip().lower() == requested_title.lower()
                and any(v.lower() == requested_value.lower() for v in s["values"])
            ),
            None,
        )
        if exact:
            resolved[exact] = requested_value
            continue

        matches = [
            s["title"]
            for s in sections
            if any(v.lower() == requested_value.lower() for v in s["values"])
            and s["title"].strip().lower() not in {"shop vouchers", "quantity"}
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Could not uniquely resolve {requested_title} -> {requested_value}: {matches}"
            )
        resolved[matches[0]] = requested_value

    return resolved, sections


def capture_get_pc(owner, session, run_dir):
    events = []
    connector = BrowserConnector()
    engine = connector.engine
    parser = ShopeeAPIParser()
    sku_parser = SkuPriceParser()

    async def callback(response):
        if "/api/v4/pdp/get_pc" not in response.url:
            return
        timestamp = utc_now()
        try:
            data = await response.json()
        except Exception as exc:
            events.append({"timestamp": timestamp, "type": "get_pc_error", "error": str(exc)})
            return

        record = {"timestamp": timestamp, "type": "get_pc", "url": response.url, "status": response.status}
        try:
            product = parser.parse(data)
            record["product"] = {
                "item_id": product.item_id,
                "shop_id": product.shop_id,
                "product_name": product.product_name,
                "variations": [
                    {
                        "model_id": v.model_id,
                        "name": v.name,
                        "options": v.options,
                        "price": v.price,
                        "price_before_discount": v.price_before_discount,
                        "has_stock": v.has_stock,
                    }
                    for v in product.available_variations
                    if v.model_id == session.get("model_id")
                ],
            }
        except Exception as exc:
            record["product_parse_error"] = str(exc)

        try:
            model_id = session.get("model_id", DEFAULT_MODEL_ID)
            state = sku_parser.parse(data, model_id=model_id)
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
            record["sku_parse_error"] = str(exc)

        events.append(record)
        save_json(run_dir / "api" / f"get_pc_{len(events):04d}.json", data)
        print(
            "[PHASE4] get_pc",
            record.get("timestamp"),
            record.get("sku_state", {}),
        )

    engine.register_response_callback(owner, callback, session=session["browser_session"])
    return connector, events


def snapshot_page(session, path, label):
    actions = BrowserActions(session)
    try:
        text = actions.text(actions.find_all("body"))
        save_text(path, text)
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
        "run_dir": str(run_dir),
    }
    save_json(run_dir / "summary.json", manifest)

    owner = object()
    connector = BrowserConnector()
    browser_session = None
    callback_owner = object()
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

        actions.wait_for_selector("section h2")
        live_options, sections = resolve_live_variation_options(browser_session)
        manifest["live_sections"] = sections
        manifest["resolved_variation"] = live_options

        parser = ShopeeAPIParser()
        # Capture the first product API directly through a short callback.
        first_product = {"value": None}

        async def initial_callback(response):
            if "/api/v4/pdp/get_pc" not in response.url:
                return
            try:
                data = await response.json()
                first_product["value"] = parser.parse(data)
            except Exception:
                pass

        connector.engine.register_response_callback(
            callback_owner,
            initial_callback,
            session=browser_session,
        )
        actions.reload()
        deadline = time.time() + 10
        while first_product["value"] is None and time.time() < deadline:
            actions.wait_for_timeout(250)
        connector.engine.unregister_response_callback(callback_owner, session=browser_session)

        product = first_product["value"]
        if product is None:
            raise RuntimeError("No product get_pc response was captured.")

        manifest["product"] = {
            "item_id": product.item_id,
            "shop_id": product.shop_id,
            "product_name": product.product_name,
            "url": product.product_url,
        }
        print(f"[PHASE4] Product: {product.product_name}")

        matching = [
            v for v in product.available_variations
            if all(
                any(k.lower() == rk.lower() and value.lower() == rv.lower() for k, value in v.options.items())
                for rk, rv in REQUESTED_VARIATION.items()
            )
        ]
        if not matching:
            raise RuntimeError("Requested SKU was not found in live ProductInfo.")
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

        session_info = {
            "browser_session": browser_session,
            "model_id": variation.model_id,
        }
        capture_connector, events = capture_get_pc(callback_owner, session_info, run_dir)
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
        manifest["get_pc_events"] = len([e for e in events if e.get("type") == "get_pc"])

        snapshot_page(browser_session, run_dir / "after_monitor.txt", "post-monitor page")
        save_json(run_dir / "events.json", events)
        save_json(run_dir / "summary.json", manifest)

        print()
        print("=" * 72)
        print("PHASE 4 RESULT")
        print("=" * 72)
        print(f"Product loaded:       PASS")
        print(f"Exact SKU resolved:   PASS | model {variation.model_id}")
        print(f"get_pc observations:  {manifest['get_pc_events']}")
        print(f"Evidence directory:   {run_dir}")
        print("Place Order clicked:   NO")
        print("=" * 72)
        return 0

    except Exception as exc:
        manifest["finished_at"] = utc_now()
        manifest["error"] = str(exc)
        save_json(run_dir / "summary.json", manifest)
        print(f"[PHASE4] FAILED: {exc}")
        return 1
    finally:
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
