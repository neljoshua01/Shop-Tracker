"""Phase 4 — promotional price-state investigation.

TEST-ONLY. This file is the only file changed by this investigation.

Goal:
    Determine whether the promotional get_pc price observed by the monitor is
    the same price/promotion state that reaches cart and checkout, or whether
    checkout receives a different price state.

Safety boundary:
    - Existing production CartPreparer/Add To Cart: YES.
    - Existing production variation selection: YES.
    - Cart checkbox selection: TEST-ONLY reproduction of current identity path.
    - Check Out navigation: YES, observation only.
    - Payment selection: NO.
    - Place Order: NO.
    - settings.json: NOT read or modified.
    - Production application code: NOT modified.

This test intentionally does not execute CheckoutExecutor.execute().
It captures response bodies from PDP get_pc, cart/get, and checkout-related
API calls and correlates item_id/model_id/price/promotion fields so the final
report can distinguish a SKU-identity problem from a promotional-price-state
problem.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_action import BrowserActions
from execution.browser.browser_connector import BrowserConnector
from purchase.execution.cart_preparer import CartPreparer
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.parser.shopee_api_parser import ShopeeAPIParser

PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"
CANONICAL_URL = "https://shopee.ph/Apple-iPhone-17-Pro-Max-i.1275798143.26342037051"
CART_URL = "https://shopee.ph/cart"
ITEM_ID = 26342037051
SHOP_ID = 1275798143
REQUESTED_VARIATION = {"Color": "Silver", "Storage": "256GB"}
QUANTITY = 1
OBSERVE_SECONDS = 8

PRICE_KEYS = {
    "price",
    "price_before_discount",
    "origin_cart_item_price",
    "promotion_price",
    "promotion_price_before_discount",
    "discount_price",
    "final_price",
    "unit_price",
    "item_price",
    "merchandise_subtotal",
}
PROMO_KEYS = {
    "promotion_id",
    "promotionid",
    "promotion_type",
    "promotion_type_id",
    "discount_promotion_id",
    "discount_promotion_type",
    "current_promotion_id",
    "current_promotion_type",
    "promotion_price",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_run_dir():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = Path("tests/output") / f"phase4_promo_price_state_{stamp}"
    (path / "api").mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def save_text(path, text):
    path.write_text(text, encoding="utf-8")


def normalize_key(key):
    return str(key).strip().lower()


def number_like(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        raw = value.replace(",", "").replace("₱", "").strip()
        try:
            return float(raw)
        except ValueError:
            return value
    return value


def extract_price_promo_records(node, path="root", out=None):
    """Find API objects that carry target item/model plus price/promo fields."""
    if out is None:
        out = []
    if isinstance(node, dict):
        norm = {normalize_key(k): v for k, v in node.items()}
        item = norm.get("item_id", norm.get("itemid"))
        model = norm.get("model_id", norm.get("modelid"))
        shop = norm.get("shop_id", norm.get("shopid"))
        has_price = any(k in norm for k in PRICE_KEYS)
        has_promo = any(k in norm for k in PROMO_KEYS)
        if (str(item) == str(ITEM_ID) or str(model) == str(CURRENT_MODEL)) and (has_price or has_promo):
            record = {
                "path": path,
                "item_id": item,
                "model_id": model,
                "shop_id": shop,
                "name": norm.get("name") or norm.get("model_name") or norm.get("item_name"),
            }
            for key in sorted(PRICE_KEYS | PROMO_KEYS):
                if key in norm:
                    record[key] = number_like(norm[key])
            out.append(record)
        for key, value in node.items():
            extract_price_promo_records(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            extract_price_promo_records(value, f"{path}[{index}]", out)
    return out


def extract_all_identity_records(node, path="root", out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        norm = {normalize_key(k): v for k, v in node.items()}
        item = norm.get("item_id", norm.get("itemid"))
        model = norm.get("model_id", norm.get("modelid"))
        if item is not None or model is not None:
            out.append({
                "path": path,
                "item_id": item,
                "model_id": model,
                "shop_id": norm.get("shop_id", norm.get("shopid")),
                "name": norm.get("name") or norm.get("model_name") or norm.get("item_name"),
                "price": number_like(norm.get("price")),
                "price_before_discount": number_like(norm.get("price_before_discount")),
                "origin_cart_item_price": number_like(norm.get("origin_cart_item_price")),
                "promotion_id": norm.get("promotion_id", norm.get("promotionid")),
                "promotion_type": norm.get("promotion_type", norm.get("promotiontype")),
            })
        for key, value in node.items():
            extract_all_identity_records(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            extract_all_identity_records(value, f"{path}[{index}]", out)
    return out


def capture_responses(browser_session, run_dir, target_url, phase):
    runtime = AsyncRuntime.instance()
    page = browser_session.page
    captured = []

    async def _capture():
        def on_response(response):
            captured.append(response)
        page.on("response", on_response)
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(OBSERVE_SECONDS * 1000)
            records = []
            for index, response in enumerate(captured, start=1):
                url = response.url
                low = url.lower()
                relevant = (
                    "/api/v4/pdp/get_pc" in low
                    or "/api/v4/cart/get" in low
                    or "/api/v4/checkout" in low
                    or "/api/v4/order" in low
                    or "/api/v4/cart/" in low
                    or "/checkout" in low
                )
                if not relevant:
                    continue
                entry = {
                    "index": index,
                    "url": url,
                    "status": response.status,
                    "method": response.request.method,
                    "resource_type": response.request.resource_type,
                }
                try:
                    body = await response.json()
                    entry["json"] = body
                    entry["identity_records"] = extract_all_identity_records(body)
                    entry["price_promo_records"] = extract_price_promo_records(body)
                except Exception as exc:
                    entry["json_error"] = repr(exc)
                records.append(entry)
            return page.url, records
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    final_url, records = runtime.submit(_capture()).result(timeout=60)
    save_json(run_dir / "api" / f"{phase}_responses.json", records)
    return final_url, records


def summarize_records(records, phase):
    price_records = []
    identity_records = []
    for response in records:
        price_records.extend(response.get("price_promo_records", []))
        identity_records.extend(response.get("identity_records", []))
    summary = {
        "phase": phase,
        "response_count": len(records),
        "target_price_promo_records": price_records,
        "target_identity_records": [
            r for r in identity_records
            if str(r.get("item_id")) == str(ITEM_ID) or str(r.get("model_id")) == str(CURRENT_MODEL)
        ],
    }
    save_json(RUN_DIR / "api" / f"{phase}_price_state_summary.json", summary)
    return summary


def resolve_live_variation(product):
    keys = []
    for variation in product.available_variations:
        for key in variation.options:
            if key not in keys:
                keys.append(key)
    resolved = {}
    for requested_title, requested_value in REQUESTED_VARIATION.items():
        live_title = next((key for key in keys if key.strip().lower() == requested_title.strip().lower()), None)
        if live_title is None:
            matches = []
            for key in keys:
                values = {str(v.options.get(key, "")).strip().lower() for v in product.available_variations if key in v.options}
                if requested_value.strip().lower() in values:
                    matches.append(key)
            if len(matches) != 1:
                raise RuntimeError(f"Could not uniquely resolve {requested_title} -> {requested_value}: {matches}")
            live_title = matches[0]
        resolved[live_title] = requested_value
        print(f"[PHASE4] {requested_title} -> {requested_value} resolves to live {live_title} -> {requested_value}")
    return resolved


def find_matching_variations(product, request):
    matches = []
    for variation in product.available_variations:
        ok = all(
            any(
                key.strip().lower() == wanted_key.strip().lower()
                and str(value).strip().lower() == wanted_value.strip().lower()
                for key, value in variation.options.items()
            )
            for wanted_key, wanted_value in request.items()
        )
        if ok:
            matches.append(variation)
    return matches


def capture_checkout_only(browser_session, decision, run_dir):
    """Select the same cart row path, then capture checkout API bodies."""
    actions = BrowserActions(browser_session)
    checkboxes = actions.find_all("input.stardust-checkbox__input")
    if actions.count(checkboxes) == 0:
        raise RuntimeError("No cart checkboxes found.")

    if decision["strategy"] == "stable_item_identity":
        checkbox = checkboxes.nth(decision["checkbox_index"])
    else:
        products = actions.find_all(f"text={decision['product_name']}")
        if actions.count(products) == 0:
            raise RuntimeError("Fallback product-name locator disappeared.")
        current = actions.first(products)
        checkbox = None
        for _ in range(8):
            current = actions.parent(current)
            if current is None:
                break
            found = actions.find_all("input.stardust-checkbox__input", parent=current)
            if actions.count(found) > 0:
                checkbox = actions.first(found)
                break
        if checkbox is None:
            raise RuntimeError("Fallback checkbox disappeared.")

    before = actions.attribute(checkbox, "aria-checked")
    if before != "true":
        parent = actions.parent(checkbox)
        ui = actions.find_all(".stardust-checkbox__box", parent=parent)
        if actions.count(ui) == 0:
            raise RuntimeError("Visible checkbox UI not found.")
        actions.click(actions.first(ui))
        actions.wait_for_timeout(500)
    after = actions.attribute(checkbox, "aria-checked")
    print(f"[PHASE4] Checkbox aria-checked: {before} -> {after}")
    if after != "true":
        raise RuntimeError("Target cart row was not selected.")

    checkout_buttons = actions.find_all("button:has-text('Check Out')")
    if actions.count(checkout_buttons) == 0:
        raise RuntimeError("Check Out button not found.")

    runtime = AsyncRuntime.instance()
    page = browser_session.page
    captured = []

    async def _checkout():
        def on_response(response):
            low = response.url.lower()
            if "/api/v4/" in low or "/checkout" in low:
                captured.append(response)
        page.on("response", on_response)
        try:
            await actions.first(checkout_buttons).evaluate("el => el.click()")
            await page.wait_for_timeout(OBSERVE_SECONDS * 1000)
            records = []
            for index, response in enumerate(captured, start=1):
                entry = {
                    "index": index,
                    "url": response.url,
                    "status": response.status,
                    "method": response.request.method,
                    "resource_type": response.request.resource_type,
                }
                try:
                    body = await response.json()
                    entry["json"] = body
                    entry["identity_records"] = extract_all_identity_records(body)
                    entry["price_promo_records"] = extract_price_promo_records(body)
                except Exception as exc:
                    entry["json_error"] = repr(exc)
                records.append(entry)
            return page.url, records
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    checkout_url, records = runtime.submit(_checkout()).result(timeout=60)
    save_json(run_dir / "api" / "checkout_api_bodies.json", records)

    actions = BrowserActions(browser_session)
    body_text = actions.text(actions.find_all("body"))
    save_text(run_dir / "checkout_page.txt", body_text)
    return checkout_url, records, body_text


def inspect_current_cart_identity(browser_session, run_dir, model_id, product_name):
    actions = BrowserActions(browser_session)
    checkboxes = actions.find_all("input.stardust-checkbox__input")
    count = actions.count(checkboxes)
    target = None
    traces = []

    for index in range(count):
        checkbox = checkboxes.nth(index)
        current = checkbox
        parent_trace = []
        for level in range(1, 9):
            current = actions.parent(current)
            if current is None:
                break
            attrs = {}
            for name in ("data-item-id", "data-model-id", "data-product-id", "data-sku-id", "data-id"):
                value = actions.attribute(current, name)
                if value:
                    attrs[name] = str(value)
            text = actions.text(current) or ""
            haystack = " ".join(attrs.values()) + " " + text
            item_match = str(ITEM_ID) in haystack
            model_match = str(model_id) in haystack
            parent_trace.append({"level": level, "attributes": attrs, "text": text[:1000], "item_match": item_match, "model_match": model_match})
            if item_match:
                target = {
                    "strategy": "stable_item_identity",
                    "checkbox_index": index,
                    "parent_level": level,
                    "model_identity_exposed": model_match,
                    "parent_trace": parent_trace,
                }
                break
        traces.append({"checkbox_index": index, "parent_trace": parent_trace})
        if target:
            break

    product_count = 0
    if target is None:
        products = actions.find_all(f"text={product_name}")
        product_count = actions.count(products)
        if product_count:
            current = actions.first(products)
            for level in range(1, 9):
                current = actions.parent(current)
                if current is None:
                    break
                found = actions.find_all("input.stardust-checkbox__input", parent=current)
                found_count = actions.count(found)
                if found_count:
                    target = {
                        "strategy": "product_name_fallback",
                        "product_name_match_count": product_count,
                        "fallback_parent_level": level,
                        "fallback_checkbox_count": found_count,
                        "product_name": product_name,
                        "product_text": (actions.text(current) or "")[:2000],
                    }
                    break

    if target is None:
        target = {"strategy": "unresolved", "product_name_match_count": product_count}

    evidence = {
        "expected_item_id": str(ITEM_ID),
        "expected_model_id": str(model_id),
        "checkbox_count": count,
        "candidate_trace": traces,
        "decision": target,
    }
    save_json(run_dir / "checkout_identity_decision.json", evidence)
    print(f"[PHASE4] Cart checkboxes: {count}")
    print(f"[PHASE4] Identity strategy: {target['strategy']}")
    if target["strategy"] == "product_name_fallback":
        print(f"[PHASE4] Product-name DOM matches: {target['product_name_match_count']}")
        print(f"[PHASE4] Fallback checkbox count: {target['fallback_checkbox_count']}")
    return target


def extract_checkout_target_records(records, model_id):
    matches = []
    for response in records:
        for record in response.get("price_promo_records", []):
            if str(record.get("model_id")) == str(model_id) or str(record.get("item_id")) == str(ITEM_ID):
                matches.append({"response_url": response["url"], **record})
    return matches


def main():
    global RUN_DIR, CURRENT_MODEL
    RUN_DIR = make_run_dir()
    CURRENT_MODEL = None
    manifest = {
        "started_at": utc_now(),
        "promotional_url": PROMOTIONAL_URL,
        "canonical_url": CANONICAL_URL,
        "cart_url": CART_URL,
        "item_id": ITEM_ID,
        "shop_id": SHOP_ID,
        "requested_variation": REQUESTED_VARIATION,
        "quantity": QUANTITY,
        "test_goal": "Compare promotional get_pc price/promotion state with cart and checkout state.",
        "production_code_modified": False,
        "settings_json_modified": False,
        "payment_selected": False,
        "place_order_clicked": False,
    }
    save_json(RUN_DIR / "summary.json", manifest)

    owner = object()
    connector = BrowserConnector()
    browser_session = None
    try:
        print("=" * 72)
        print("PHASE 4 — PROMOTIONAL PRICE-STATE → CHECKOUT INVESTIGATION")
        print("=" * 72)
        print(f"Promotional URL: {PROMOTIONAL_URL}")
        print(f"Requested SKU:   {REQUESTED_VARIATION}")
        print("Production code modified: NO")
        print("settings.json modified:   NO")
        print("Payment selected: NO")
        print("Place Order clicked: NO")
        print("=" * 72)

        connector.connect()
        browser_session = connector.open_session(owner, PROMOTIONAL_URL)

        promo_final_url, promo_records = capture_responses(browser_session, RUN_DIR, PROMOTIONAL_URL, "promotional")
        promo_get_pc = [r for r in promo_records if "/api/v4/pdp/get_pc" in r["url"].lower() and "json" in r]
        print(f"[PHASE4] Promotional final URL: {promo_final_url}")
        print(f"[PHASE4] Promotional get_pc responses: {len(promo_get_pc)}")

        if not promo_get_pc:
            canonical_final_url, canonical_records = capture_responses(browser_session, RUN_DIR, CANONICAL_URL, "canonical")
            print(f"[PHASE4] Canonical final URL: {canonical_final_url}")
            promo_records.extend(canonical_records)
            promo_get_pc = [r for r in canonical_records if "/api/v4/pdp/get_pc" in r["url"].lower() and "json" in r]

        parsed_entry = promo_get_pc[-1] if promo_get_pc else None
        if parsed_entry is None:
            raise RuntimeError("No parseable get_pc response was captured.")
        product = ShopeeAPIParser().parse(parsed_entry["json"])
        if product.item_id != ITEM_ID or product.shop_id != SHOP_ID:
            raise RuntimeError(f"Unexpected ProductInfo item/shop: {product.item_id}/{product.shop_id}")

        live_request = resolve_live_variation(product)
        matching = find_matching_variations(product, live_request)
        if len(matching) != 1:
            raise RuntimeError("Live SKU resolution was not unique.")
        variation = matching[0]
        CURRENT_MODEL = variation.model_id
        print(f"[PHASE4] Exact live SKU: {variation.name} | model={variation.model_id}")
        print(f"[PHASE4] Live options: {variation.options}")

        # Re-run the promotional extraction now that CURRENT_MODEL is known.
        promo_price_records = []
        for response in promo_records:
            promo_price_records.extend(extract_price_promo_records(response.get("json"), f"response[{response.get('index')}]"))
        save_json(RUN_DIR / "api" / "promotional_target_price_records.json", promo_price_records)

        request = PurchaseRequest(
            reference=ProductReference(shop_id=SHOP_ID, item_id=ITEM_ID, url=PROMOTIONAL_URL),
            options=dict(variation.options),
            quantity=QUANTITY,
        )
        session = PurchaseSession(request=request, product=product, variation=variation, browser_session=browser_session, browser_owner=owner)

        print()
        print("=" * 72)
        print("PRODUCTION CART PATH")
        print("=" * 72)
        CartPreparer().prepare(session)
        print("[PHASE4] Production Add To Cart: EXECUTED")

        cart_final_url, cart_records = capture_responses(browser_session, RUN_DIR, CART_URL, "cart")
        cart_price_records = []
        for response in cart_records:
            cart_price_records.extend(extract_price_promo_records(response.get("json"), f"response[{response.get('index')}]"))
        save_json(RUN_DIR / "api" / "cart_target_price_records.json", cart_price_records)

        exact_cart = []
        for response in cart_records:
            for record in response.get("identity_records", []):
                if str(record.get("item_id")) == str(ITEM_ID) and str(record.get("model_id")) == str(CURRENT_MODEL):
                    exact_cart.append({"response_url": response["url"], **record})
        print(f"[PHASE4] Cart exact item+model records: {len(exact_cart)}")

        decision = inspect_current_cart_identity(browser_session, RUN_DIR, CURRENT_MODEL, product.product_name)
        checkout_url, checkout_records, checkout_text = capture_checkout_only(browser_session, decision, RUN_DIR)
        checkout_target = extract_checkout_target_records(checkout_records, CURRENT_MODEL)
        save_json(RUN_DIR / "api" / "checkout_target_price_records.json", checkout_target)

        lower_text = checkout_text.lower()
        checkout_dom_evidence = {
            "contains_product_name": product.product_name.lower() in lower_text,
            "contains_requested_color": "silver" in lower_text,
            "contains_requested_storage": "256gb" in lower_text,
            "contains_quantity_1": "1" in lower_text,
            "body_excerpt": checkout_text[:12000],
        }
        save_json(RUN_DIR / "checkout_dom_evidence.json", checkout_dom_evidence)

        # Build a machine-readable comparison for the final report.
        all_checkout_prices = []
        for record in checkout_target:
            for key in PRICE_KEYS:
                if key in record:
                    all_checkout_prices.append({"source": record["response_url"], "field": key, "value": record[key]})
        comparison = {
            "target": {"item_id": ITEM_ID, "model_id": CURRENT_MODEL, "sku": variation.name},
            "promotional_get_pc_price_promo_records": promo_price_records,
            "cart_target_price_promo_records": cart_price_records,
            "checkout_target_price_promo_records": checkout_target,
            "checkout_numeric_price_fields": all_checkout_prices,
            "exact_cart_identity_verified": bool(exact_cart),
            "checkout_reached": "/checkout" in checkout_url,
            "checkout_dom_evidence": checkout_dom_evidence,
        }
        save_json(RUN_DIR / "promo_to_checkout_comparison.json", comparison)

        # Conservative conclusion: only call C proven if the same model is
        # observed at a promotional get_pc price and checkout shows a distinct
        # price state for that same model. Otherwise classify as inconclusive.
        c = {
            "status": "INCONCLUSIVE",
            "reason": "Evidence does not yet contain both a get_pc promotional price and a distinct checkout price for the same model.",
        }
        promo_model_prices = [r for r in promo_price_records if str(r.get("model_id")) == str(CURRENT_MODEL)]
        checkout_model_prices = [r for r in checkout_target if str(r.get("model_id")) == str(CURRENT_MODEL)]
        promo_values = {str(r.get(k)) for r in promo_model_prices for k in PRICE_KEYS if k in r and r.get(k) is not None}
        checkout_values = {str(r.get(k)) for r in checkout_model_prices for k in PRICE_KEYS if k in r and r.get(k) is not None}
        if promo_model_prices and checkout_model_prices and promo_values and checkout_values and promo_values.isdisjoint(checkout_values):
            c = {
                "status": "SUPPORTED",
                "reason": "The same model is represented in get_pc and checkout, but the observed price/promotion values differ between the two states.",
            }
        comparison["hypothesis_C"] = c
        save_json(RUN_DIR / "promo_to_checkout_comparison.json", comparison)

        print()
        print("=" * 72)
        print("PHASE 4 — PROMOTIONAL PRICE-STATE RESULT")
        print("=" * 72)
        print(f"Promotional get_pc:          {'PASS' if promo_get_pc else 'FAIL'}")
        print(f"Exact SKU resolved:          PASS | model {CURRENT_MODEL}")
        print(f"Production Add To Cart:      EXECUTED")
        print(f"Cart exact item+model:        {'PASS' if exact_cart else 'FAIL'}")
        print(f"Checkout reached:             {'PASS' if '/checkout' in checkout_url else 'FAIL'}")
        print(f"Checkout target API records:  {len(checkout_target)}")
        print(f"Hypothesis C:                 {c['status']}")
        print(f"Evidence directory:           {RUN_DIR}")
        print("Payment selected:             NO")
        print("Place Order clicked:          NO")
        print("=" * 72)

        manifest.update({
            "finished_at": utc_now(),
            "model_id": CURRENT_MODEL,
            "add_to_cart_executed": True,
            "checkout_executed": True,
            "checkout_url": checkout_url,
            "cart_exact_item_model": bool(exact_cart),
            "hypothesis_C": c,
            "evidence_directory": str(RUN_DIR),
        })
        save_json(RUN_DIR / "summary.json", manifest)
        return 0 if exact_cart and "/checkout" in checkout_url else 2

    except Exception as exc:
        manifest["finished_at"] = utc_now()
        manifest["error"] = repr(exc)
        save_json(RUN_DIR / "summary.json", manifest)
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
