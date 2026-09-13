"""Phase 4 promotional SKU investigation.

TEST-ONLY. No production application code is modified by this test.
SAFE / observation-only: never clicks Add to Cart, Checkout, or Place Order.

The cart investigation intentionally evaluates ONLY the actual
/api/v4/cart/get response for the requested item/model. Recommendation and
other API responses are recorded separately and cannot make the cart identity
check pass. This prevents false positives when the requested model appears in
recommendation data while a different model is actually in the cart.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_action import BrowserActions
from execution.browser.browser_connector import BrowserConnector
from purchase.parser.shopee_api_parser import ShopeeAPIParser

PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"
CANONICAL_URL = "https://shopee.ph/Apple-iPhone-17-Pro-Max-i.1275798143.26342037051"
CART_URL = "https://shopee.ph/cart"
ITEM_ID = 26342037051
SHOP_ID = 1275798143
REQUESTED_VARIATION = {"Color": "Silver", "Storage": "256GB"}
OBSERVE_AFTER_NAVIGATION_SECONDS = 10
OBSERVE_CART_SECONDS = 8


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
                titles = {x["title"].strip().lower() for x in result}
                if {"color", "capacity", "storage"} & titles:
                    return result
        except Exception:
            pass
        actions.wait_for_timeout(500)
    return last_result


def capture_get_pc(browser_session, label, target_url, run_dir):
    runtime = AsyncRuntime.instance()
    page = browser_session.page
    captured = []

    async def _capture():
        def on_response(response):
            captured.append(response)

        page.on("response", on_response)
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(OBSERVE_AFTER_NAVIGATION_SECONDS * 1000)
            records = []
            get_pc = []
            for response in captured:
                records.append({
                    "url": response.url,
                    "status": response.status,
                    "method": response.request.method,
                    "resource_type": response.request.resource_type,
                })
                if "/api/v4/pdp/get_pc" in response.url:
                    try:
                        get_pc.append({"status": response.status, "url": response.url, "data": await response.json()})
                    except Exception as exc:
                        get_pc.append({"status": response.status, "url": response.url, "json_error": repr(exc)})
            return page.url, records, get_pc
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    future = runtime.submit(_capture())
    final_url, records, get_pc = future.result(timeout=50)
    save_json(run_dir / "api" / f"{label}_responses.json", records)
    parsed = []
    for index, response in enumerate([x for x in get_pc if "data" in x], start=1):
        save_json(run_dir / "api" / f"{label}_get_pc_{index:02d}.json", response["data"])
        parsed.append({"status": response["status"], "url": response["url"], "product": ShopeeAPIParser().parse(response["data"])})
    print(f"[PHASE4] {label} final URL: {final_url}")
    print(f"[PHASE4] {label} captured {len(records)} responses; get_pc={len(parsed)}")
    return final_url, records, parsed


def resolve_live_request(product):
    keys = []
    for variation in product.available_variations:
        for key in variation.options:
            if key not in keys:
                keys.append(key)
    resolved = {}
    for requested_title, requested_value in REQUESTED_VARIATION.items():
        live_title = next((k for k in keys if k.strip().lower() == requested_title.lower()), None)
        if live_title is None:
            matches = []
            for key in keys:
                values = {str(v.options.get(key, "")).strip().lower() for v in product.available_variations if key in v.options}
                if requested_value.lower() in values:
                    matches.append(key)
            if len(matches) != 1:
                raise RuntimeError(f"Could not uniquely resolve {requested_title} -> {requested_value}: {matches}")
            live_title = matches[0]
        resolved[live_title] = requested_value
        print(f"[PHASE4] Application request {requested_title} -> {requested_value} resolves to ProductInfo label {live_title} -> {requested_value}")
    return resolved


def find_matching_variations(product, request):
    return [
        v for v in product.available_variations
        if all(
            any(k.strip().lower() == wanted_key.strip().lower() and str(value).strip().lower() == wanted_value.strip().lower() for k, value in v.options.items())
            for wanted_key, wanted_value in request.items()
        )
    ]


def walk_identity(node, path="root", results=None):
    if results is None:
        results = []
    if isinstance(node, dict):
        normalized = {str(k).lower(): v for k, v in node.items()}
        item = normalized.get("item_id", normalized.get("itemid"))
        model = normalized.get("model_id", normalized.get("modelid"))
        if item is not None or model is not None:
            results.append({
                "path": path,
                "item_id": item,
                "model_id": model,
                "shop_id": normalized.get("shop_id", normalized.get("shopid")),
                "name": normalized.get("name") or normalized.get("model_name") or normalized.get("item_name"),
                "price": normalized.get("price"),
                "origin_cart_item_price": normalized.get("origin_cart_item_price"),
                "promotion_id": normalized.get("promotion_id") or normalized.get("promotionid"),
                "promotion_type": normalized.get("promotion_type") or normalized.get("promotiontype"),
            })
        for key, value in node.items():
            walk_identity(value, f"{path}.{key}", results)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk_identity(value, f"{path}[{index}]", results)
    return results


def capture_cart_evidence(browser_session, item_id, model_id, run_dir):
    """Read-only cart inspection; only /api/v4/cart/get can prove cart identity."""
    runtime = AsyncRuntime.instance()
    page = browser_session.page
    captured = []

    async def _capture():
        def on_response(response):
            if "/api/" in response.url.lower():
                captured.append(response)
        page.on("response", on_response)
        try:
            await page.goto(CART_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(OBSERVE_CART_SECONDS * 1000)
            all_records = []
            cart_get_payloads = []
            for response in captured:
                try:
                    data = await response.json()
                except Exception:
                    continue
                record = {"url": response.url, "status": response.status, "method": response.request.method, "resource_type": response.request.resource_type}
                all_records.append(record)
                if "/api/v4/cart/get" in response.url:
                    cart_get_payloads.append({"url": response.url, "status": response.status, "data": data})
            return page.url, all_records, cart_get_payloads
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    final_url, all_records, cart_get_payloads = runtime.submit(_capture()).result(timeout=50)
    save_json(run_dir / "api" / "cart_responses.json", all_records)

    actual_cart_identities = []
    for payload in cart_get_payloads:
        identities = walk_identity(payload["data"])
        actual_cart_identities.extend([x for x in identities if x["item_id"] is not None or x["model_id"] is not None])

    # The old test searched every API response. That allowed recommendation
    # data to make the cart check pass. This result is restricted to cart/get.
    exact_matches = [
        x for x in actual_cart_identities
        if str(x.get("item_id")) == str(item_id) and str(x.get("model_id")) == str(model_id)
    ]
    item_matches = [x for x in actual_cart_identities if str(x.get("item_id")) == str(item_id)]
    model_matches = [x for x in actual_cart_identities if str(x.get("model_id")) == str(model_id)]

    cart_identity = {
        "cart_final_url": final_url,
        "item_id": int(item_id),
        "requested_model_id": int(model_id),
        "cart_get_response_count": len(cart_get_payloads),
        "cart_get_identities": actual_cart_identities,
        "cart_get_exact_item_model_matches": exact_matches,
        "cart_get_item_matches": item_matches,
        "cart_get_model_matches": model_matches,
        "exact_cart_api_item_model_match": bool(exact_matches),
    }
    save_json(run_dir / "api" / "cart_identity_matches.json", cart_identity)

    actions = BrowserActions(browser_session)
    checkboxes = actions.find_all("input.stardust-checkbox__input")
    checkbox_count = actions.count(checkboxes)
    dom_matches = []
    for index in range(checkbox_count):
        current = checkboxes.nth(index)
        for level in range(1, 9):
            current = actions.parent(current)
            if current is None:
                break
            attrs = {}
            for attr in ("data-item-id", "data-model-id", "data-product-id", "data-sku-id", "data-id"):
                value = actions.attribute(current, attr)
                if value:
                    attrs[attr] = value
            text = actions.text(current)
            combined = " ".join(list(attrs.values()) + [text])
            item_match = str(item_id) in combined
            model_match = str(model_id) in combined
            if item_match or model_match:
                dom_matches.append({"checkbox_index": index, "parent_level": level, "attributes": attrs, "item_match": item_match, "model_match": model_match, "container_text": text[:1500]})
                break

    result = {
        **cart_identity,
        "dom_checkbox_count": checkbox_count,
        "dom_identity_matches": dom_matches,
        "exact_dom_item_model_match": any(x["item_match"] and x["model_match"] for x in dom_matches),
    }
    save_json(run_dir / "cart_identity.json", result)

    print()
    print("=" * 72)
    print("PHASE 4 — CART IDENTITY INVESTIGATION")
    print("=" * 72)
    print(f"[PHASE4] Cart final URL: {final_url}")
    print(f"[PHASE4] /api/v4/cart/get responses: {len(cart_get_payloads)}")
    print(f"[PHASE4] Requested cart item: {item_id}")
    print(f"[PHASE4] Requested cart model: {model_id}")
    print(f"[PHASE4] Cart API exact item+model match: {'YES' if exact_matches else 'NO'}")
    if item_matches:
        print(f"[PHASE4] Cart API item matches found: {len(item_matches)}")
        for identity in item_matches[:10]:
            print(f"[PHASE4]   actual model={identity.get('model_id')} name={identity.get('name')} price={identity.get('price')}")
    else:
        print("[PHASE4] Cart API item match: NONE")
    print(f"[PHASE4] Cart checkboxes: {checkbox_count}")
    print(f"[PHASE4] DOM exact item+model match: {'YES' if result['exact_dom_item_model_match'] else 'NO'}")
    print("[PHASE4] Cart action performed: NAVIGATION ONLY")
    print("[PHASE4] Add to Cart clicked: NO")
    print("[PHASE4] Checkout clicked: NO")
    print("[PHASE4] Place Order clicked: NO")
    print("=" * 72)
    return result


def snapshot_page(browser_session, path):
    try:
        body = BrowserActions(browser_session).find_all("body")
        save_text(path, BrowserActions(browser_session).text(body))
        print(f"[PHASE4] Saved final page: {path}")
    except Exception as exc:
        print(f"[PHASE4] Could not snapshot final page: {exc!r}")


def main():
    run_dir = make_run_dir()
    manifest = {
        "started_at": utc_now(),
        "promotional_url": PROMOTIONAL_URL,
        "canonical_url": CANONICAL_URL,
        "cart_url": CART_URL,
        "item_id": ITEM_ID,
        "shop_id": SHOP_ID,
        "requested_variation": REQUESTED_VARIATION,
        "mode": "SAFE / observation only",
        "cart_actions": False,
        "checkout_actions": False,
        "place_order_actions": False,
        "run_dir": str(run_dir),
    }
    save_json(run_dir / "summary.json", manifest)
    owner = object()
    connector = BrowserConnector()
    browser_session = None
    try:
        print("=" * 72)
        print("PHASE 4 — PROMOTIONAL SKU INVESTIGATION")
        print("=" * 72)
        print(f"Promotional URL: {PROMOTIONAL_URL}")
        print(f"Canonical URL:   {CANONICAL_URL}")
        print(f"Cart URL:        {CART_URL}")
        print(f"Item: {ITEM_ID} | Shop: {SHOP_ID}")
        print(f"Requested SKU: {REQUESTED_VARIATION}")
        print("Mode: SAFE / observation only")
        print("=" * 72)

        connector.connect()
        browser_session = connector.open_session(owner, PROMOTIONAL_URL)
        manifest["initial_connector_url"] = browser_session.page.url
        sections = collect_sections(browser_session)
        manifest["initial_live_sections"] = sections
        if sections:
            print("[PHASE4] Initial PDP sections observed:")
            for section in sections:
                print(f"[PHASE4]   {section['title']}: {section['values']}")

        promo_final_url, promo_responses, promo_get_pc = capture_get_pc(browser_session, "promotional", PROMOTIONAL_URL, run_dir)
        canonical_final_url, canonical_responses, canonical_get_pc = capture_get_pc(browser_session, "canonical", CANONICAL_URL, run_dir)
        manifest.update({
            "promotional_final_url": promo_final_url,
            "promotional_response_count": len(promo_responses),
            "promotional_get_pc_count": len(promo_get_pc),
            "promotional_get_pc_urls": [x["url"] for x in promo_get_pc],
            "canonical_final_url": canonical_final_url,
            "canonical_response_count": len(canonical_responses),
            "canonical_get_pc_count": len(canonical_get_pc),
            "canonical_get_pc_urls": [x["url"] for x in canonical_get_pc],
        })
        promo_product = promo_get_pc[-1]["product"] if promo_get_pc else None
        canonical_product = canonical_get_pc[-1]["product"] if canonical_get_pc else None
        if promo_product:
            print(f"[PHASE4] Promotional URL produced ProductInfo: {promo_product.product_name}")
        if canonical_product:
            print(f"[PHASE4] Canonical URL produced ProductInfo: {canonical_product.product_name}")
        product = promo_product or canonical_product
        if product is None:
            raise RuntimeError("Neither PDP navigation produced a parseable get_pc response.")
        if product.item_id != ITEM_ID or product.shop_id != SHOP_ID:
            raise RuntimeError(f"Unexpected ProductInfo item/shop: {product.item_id}/{product.shop_id}")

        manifest["product"] = {"item_id": product.item_id, "shop_id": product.shop_id, "product_name": product.product_name, "url": product.product_url}
        option_keys = sorted({key for v in product.available_variations for key in v.options})
        manifest["product_option_keys"] = option_keys
        print(f"[PHASE4] ProductInfo option keys: {option_keys}")
        live_request = resolve_live_request(product)
        manifest["live_test_request"] = live_request
        matching = find_matching_variations(product, live_request)
        if len(matching) != 1:
            raise RuntimeError("Live SKU resolution was not unique: " + json.dumps([{"model_id": v.model_id, "name": v.name, "options": v.options} for v in matching], ensure_ascii=False))
        variation = matching[0]
        manifest["variation"] = {"model_id": variation.model_id, "name": variation.name, "options": variation.options, "price": variation.price, "price_before_discount": variation.price_before_discount, "has_stock": variation.has_stock, "tier_index": variation.tier_index}
        print(f"[PHASE4] Exact requested live SKU: {variation.name} | model={variation.model_id}")
        print(f"[PHASE4] Live ProductInfo options: {variation.options}")

        manifest["exact_model_presence"] = {
            "model_id": variation.model_id,
            "promotional": any(v.model_id == variation.model_id for x in promo_get_pc for v in x["product"].available_variations),
            "canonical": any(v.model_id == variation.model_id for x in canonical_get_pc for v in x["product"].available_variations),
        }
        manifest["diagnosis"] = {
            "promotional_get_pc": bool(promo_get_pc),
            "canonical_get_pc": bool(canonical_get_pc),
            "promotional_resolved_to_canonical": promo_final_url != PROMOTIONAL_URL and str(ITEM_ID) in promo_final_url and str(SHOP_ID) in promo_final_url,
        }

        cart_result = capture_cart_evidence(browser_session, ITEM_ID, variation.model_id, run_dir)
        manifest["cart_investigation"] = cart_result
        snapshot_page(browser_session, run_dir / "final_page.txt")
        manifest["finished_at"] = utc_now()
        save_json(run_dir / "summary.json", manifest)

        print("=" * 72)
        print("PHASE 4 RESULT")
        print("=" * 72)
        print(f"Promotional get_pc:    {'PASS' if promo_get_pc else 'NOT OBSERVED'}")
        print(f"Canonical get_pc:      {'PASS' if canonical_get_pc else 'NOT OBSERVED'}")
        print(f"Promotional final URL: {promo_final_url}")
        print(f"Canonical final URL:   {canonical_final_url}")
        print(f"Exact SKU resolved:    PASS | model {variation.model_id}")
        print(f"Cart API exact model:  {'PASS' if cart_result['exact_cart_api_item_model_match'] else 'FAIL / NOT FOUND'}")
        print(f"Cart DOM exact model:  {'PASS' if cart_result['exact_dom_item_model_match'] else 'NOT PROVEN'}")
        print(f"Evidence directory:    {run_dir}")
        print("Add to Cart clicked:    NO")
        print("Checkout clicked:       NO")
        print("Place Order clicked:    NO")
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


if __name__ == "__main__":
    raise SystemExit(main())
