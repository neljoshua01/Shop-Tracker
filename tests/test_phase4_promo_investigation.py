"""Phase 4 — checkout cart-identity investigation.

TEST-ONLY. This file is the only file changed by this investigation.

Purpose:
    Reproduce the current CheckoutExecutor cart-row identity decision without
    changing production code, then observe what reaches Shopee checkout.

Safety boundary:
    - Production CartPreparer/Add To Cart: YES.
    - Cart identity inspection: YES.
    - Cart checkbox selection: YES, using the same identity decision logic.
    - Check Out navigation: YES, for observation only.
    - Payment selection: NO.
    - Place Order: NO.
    - settings.json: NOT READ OR MODIFIED.

The test deliberately does NOT import or execute CheckoutExecutor.execute().
That production method would continue into payment/protection/order
verification. Instead, this test-only investigator mirrors ONLY the current
cart identity-selection portion so we can see whether it finds item+model or
falls back to the first product-name match. It then clicks Check Out only to
inspect the resulting checkout page and network evidence.
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
OBSERVE_AFTER_NAVIGATION_SECONDS = 8
OBSERVE_CART_SECONDS = 8
OBSERVE_CHECKOUT_SECONDS = 8


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_run_dir():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = Path("tests/output") / f"phase4_checkout_identity_{stamp}"
    (path / "api").mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def save_text(path, text):
    path.write_text(text, encoding="utf-8")


def capture_get_pc(browser_session, target_url, run_dir):
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
                records.append({"url": response.url, "status": response.status, "method": response.request.method, "resource_type": response.request.resource_type})
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

    final_url, records, get_pc = runtime.submit(_capture()).result(timeout=50)
    save_json(run_dir / "api" / "pdp_responses.json", records)
    parsed = []
    for index, response in enumerate([x for x in get_pc if "data" in x], start=1):
        save_json(run_dir / "api" / f"get_pc_{index:02d}.json", response["data"])
        parsed.append({"status": response["status"], "url": response["url"], "product": ShopeeAPIParser().parse(response["data"])})
    return final_url, records, parsed


def resolve_live_request(product):
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
        print(f"[PHASE4] Application request {requested_title} -> {requested_value} resolves to ProductInfo label {live_title} -> {requested_value}")
    return resolved


def find_matching_variations(product, request):
    matches = []
    for variation in product.available_variations:
        if all(any(key.strip().lower() == wanted_key.strip().lower() and str(value).strip().lower() == wanted_value.strip().lower() for key, value in variation.options.items()) for wanted_key, wanted_value in request.items()):
            matches.append(variation)
    return matches


def walk_identity(node, path="root", results=None):
    if results is None:
        results = []
    if isinstance(node, dict):
        normalized = {str(k).lower(): v for k, v in node.items()}
        item = normalized.get("item_id", normalized.get("itemid"))
        model = normalized.get("model_id", normalized.get("modelid"))
        if item is not None or model is not None:
            results.append({"path": path, "item_id": item, "model_id": model, "shop_id": normalized.get("shop_id", normalized.get("shopid")), "name": normalized.get("name") or normalized.get("model_name") or normalized.get("item_name"), "price": normalized.get("price"), "origin_cart_item_price": normalized.get("origin_cart_item_price"), "promotion_id": normalized.get("promotion_id", normalized.get("promotionid"))})
        for key, value in node.items():
            walk_identity(value, f"{path}.{key}", results)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk_identity(value, f"{path}[{index}]", results)
    return results


def collect_cart_get(browser_session, run_dir):
    runtime = AsyncRuntime.instance()
    page = browser_session.page
    captured = []

    async def _capture():
        def on_response(response):
            if "/api/v4/cart/get" in response.url:
                captured.append(response)
        page.on("response", on_response)
        try:
            await page.goto(CART_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(OBSERVE_CART_SECONDS * 1000)
            payloads = []
            for response in captured:
                try:
                    payloads.append({"url": response.url, "status": response.status, "data": await response.json()})
                except Exception as exc:
                    payloads.append({"url": response.url, "status": response.status, "json_error": repr(exc)})
            return page.url, payloads
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    final_url, payloads = runtime.submit(_capture()).result(timeout=50)
    identities = []
    for payload in payloads:
        if "data" in payload:
            identities.extend(walk_identity(payload["data"]))
    evidence = {"cart_final_url": final_url, "cart_get_response_count": len(payloads), "identities": identities}
    save_json(run_dir / "api" / "cart_identity_after_app_add.json", evidence)
    return evidence


def inspect_checkbox_candidates(browser_session, item_id, model_id, product_name, run_dir):
    """Mirror ONLY CheckoutExecutor's current cart identity decision."""
    actions = BrowserActions(browser_session)
    checkboxes = actions.find_all("input.stardust-checkbox__input")
    count = actions.count(checkboxes)
    candidates = []
    target = None

    for index in range(count):
        checkbox = checkboxes.nth(index)
        parent_trace = []
        current = checkbox
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
            identity_text = " ".join(attrs.values())
            item_match = str(item_id) in identity_text or str(item_id) in text
            model_match = str(model_id) in identity_text or str(model_id) in text
            parent_trace.append({"level": level, "attributes": attrs, "text": text[:1200], "item_match": item_match, "model_match": model_match})
            if item_match:
                target = {"strategy": "stable_item_identity", "checkbox_index": index, "parent_level": level, "item_match": True, "model_match": model_match, "parent_trace": parent_trace}
                break
        candidates.append({"checkbox_index": index, "parent_trace": parent_trace})
        if target is not None:
            break

    product_count = 0
    if target is None:
        products = actions.find_all(f"text={product_name}")
        product_count = actions.count(products)
        if product_count > 0:
            current = actions.first(products)
            for level in range(1, 9):
                current = actions.parent(current)
                if current is None:
                    break
                checkbox_locator = actions.find_all("input.stardust-checkbox__input", parent=current)
                checkbox_count = actions.count(checkbox_locator)
                if checkbox_count > 0:
                    target = {"strategy": "product_name_fallback", "product_name_match_count": product_count, "fallback_parent_level": level, "fallback_checkbox_count": checkbox_count, "product_text": (actions.text(current) or "")[:2000], "product_name": product_name}
                    break

    if target is None:
        target = {"strategy": "unresolved", "product_name_match_count": product_count}

    evidence = {"expected_item_id": str(item_id), "expected_model_id": str(model_id), "product_name": product_name, "checkbox_count": count, "candidate_trace": candidates, "decision": target}
    save_json(run_dir / "checkout_identity_decision.json", evidence)

    print()
    print("=" * 72)
    print("CHECKOUT IDENTITY INVESTIGATION — CURRENT PRODUCTION LOGIC")
    print("=" * 72)
    print(f"[PHASE4] Cart checkboxes found: {count}")
    print(f"[PHASE4] Target item_id: {item_id}")
    print(f"[PHASE4] Target model_id: {model_id}")
    print(f"[PHASE4] Identity strategy selected: {target.get('strategy')}")
    if target.get("strategy") == "stable_item_identity":
        print(f"[PHASE4] Stable identity checkbox index: {target.get('checkbox_index')}")
        print(f"[PHASE4] Stable identity parent level: {target.get('parent_level')}")
        print(f"[PHASE4] Model identity exposed: {target.get('model_match')}")
    elif target.get("strategy") == "product_name_fallback":
        print(f"[PHASE4] Product-name matches: {target.get('product_name_match_count')}")
        print(f"[PHASE4] Fallback parent level: {target.get('fallback_parent_level')}")
        print(f"[PHASE4] Fallback checkbox count: {target.get('fallback_checkbox_count')}")
    print("=" * 72)
    return target


def execute_selected_checkout(browser_session, decision, run_dir):
    """Apply the investigated decision, then inspect checkout only."""
    if decision.get("strategy") == "unresolved":
        raise RuntimeError("Checkout identity could not be resolved; refusing navigation.")

    actions = BrowserActions(browser_session)
    checkboxes = actions.find_all("input.stardust-checkbox__input")
    if decision.get("strategy") == "stable_item_identity":
        checkbox = checkboxes.nth(decision["checkbox_index"])
    else:
        product_locator = actions.find_all(f"text={decision['product_name']}")
        if actions.count(product_locator) == 0:
            raise RuntimeError("Fallback product-name locator disappeared before checkout.")
        current = actions.first(product_locator)
        checkbox = None
        for _ in range(8):
            current = actions.parent(current)
            if current is None:
                break
            checkbox_locator = actions.find_all("input.stardust-checkbox__input", parent=current)
            if actions.count(checkbox_locator) > 0:
                checkbox = actions.first(checkbox_locator)
                break
        if checkbox is None:
            raise RuntimeError("Fallback checkbox disappeared before checkout.")

    before = actions.attribute(checkbox, "aria-checked")
    if before != "true":
        parent = actions.parent(checkbox)
        ui = actions.find_all(".stardust-checkbox__box", parent=parent)
        if actions.count(ui) == 0:
            raise RuntimeError("Visible checkbox UI not found.")
        actions.click(actions.first(ui))
        actions.wait_for_timeout(500)
    after = actions.attribute(checkbox, "aria-checked")
    print(f"[PHASE4] Investigated checkbox aria-checked: {before} -> {after}")
    if after != "true":
        raise RuntimeError("Investigated cart row could not be selected.")

    checkout_buttons = actions.find_all("button:has-text('Check Out')")
    if actions.count(checkout_buttons) == 0:
        raise RuntimeError("Check Out button not found.")

    network = []
    page = browser_session.page
    runtime = AsyncRuntime.instance()

    async def _navigate_and_capture():
        def on_response(response):
            url = response.url
            low = url.lower()
            if "/checkout" in low or ("/api/v4/" in low and any(token in low for token in ("checkout", "order", "cart"))):
                network.append({"url": url, "status": response.status, "method": response.request.method})
        page.on("response", on_response)
        try:
            # BrowserActions.click() waits for Playwright's navigation/action
            # completion. Shopee can keep that navigation pending long enough
            # to trip the generic 10-second BrowserActions timeout. For this
            # TEST ONLY investigation, dispatch the already-selected Check Out
            # button in the page and then observe navigation explicitly.
            checkout_button = actions.first(checkout_buttons)
            await checkout_button.evaluate("el => el.click()")
            await page.wait_for_timeout(OBSERVE_CHECKOUT_SECONDS * 1000)
            return page.url
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    checkout_url = runtime.submit(_navigate_and_capture()).result(timeout=50)
    save_json(run_dir / "api" / "checkout_network.json", network)
    try:
        body_text = actions.text(actions.find_all("body"))
    except Exception as exc:
        body_text = f"<body snapshot failed: {exc!r}>"
    save_text(run_dir / "checkout_page.txt", body_text)

    result = {"checkout_url": checkout_url, "checkout_reached": "/checkout" in checkout_url, "network": network, "payment_selected": False, "place_order_clicked": False}
    save_json(run_dir / "checkout_observation.json", result)
    print()
    print("=" * 72)
    print("CHECKOUT PAGE OBSERVATION")
    print("=" * 72)
    print(f"[PHASE4] Current URL after checkout: {checkout_url}")
    print(f"[PHASE4] Checkout page reached: {result['checkout_reached']}")
    print(f"[PHASE4] Checkout-related responses captured: {len(network)}")
    print(f"[PHASE4] Saved checkout page: {run_dir / 'checkout_page.txt'}")
    print("[PHASE4] Payment selected: NO")
    print("[PHASE4] Place Order clicked: NO")
    print("=" * 72)
    return result


def snapshot_page(browser_session, path):
    try:
        actions = BrowserActions(browser_session)
        save_text(path, actions.text(actions.find_all("body")))
    except Exception as exc:
        save_text(path, f"snapshot failed: {exc!r}")


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
        "quantity": QUANTITY,
        "mode": "PRODUCTION ADD-TO-CART + TEST-ONLY CHECKOUT IDENTITY INVESTIGATION",
        "production_code_modified": False,
        "settings_json_modified": False,
        "add_to_cart_executed": False,
        "checkout_executed": False,
        "payment_selected": False,
        "place_order_executed": False,
        "run_dir": str(run_dir),
    }
    save_json(run_dir / "summary.json", manifest)

    owner = object()
    connector = BrowserConnector()
    browser_session = None
    try:
        print("=" * 72)
        print("PHASE 4 — CHECKOUT CART-IDENTITY INVESTIGATION")
        print("=" * 72)
        print(f"Promotional URL: {PROMOTIONAL_URL}")
        print(f"Canonical URL:   {CANONICAL_URL}")
        print(f"Requested SKU:   {REQUESTED_VARIATION}")
        print("Production code modified: NO")
        print("settings.json modified:   NO")
        print("Payment: NO")
        print("Place Order: NO")
        print("=" * 72)

        connector.connect()
        browser_session = connector.open_session(owner, PROMOTIONAL_URL)
        promo_final_url, _, promo_get_pc = capture_get_pc(browser_session, PROMOTIONAL_URL, run_dir)
        print(f"[PHASE4] Promotional final URL: {promo_final_url}")
        print(f"[PHASE4] Promotional get_pc responses: {len(promo_get_pc)}")

        canonical_get_pc = []
        canonical_final_url = None
        if not promo_get_pc:
            canonical_final_url, _, canonical_get_pc = capture_get_pc(browser_session, CANONICAL_URL, run_dir)
            print(f"[PHASE4] Canonical final URL: {canonical_final_url}")
            print(f"[PHASE4] Canonical get_pc responses: {len(canonical_get_pc)}")

        parsed_entry = promo_get_pc[-1] if promo_get_pc else (canonical_get_pc[-1] if canonical_get_pc else None)
        if parsed_entry is None:
            raise RuntimeError("No parseable get_pc response was produced.")
        product = parsed_entry["product"]
        if product.item_id != ITEM_ID or product.shop_id != SHOP_ID:
            raise RuntimeError(f"Unexpected ProductInfo item/shop: {product.item_id}/{product.shop_id}")

        live_request = resolve_live_request(product)
        matching = find_matching_variations(product, live_request)
        if len(matching) != 1:
            raise RuntimeError("Live SKU resolution was not unique: " + json.dumps([{"model_id": v.model_id, "name": v.name, "options": v.options} for v in matching], ensure_ascii=False))
        variation = matching[0]
        print(f"[PHASE4] Exact requested live SKU: {variation.name} | model={variation.model_id}")
        print(f"[PHASE4] Live ProductInfo options: {variation.options}")

        request = PurchaseRequest(reference=ProductReference(shop_id=SHOP_ID, item_id=ITEM_ID, url=PROMOTIONAL_URL), options=dict(variation.options), quantity=QUANTITY)
        session = PurchaseSession(request=request, product=product, variation=variation, browser_session=browser_session, browser_owner=owner)

        print()
        print("=" * 72)
        print("EXECUTING EXISTING PRODUCTION CART PATH")
        print("=" * 72)
        print("[PHASE4] CartPreparer.prepare(session)")
        print("[PHASE4] Production Add To Cart: YES")
        print("[PHASE4] CheckoutExecutor.execute(): NO")
        print("=" * 72)
        CartPreparer().prepare(session)
        manifest["add_to_cart_executed"] = True
        save_json(run_dir / "summary.json", manifest)

        cart_evidence = collect_cart_get(browser_session, run_dir)
        exact = [x for x in cart_evidence["identities"] if str(x.get("item_id")) == str(ITEM_ID) and str(x.get("model_id")) == str(variation.model_id)]
        print(f"[PHASE4] /api/v4/cart/get exact item+model matches: {len(exact)}")

        decision = inspect_checkbox_candidates(browser_session, ITEM_ID, variation.model_id, product.product_name, run_dir)
        checkout_result = execute_selected_checkout(browser_session, decision, run_dir)
        manifest.update({"checkout_executed": True, "checkout_result": checkout_result, "identity_decision": decision, "cart_exact_item_model_match": bool(exact), "finished_at": utc_now()})
        save_json(run_dir / "summary.json", manifest)
        snapshot_page(browser_session, run_dir / "final_page.txt")

        print()
        print("=" * 72)
        print("PHASE 4 CHECKOUT IDENTITY RESULT")
        print("=" * 72)
        print(f"Promotional get_pc:          {'PASS' if promo_get_pc else 'NOT OBSERVED'}")
        print(f"Exact SKU resolved:          PASS | model {variation.model_id}")
        print(f"Production Add To Cart:      {'EXECUTED' if manifest['add_to_cart_executed'] else 'NO'}")
        print(f"Cart API exact item+model:   {'PASS' if exact else 'FAIL'}")
        print(f"Identity strategy:            {decision.get('strategy')}")
        print(f"Checkout reached:            {'PASS' if checkout_result['checkout_reached'] else 'FAIL'}")
        print("Payment selected:             NO")
        print("Place Order clicked:          NO")
        print(f"Evidence directory:           {run_dir}")
        print("=" * 72)
        return 0 if exact and checkout_result["checkout_reached"] else 2

    except Exception as exc:
        manifest["finished_at"] = utc_now()
        manifest["error"] = repr(exc)
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
