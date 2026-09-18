"""
Opt-in integration test for the experimental Shopee direct-checkout URL.

This is deliberately separate from the application execution path. It does
not modify PurchasePipeline or DirectCheckoutInitializer and it never clicks
Place Order.

Run only when explicitly enabled:

    SHOPEE_LIVE_CHECKOUT_URL_TEST=1 python -m pytest -s \
        tests/test_live_direct_checkout_url.py

The test uses the existing persistent Chrome/CDP connection, so the normal
authenticated Shopee browser session must already be running on port 9222.
"""

import os

import pytest

from execution.browser.browser_action import BrowserActions
from execution.browser.browser_connector import BrowserConnector


LIVE_TEST_ENABLED = os.getenv("SHOPEE_LIVE_CHECKOUT_URL_TEST") == "1"


@pytest.mark.skipif(
    not LIVE_TEST_ENABLED,
    reason="Opt-in live Shopee checkout URL test is disabled.",
)
def test_live_direct_checkout_url_reaches_checkout():
    item_id = os.getenv("SHOPEE_TEST_ITEM_ID", "26342037051")
    model_id = os.getenv("SHOPEE_TEST_MODEL_ID", "139454633403")
    quantity = os.getenv("SHOPEE_TEST_QUANTITY", "1")
    product_url = os.getenv(
        "SHOPEE_TEST_PRODUCT_URL",
        f"https://shopee.ph/product/1275798143/{item_id}",
    )

    direct_url = (
        "https://shopee.ph/checkout"
        f"?buy_now=true&item_id={item_id}"
        f"&model_id={model_id}&quantity={quantity}"
    )

    connector = BrowserConnector()
    owner = object()
    session = None

    print()
    print("========== LIVE DIRECT CHECKOUT URL TEST ==========")
    print(f"Product URL: {product_url}")
    print(f"Item ID: {item_id}")
    print(f"Model ID: {model_id}")
    print(f"Quantity: {quantity}")
    print(f"Direct URL: {direct_url}")
    print("Safety gate: Place Order will NOT be clicked.")

    try:
        connector.connect()
        session = connector.open_session(owner, product_url)

        print("[LiveDirectURLTest] Navigating directly to checkout URL...")
        BrowserActions(session).goto(
            direct_url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        BrowserActions(session).wait_for_timeout(3000)

        final_url = session.page.url
        print(f"[LiveDirectURLTest] Final URL: {final_url}")

        assert "/checkout" in final_url, (
            "Shopee did not reach /checkout from the experimental direct URL. "
            f"Final URL: {final_url}"
        )

        print("[LiveDirectURLTest] SUCCESS: /checkout was reached.")
        print("[LiveDirectURLTest] Stopping at checkout; no Place Order action.")
    finally:
        if session is not None:
            try:
                connector.close_session(owner)
            except Exception as exc:
                print(f"[LiveDirectURLTest] Session cleanup warning: {exc}")
