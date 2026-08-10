from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions


PRODUCT_URL = "https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321?xptdk=d3f1c8cb-7a25-4630-8899-5fcd76155d9b"


def main():

    print()
    print("========== TESTING BROWSER RELOAD ==========")

    browser = BrowserConnector()

    session = None

    try:

        print()
        print("========== OPENING PRODUCT PAGE ==========")

        session = browser.open_session(
            "test_browser_reload",
            PRODUCT_URL,
        )

        actions = BrowserActions(session)

        print()
        print("========== BEFORE RELOAD ==========")

        print(
            f"[TEST] URL: "
            f"{session.page.url}"
        )

        print()
        print("========== RELOADING PAGE ==========")

        actions.reload()

        print(
            "[TEST] Reload completed."
        )

        print()
        print("========== AFTER RELOAD ==========")

        print(
            f"[TEST] URL: "
            f"{session.page.url}"
        )

        print()
        print(
            "[TEST] SUCCESS: "
            "Browser reload works."
        )

    except Exception as e:

        print()
        print(
            f"[TEST] FAILED: {e}"
        )

    finally:

        browser.close_session(
            "test_browser_reload",
        )


if __name__ == "__main__":
    main()