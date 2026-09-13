"""Phase 4 — production Add-to-Cart SKU investigation.

TEST-ONLY. No production application code is modified by this test.

Purpose:
    Prove whether the EXISTING production CartPreparer path adds the exact
    requested SKU to Shopee's cart.

Safety boundary:
    - Add To Cart: YES (this is the behavior under investigation).
    - Cart navigation/read-only verification: YES.
    - Checkout: NO.
    - Place Order: NO.
    - Payment: NO.
    - settings.json: NOT READ OR MODIFIED BY THIS TEST.

The test deliberately imports and executes the production CartPreparer and
VariationSelector. It does not reimplement their selection or Add-to-Cart
logic. After the production path finishes, the test independently verifies
/api/v4/cart/get and compares item_id + model_id against the requested live
SKU. Recommendation responses are never allowed to prove cart identity.
"""

import json
import time
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


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_run_dir():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = Path("tests/output") / f"phase4_promo_{stamp}"
    (path / "api").mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def save_text(path, text):
    path.write_text(text, encoding="utf-8")


def capture_get_pc(browser_session, target_url, run_dir):
    """Load PDP and parse the same get_pc payload used by production."""
    runtime = AsyncRuntime.instance()
    page = browser_session.page
    captured = []

    async def _capture():
        def on_response(response):
            captured.append(response)

        page.on("response", on_response)
        try:
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await page.wait_for_timeout(
                OBSERVE_AFTER_NAVIGATION_SECONDS * 1000
            )

            records = []
            get_pc = []
            for response in captured:
                records.append(
                    {
                        "url": response.url,
                        "status": response.status,
                        "method": response.request.method,
                        "resource_type": response.request.resource_type,
                    }
                )
                if "/api/v4/pdp/get_pc" in response.url:
                    try:
                        get_pc.append(
                            {
                                "status": response.status,
                                "url": response.url,
                                "data": await response.json(),
                            }
                        )
                    except Exception as exc:
                        get_pc.append(
                            {
                                "status": response.status,
                                "url": response.url,
                                "json_error": repr(exc),
                            }
                        )
            return page.url, records, get_pc
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    final_url, records, get_pc = runtime.submit(_capture()).result(timeout=50)
    save_json(run_dir / "api" / "pdp_responses.json", records)

    parsed = []
    for index, response in enumerate(
        [x for x in get_pc if "data" in x],
        start=1,
    ):
        save_json(
            run_dir / "api" / f"get_pc_{index:02d}.json",
            response["data"],
        )
        parsed.append(
            {
                "status": response["status"],
                "url": response["url"],
                "product": ShopeeAPIParser().parse(response["data"]),
            }
        )

    return final_url, records, parsed


def resolve_live_request(product):
    """Map application-facing Storage to the live ProductInfo label."""
    keys = []
    for variation in product.available_variations:
        for key in variation.options:
            if key not in keys:
                keys.append(key)

    resolved = {}
    for requested_title, requested_value in REQUESTED_VARIATION.items():
        live_title = next(
            (
                key
                for key in keys
                if key.strip().lower() == requested_title.strip().lower()
            ),
            None,
        )

        if live_title is None:
            matches = []
            for key in keys:
                values = {
                    str(v.options.get(key, "")).strip().lower()
                    for v in product.available_variations
                    if key in v.options
                }
                if requested_value.strip().lower() in values:
                    matches.append(key)

            if len(matches) != 1:
                raise RuntimeError(
                    f"Could not uniquely resolve {requested_title} -> "
                    f"{requested_value}: {matches}"
                )
            live_title = matches[0]

        resolved[live_title] = requested_value
        print(
            "[PHASE4] Application request "
            f"{requested_title} -> {requested_value} resolves to "
            f"ProductInfo label {live_title} -> {requested_value}"
        )

    return resolved


def find_matching_variations(product, request):
    matches = []
    for variation in product.available_variations:
        matched = True
        for wanted_key, wanted_value in request.items():
            if not any(
                key.strip().lower() == wanted_key.strip().lower()
                and str(value).strip().lower()
                == wanted_value.strip().lower()
                for key, value in variation.options.items()
            ):
                matched = False
                break
        if matched:
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
            results.append(
                {
                    "path": path,
                    "item_id": item,
                    "model_id": model,
                    "shop_id": normalized.get(
                        "shop_id", normalized.get("shopid")
                    ),
                    "name": normalized.get("name")
                    or normalized.get("model_name")
                    or normalized.get("item_name"),
                    "price": normalized.get("price"),
                    "origin_cart_item_price": normalized.get(
                        "origin_cart_item_price"
                    ),
                    "promotion_id": normalized.get(
                        "promotion_id", normalized.get("promotionid")
                    ),
                }
            )

        for key, value in node.items():
            walk_identity(value, f"{path}.{key}", results)

    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk_identity(value, f"{path}[{index}]", results)

    return results


def collect_cart_get_payloads(browser_session):
    """Read cart/get after CartPreparer has completed."""
    runtime = AsyncRuntime.instance()
    page = browser_session.page
    captured = []

    async def _capture():
        def on_response(response):
            if "/api/v4/cart/get" in response.url:
                captured.append(response)

        page.on("response", on_response)
        try:
            await page.goto(
                CART_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await page.wait_for_timeout(OBSERVE_CART_SECONDS * 1000)

            payloads = []
            for response in captured:
                try:
                    payloads.append(
                        {
                            "url": response.url,
                            "status": response.status,
                            "data": await response.json(),
                        }
                    )
                except Exception as exc:
                    payloads.append(
                        {
                            "url": response.url,
                            "status": response.status,
                            "json_error": repr(exc),
                        }
                    )

            return page.url, payloads
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    return runtime.submit(_capture()).result(timeout=50)


def verify_cart(browser_session, item_id, model_id, run_dir):
    final_url, payloads = collect_cart_get_payloads(browser_session)

    identities = []
    for payload in payloads:
        if "data" not in payload:
            continue
        identities.extend(walk_identity(payload["data"]))

    identities = [
        identity
        for identity in identities
        if identity.get("item_id") is not None
        or identity.get("model_id") is not None
    ]

    exact_matches = [
        identity
        for identity in identities
        if str(identity.get("item_id")) == str(item_id)
        and str(identity.get("model_id")) == str(model_id)
    ]
    item_matches = [
        identity
        for identity in identities
        if str(identity.get("item_id")) == str(item_id)
    ]

    evidence = {
        "cart_final_url": final_url,
        "cart_get_response_count": len(payloads),
        "requested_item_id": int(item_id),
        "requested_model_id": int(model_id),
        "cart_get_identities": identities,
        "exact_item_model_matches": exact_matches,
        "item_matches": item_matches,
        "exact_cart_api_item_model_match": bool(exact_matches),
    }
    save_json(run_dir / "api" / "cart_identity_after_app_add.json", evidence)

    print()
    print("=" * 72)
    print("PHASE 4 — PRODUCTION ADD-TO-CART VERIFICATION")
    print("=" * 72)
    print(f"[PHASE4] Cart final URL: {final_url}")
    print(f"[PHASE4] /api/v4/cart/get responses: {len(payloads)}")
    print(f"[PHASE4] Expected item_id: {item_id}")
    print(f"[PHASE4] Expected model_id: {model_id}")
    print(
        "[PHASE4] Cart API exact item+model match: "
        f"{'YES' if exact_matches else 'NO'}"
    )
    print(f"[PHASE4] Cart API item matches found: {len(item_matches)}")
    for identity in item_matches[:10]:
        print(
            "[PHASE4]   actual model="
            f"{identity.get('model_id')} "
            f"name={identity.get('name')} "
            f"price={identity.get('price')}"
        )
    print("[PHASE4] Production Add To Cart path: EXECUTED")
    print("[PHASE4] Checkout clicked: NO")
    print("[PHASE4] Place Order clicked: NO")
    print("=" * 72)

    return evidence


def snapshot_page(browser_session, path):
    try:
        actions = BrowserActions(browser_session)
        body = actions.find_all("body")
        save_text(path, actions.text(body))
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
        "quantity": QUANTITY,
        "mode": "PRODUCTION ADD-TO-CART / NO CHECKOUT",
        "production_code_modified": False,
        "settings_json_modified": False,
        "add_to_cart_executed": False,
        "checkout_executed": False,
        "place_order_executed": False,
        "run_dir": str(run_dir),
    }
    save_json(run_dir / "summary.json", manifest)

    owner = object()
    connector = BrowserConnector()
    browser_session = None

    try:
        print("=" * 72)
        print("PHASE 4 — PRODUCTION ADD-TO-CART SKU INVESTIGATION")
        print("=" * 72)
        print(f"Promotional URL: {PROMOTIONAL_URL}")
        print(f"Canonical URL:   {CANONICAL_URL}")
        print(f"Requested SKU:   {REQUESTED_VARIATION}")
        print(f"Quantity:         {QUANTITY}")
        print("Mode: PRODUCTION ADD-TO-CART / NO CHECKOUT")
        print("Production code modified: NO")
        print("settings.json modified:   NO")
        print("=" * 72)

        connector.connect()
        browser_session = connector.open_session(owner, PROMOTIONAL_URL)

        promo_final_url, promo_records, promo_get_pc = capture_get_pc(
            browser_session,
            PROMOTIONAL_URL,
            run_dir,
        )
        print(f"[PHASE4] Promotional final URL: {promo_final_url}")
        print(
            f"[PHASE4] Promotional captured {len(promo_records)} "
            f"responses; get_pc={len(promo_get_pc)}"
        )

        canonical_final_url = None
        canonical_get_pc = []
        if not promo_get_pc:
            canonical_final_url, _, canonical_get_pc = capture_get_pc(
                browser_session,
                CANONICAL_URL,
                run_dir,
            )
            print(f"[PHASE4] Canonical final URL: {canonical_final_url}")
            print(
                f"[PHASE4] Canonical get_pc={len(canonical_get_pc)}"
            )

        parsed_entry = promo_get_pc[-1] if promo_get_pc else None
        if parsed_entry is None and canonical_get_pc:
            parsed_entry = canonical_get_pc[-1]

        if parsed_entry is None:
            raise RuntimeError(
                "No parseable get_pc response was produced for the product."
            )

        product = parsed_entry["product"]
        if product.item_id != ITEM_ID or product.shop_id != SHOP_ID:
            raise RuntimeError(
                "Unexpected ProductInfo item/shop: "
                f"{product.item_id}/{product.shop_id}"
            )

        print(
            f"[PHASE4] ProductInfo: {product.product_name} "
            f"item={product.item_id} shop={product.shop_id}"
        )

        live_request = resolve_live_request(product)
        matching = find_matching_variations(product, live_request)
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
        print(
            f"[PHASE4] Exact requested live SKU: {variation.name} "
            f"| model={variation.model_id}"
        )
        print(f"[PHASE4] Live ProductInfo options: {variation.options}")

        request = PurchaseRequest(
            reference=ProductReference(
                shop_id=SHOP_ID,
                item_id=ITEM_ID,
                url=PROMOTIONAL_URL,
            ),
            options=dict(variation.options),
            quantity=QUANTITY,
        )
        session = PurchaseSession(
            request=request,
            product=product,
            variation=variation,
            browser_session=browser_session,
            browser_owner=owner,
        )

        manifest.update(
            {
                "promotional_final_url": promo_final_url,
                "canonical_final_url": canonical_final_url,
                "product": {
                    "name": product.product_name,
                    "item_id": product.item_id,
                    "shop_id": product.shop_id,
                },
                "resolved_live_request": live_request,
                "variation": {
                    "model_id": variation.model_id,
                    "name": variation.name,
                    "options": variation.options,
                    "price": variation.price,
                    "price_before_discount": variation.price_before_discount,
                    "has_stock": variation.has_stock,
                },
                "production_path": {
                    "class": "purchase.execution.cart_preparer.CartPreparer",
                    "method": "prepare",
                    "variation_selector": "purchase.execution.variation_selector.VariationSelector",
                },
            }
        )
        save_json(run_dir / "summary.json", manifest)

        print()
        print("=" * 72)
        print("EXECUTING EXISTING PRODUCTION CART PATH")
        print("=" * 72)
        print("[PHASE4] Calling CartPreparer.prepare(session)")
        print("[PHASE4] This will select the requested SKU and click Add To Cart.")
        print("[PHASE4] Checkout/Place Order are NOT part of this test.")
        print("=" * 72)

        # IMPORTANT: This is the actual production execution path.
        # No Add-to-Cart behavior is reimplemented in this test.
        CartPreparer().prepare(session)
        manifest["add_to_cart_executed"] = True
        manifest["session_status_after_cart_prepare"] = str(session.status)

        cart_evidence = verify_cart(
            browser_session,
            ITEM_ID,
            variation.model_id,
            run_dir,
        )
        manifest["cart_verification"] = cart_evidence
        manifest["finished_at"] = utc_now()
        save_json(run_dir / "summary.json", manifest)
        snapshot_page(browser_session, run_dir / "final_page.txt")

        passed = cart_evidence["exact_cart_api_item_model_match"]
        print()
        print("=" * 72)
        print("PHASE 4 RESULT")
        print("=" * 72)
        print(f"Promotional get_pc:          {'PASS' if promo_get_pc else 'NOT OBSERVED'}")
        print(f"Exact SKU resolved:          PASS | model {variation.model_id}")
        print("Production CartPreparer:     EXECUTED")
        print(f"Production Add To Cart:      {'EXECUTED' if manifest['add_to_cart_executed'] else 'NOT EXECUTED'}")
        print(f"Cart API exact item+model:   {'PASS' if passed else 'FAIL'}")
        print(f"Evidence directory:          {run_dir}")
        print("Checkout clicked:            NO")
        print("Place Order clicked:         NO")
        print("=" * 72)

        return 0 if passed else 2

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
