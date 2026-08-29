"""
Standalone validation for Shopee's item-scoped cart deep link.

This test intentionally does NOT modify the production checkout flow.
It opens the existing browser session on:

    /cart?itemKeys={item_id}.{model_id}.&shopId={shop_id}

and reports whether Shopee scopes the cart to the requested item and
whether the item is already selected. It does not click Checkout or
Place Order.

Before running, add the target product/SKU to the Shopee cart manually
and provide the identifiers through environment variables:

    SHOPEE_ITEM_ID=...
    SHOPEE_MODEL_ID=...
    SHOPEE_SHOP_ID=...

Example:

    SHOPEE_ITEM_ID=40662090854 \\
    SHOPEE_MODEL_ID=440619239463 \\
    SHOPEE_SHOP_ID=854953902 \\
    python3 tests/test_cart_deep_link.py
"""

import os
import sys
import time
from urllib.parse import parse_qs, urlparse

# Allow the test to be run directly from the repository root.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from execution.browser.browser_action import BrowserActions
from execution.browser.browser_connector import BrowserConnector


CART_URL = "https://shopee.ph/cart"


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def build_cart_deep_link(item_id, model_id, shop_id):
    return (
        f"{CART_URL}?itemKeys={item_id}.{model_id}."
        f"&shopId={shop_id}"
    )


def inspect_cart(session, item_id, model_id):
    actions = BrowserActions(session)
    page = session.page

    print(f"[CartDeepLinkTest] Final URL: {page.url}")

    parsed = urlparse(page.url)
    params = parse_qs(parsed.query)
    item_keys = params.get("itemKeys", [""])[0]
    shop_id = params.get("shopId", [""])[0]

    expected_item_keys = f"{item_id}.{model_id}."
    print(f"[CartDeepLinkTest] itemKeys: {item_keys}")
    print(f"[CartDeepLinkTest] shopId: {shop_id}")

    if item_keys != expected_item_keys:
        print("[CartDeepLinkTest] WARNING: Shopee rewrote or removed itemKeys.")
    else:
        print("[CartDeepLinkTest] PASS: itemKeys preserved in URL.")

    # Give the scoped cart a short render window, but do not use the
    # production flow's fixed 3-second cart wait as the measurement.
    start = time.perf_counter()
    actions.wait_for_selector("input.stardust-checkbox__input", timeout=10000)
    render_seconds = time.perf_counter() - start
    print(f"[CartDeepLinkTest] First cart checkbox available after: {render_seconds:.3f}s")

    checkbox_inputs = actions.find_all("input.stardust-checkbox__input")
    checkbox_count = actions.count(checkbox_inputs)
    print(f"[CartDeepLinkTest] Cart checkboxes found: {checkbox_count}")

    # Look for the requested item/model in the rendered cart without
    # modifying selection state.
    identity_matches = 0
    model_matches = 0
    for index in range(checkbox_count):
        checkbox = checkbox_inputs.nth(index)
        current = checkbox
        for _ in range(8):
            current = actions.parent(current)
            if current is None:
                break

            values = []
            for attribute_name in (
                "data-item-id",
                "data-model-id",
                "data-product-id",
                "data-sku-id",
                "data-id",
            ):
                value = actions.attribute(current, attribute_name)
                if value:
                    values.append(str(value))

            text = actions.text(current) or ""
            identity = " ".join(values)

            if item_id in identity or item_id in text:
                identity_matches += 1
                if model_id in identity or model_id in text:
                    model_matches += 1
                break

    print(f"[CartDeepLinkTest] Requested item matches: {identity_matches}")
    print(f"[CartDeepLinkTest] Requested item+model matches: {model_matches}")

    # Report selection state for the matching checkbox when possible.
    selected = None
    for index in range(checkbox_count):
        checkbox = checkbox_inputs.nth(index)
        current = checkbox
        matched = False
        for _ in range(8):
            current = actions.parent(current)
            if current is None:
                break
            values = []
            for attribute_name in (
                "data-item-id",
                "data-model-id",
                "data-product-id",
                "data-sku-id",
                "data-id",
            ):
                value = actions.attribute(current, attribute_name)
                if value:
                    values.append(str(value))
            text = actions.text(current) or ""
            identity = " ".join(values)
            if item_id in identity or item_id in text:
                matched = True
                break
        if matched:
            selected = actions.attribute(checkbox, "aria-checked")
            break

    if selected is None:
        print("[CartDeepLinkTest] Selection state: target checkbox not resolved.")
    else:
        print(f"[CartDeepLinkTest] Target aria-checked: {selected}")
        if selected == "true":
            print("[CartDeepLinkTest] Target item is PRE-SELECTED.")
        else:
            print("[CartDeepLinkTest] Target item is NOT pre-selected.")

    return {
        "url_scoped": item_keys == expected_item_keys,
        "item_matches": identity_matches,
        "model_matches": model_matches,
        "selected": selected,
        "render_seconds": render_seconds,
        "checkbox_count": checkbox_count,
    }


def main():
    item_id = required_env("SHOPEE_ITEM_ID")
    model_id = required_env("SHOPEE_MODEL_ID")
    shop_id = required_env("SHOPEE_SHOP_ID")

    cart_url = build_cart_deep_link(item_id, model_id, shop_id)
    print("[CartDeepLinkTest] ========== STANDALONE CART DEEP-LINK TEST ==========")
    print(f"[CartDeepLinkTest] Target item: {item_id}")
    print(f"[CartDeepLinkTest] Target model: {model_id}")
    print(f"[CartDeepLinkTest] Target shop: {shop_id}")
    print(f"[CartDeepLinkTest] Deep-link: {cart_url}")
    print("[CartDeepLinkTest] No Checkout or Place Order action will be performed.")

    connector = BrowserConnector()
    owner = object()
    session = None

    try:
        connector.connect()
        session = connector.open_session(owner, cart_url)
        result = inspect_cart(session, item_id, model_id)

        print("\n[CartDeepLinkTest] ========== RESULT ==========")
        print(f"[CartDeepLinkTest] URL scoped: {result['url_scoped']}")
        print(f"[CartDeepLinkTest] Item matches: {result['item_matches']}")
        print(f"[CartDeepLinkTest] Item+model matches: {result['model_matches']}")
        print(f"[CartDeepLinkTest] Pre-selected: {result['selected'] == 'true'}")
        print(f"[CartDeepLinkTest] First checkbox render: {result['render_seconds']:.3f}s")
        print(f"[CartDeepLinkTest] Checkbox count: {result['checkbox_count']}")

    finally:
        if session is not None:
            connector.close_session(owner)
        connector.disconnect()


if __name__ == "__main__":
    main()
