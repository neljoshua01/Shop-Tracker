from execution.browser.browser_action import BrowserActions


class CheckoutExecutor:

    def execute(
        self,
        session,
    ):

        print(
            "[CheckoutExecutor] "
            "========== STARTING CHECKOUT =========="
        )

        browser_session = session.browser_session

        if browser_session is None:

            print(
                "[CheckoutExecutor] "
                "Browser session not available."
            )

            return False

        page = browser_session.page

        actions = BrowserActions(
            browser_session,
        )

        print(
            "[CheckoutExecutor] "
            f"Current URL: {page.url}"
        )

        #
        # We expect to start on the cart.
        #
        if "/cart" not in page.url:

            print(
                "[CheckoutExecutor] "
                "Not on cart page."
            )

            return False

        print(
            "[CheckoutExecutor] "
            "Cart page confirmed."
        )

        #
        # =====================================================
        # 1. Wait for cart UI
        # =====================================================
        #

        print(
            "[CheckoutExecutor] "
            "Waiting for cart UI..."
        )

        actions.wait_for_timeout(3000)

        #
        # =====================================================
        # 2. Find target product
        # =====================================================
        #

        print(
            "[CheckoutExecutor] "
            "Searching for target product..."
        )

        product_name = session.product.product_name

        product_locator = actions.find_all(
            f"text={product_name}"
        )

        product_count = actions.count(
            product_locator
        )

        print(
            "[CheckoutExecutor] "
            f"Product matches: {product_count}"
        )

        if product_count == 0:

            print(
                "[CheckoutExecutor] "
                f"Target product not found: {product_name}"
            )

            return False

        product = actions.first(
            product_locator
        )

        print(
            "[CheckoutExecutor] "
            f"Target product found: {product_name}"
        )

        #
        # =====================================================
        # 3. Find cart item container
        # =====================================================
        #
        # The product text itself is not the checkbox container.
        # We walk upward until we find a parent containing
        # a Shopee checkbox.
        #

        print(
            "[CheckoutExecutor] "
            "Finding cart item container..."
        )

        container = None

        current = product

        for level in range(1, 6):

            current = actions.parent(
                current
            )

            checkbox_locator = actions.find_all(
                "input.stardust-checkbox__input",
                parent=current,
            )

            checkbox_count = actions.count(
                checkbox_locator
            )

            print(
                "[CheckoutExecutor] "
                f"Parent level {level}: "
                f"{checkbox_count} checkbox(es)"
            )

            if checkbox_count > 0:

                container = current

                print(
                    "[CheckoutExecutor] "
                    "Cart item container found."
                )

                break

        if container is None:

            print(
                "[CheckoutExecutor] "
                "Could not find cart item container."
            )

            return False

        #
        # =====================================================
        # 4. Find checkbox
        # =====================================================
        #

        checkbox = actions.find_all(
            "input.stardust-checkbox__input",
            parent=container,
        )

        checkbox_count = actions.count(
            checkbox
        )

        print(
            "[CheckoutExecutor] "
            f"Checkbox count: {checkbox_count}"
        )

        if checkbox_count == 0:

            print(
                "[CheckoutExecutor] "
                "Target item checkbox not found."
            )

            return False

        checkbox = actions.first(
            checkbox
        )

        #
        # =====================================================
        # 5. Inspect selection state
        # =====================================================
        #

        aria_checked = actions.attribute(
            checkbox,
            "aria-checked",
        )

        print(
            "[CheckoutExecutor] "
            f"aria-checked before: {aria_checked}"
        )

        #
        # Already selected
        #
        if aria_checked == "true":

            print(
                "[CheckoutExecutor] "
                "Target item is already selected."
            )

        else:

            #
            # =================================================
            # 6. Find visible checkbox UI
            # =================================================
            #
            # IMPORTANT:
            #
            # Clicking the hidden input caused the previous
            # test to timeout.
            #
            # The working test clicked:
            #
            # .stardust-checkbox__box
            #
            # instead.
            #

            print(
                "[CheckoutExecutor] "
                "Finding visible checkbox UI..."
            )

            checkbox_ui = actions.find_all(
                ".stardust-checkbox__box",
                parent=actions.parent(
                    checkbox
                ),
            )

            checkbox_ui_count = actions.count(
                checkbox_ui
            )

            print(
                "[CheckoutExecutor] "
                f"Checkbox UI boxes found: "
                f"{checkbox_ui_count}"
            )

            if checkbox_ui_count == 0:

                print(
                    "[CheckoutExecutor] "
                    "Visible checkbox UI not found."
                )

                return False

            checkbox_ui = actions.first(
                checkbox_ui
            )

            #
            # =================================================
            # 7. Click visible checkbox UI
            # =================================================
            #

            print(
                "[CheckoutExecutor] "
                "Selecting target cart item..."
            )

            actions.click(
                checkbox_ui
            )

            print(
                "[CheckoutExecutor] "
                "Target checkbox clicked."
            )

            #
            # Give Shopee time to update aria-checked.
            #
            actions.wait_for_timeout(500)

        #
        # =====================================================
        # 8. Verify selection
        # =====================================================
        #

        aria_checked = actions.attribute(
            checkbox,
            "aria-checked",
        )

        print(
            "[CheckoutExecutor] "
            f"aria-checked after: {aria_checked}"
        )

        if aria_checked != "true":

            print(
                "[CheckoutExecutor] "
                "Target item was NOT selected."
            )

            return False

        print(
            "[CheckoutExecutor] "
            "Target item selected successfully."
        )

        #
        # =====================================================
        # 9. Find Check Out button
        # =====================================================
        #

        print(
            "[CheckoutExecutor] "
            "Finding Check Out button..."
        )

        checkout_buttons = actions.find_all(
            "button:has-text('Check Out')"
        )

        checkout_count = actions.count(
            checkout_buttons
        )

        print(
            "[CheckoutExecutor] "
            f"Check Out buttons found: {checkout_count}"
        )

        if checkout_count == 0:

            print(
                "[CheckoutExecutor] "
                "Check Out button not found."
            )

            return False

        checkout_button = actions.first(
            checkout_buttons
        )

        print(
            "[CheckoutExecutor] "
            "Check Out button found."
        )

        #
        # =====================================================
        # 10. Click Check Out
        # =====================================================
        #

        print(
            "[CheckoutExecutor] "
            "Clicking Check Out..."
        )

        actions.click(
            checkout_button
        )

        print(
            "[CheckoutExecutor] "
            "Check Out clicked."
        )

        #
        # Give Shopee time to navigate.
        #
        actions.wait_for_timeout(3000)

        print(
            "[CheckoutExecutor] "
            f"Current URL after checkout: {page.url}"
        )

        #
        # =====================================================
        # 11. Verify checkout page
        # =====================================================
        #

        if "/checkout" not in page.url:

            print(
                "[CheckoutExecutor] "
                "Checkout page was not reached."
            )

            return False

        print(
            "[CheckoutExecutor] "
            "Checkout page reached."
        )

        #
        # =====================================================
        # 12. Verify Place Order exists
        # =====================================================
        #
        # IMPORTANT:
        #
        # We ONLY detect Place Order here.
        #
        # We DO NOT click it.
        #
        # This keeps the executor safe during testing.
        #

        place_order_buttons = actions.find_all(
            "button:has-text('Place Order')"
        )

        place_order_count = actions.count(
            place_order_buttons
        )

        print(
            "[CheckoutExecutor] "
            f"Place Order buttons found: "
            f"{place_order_count}"
        )

        if place_order_count == 0:

            print(
                "[CheckoutExecutor] "
                "Place Order button not found."
            )

            return False

        print(
            "[CheckoutExecutor] "
            "Place Order button detected."
        )

        print(
            "[CheckoutExecutor] "
            "Checkout verification complete."
        )

        #
        # IMPORTANT:
        #
        # No Place Order click occurs here.
        #
        return True