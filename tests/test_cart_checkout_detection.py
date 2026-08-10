"""
Inspects the Shopee cart page to determine
how the Checkout button is represented.
"""

from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions


CART_URL = "https://shopee.ph/cart"


def main():

    print()
    print("========== CART CHECKOUT DETECTION TEST ==========")

    browser = BrowserConnector()

    owner = "test_cart_checkout_detection"

    try:

        print()
        print("========== OPENING CART ==========")

        session = browser.open_session(
            owner,
            CART_URL,
        )

        actions = BrowserActions(session)

        print()
        print("========== CART OPENED ==========")
        print(f"[TEST] URL: {session.url}")

        #
        # Give Shopee time to finish rendering.
        #
        print()
        print("========== WAITING FOR CART UI ==========")

        actions.wait_for_timeout(3000)

        #
        # Inspect buttons.
        #
        print()
        print("========== BUTTON INSPECTION ==========")

        buttons = actions.find_all("button")

        count = actions.count(buttons)

        print(f"[TEST] Button count: {count}")

        for i in range(count):

            button = buttons.nth(i)

            try:
                text = actions.text(button)
            except Exception:
                text = ""

            try:
                aria = actions.attribute(
                    button,
                    "aria-label",
                )
            except Exception:
                aria = None

            try:
                title = actions.attribute(
                    button,
                    "title",
                )
            except Exception:
                title = None

            try:
                class_name = actions.attribute(
                    button,
                    "class",
                )
            except Exception:
                class_name = None

            print()
            print(f"--- BUTTON {i} ---")
            print(f"Text: {text!r}")
            print(f"ARIA: {aria!r}")
            print(f"Title: {title!r}")
            print(f"Class: {class_name!r}")

        #
        # Search for checkout text.
        #
        print()
        print("========== CHECKOUT TEXT SEARCH ==========")

        body = actions.find_all("body")

        body_text = actions.text(
            actions.first(body)
        )

        checkout_keywords = [
            "Check Out",
            "Checkout",
            "check out",
            "checkout",
        ]

        for keyword in checkout_keywords:

            if keyword in body_text:

                print(
                    f"[FOUND] Checkout text: {keyword!r}"
                )

            else:

                print(
                    f"[NOT FOUND] Checkout text: {keyword!r}"
                )

        #
        # Test the selector used by the old implementation.
        #
        print()
        print("========== OLD SELECTOR TEST ==========")

        old_selector = "button:has-text('Check Out')"

        old_checkout = actions.find_all(
            old_selector
        )

        old_count = actions.count(
            old_checkout
        )

        print(
            f"[TEST] Selector: {old_selector}"
        )

        print(
            f"[TEST] Matches: {old_count}"
        )

        #
        # Search all elements containing exact
        # checkout text.
        #
        print()
        print("========== TEXT LOCATOR TEST ==========")

        text_locator = actions.find_all(
            "text=Check Out"
        )

        text_count = actions.count(
            text_locator
        )

        print(
            f"[TEST] text=Check Out matches: "
            f"{text_count}"
        )

        for i in range(text_count):

            element = text_locator.nth(i)

            try:

                tag = actions._submit(
                    element.evaluate(
                        "(el) => el.tagName"
                    ),
                    timeout=10,
                )

            except Exception:

                tag = "UNKNOWN"

            try:

                classes = actions.attribute(
                    element,
                    "class",
                )

            except Exception:

                classes = None

            print()
            print(
                f"--- CHECKOUT ELEMENT {i} ---"
            )

            print(
                f"Tag: {tag}"
            )

            print(
                f"Class: {classes!r}"
            )

        print()
        print("========== INSPECTION COMPLETE ==========")

    finally:

        browser.close_session(owner)


if __name__ == "__main__":
    main()