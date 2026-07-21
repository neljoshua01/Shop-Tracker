class CheckoutEngine:

    def should_checkout(self, product):

        #
        # Auto checkout disabled
        #
        if not product.auto_checkout:
            return False

        #
        # No target price
        #
        if product.target_price is None:
            return False

        #
        # Already purchased
        #
        if product.purchased:
            return False

        #
        # No current price yet
        #
        if not product.current_price:
            return False

        #
        # Convert current price
        #
        try:
            current = (
                str(product.current_price)
                .replace("₱", "")
                .replace(",", "")
                .strip()
            )

            current = float(current)

        except ValueError:
            return False

        #
        # Target reached
        #
        if current <= product.target_price:

            print("[CheckoutEngine] Target reached.")

            return True

        return False

    # =====================================================
    # DRY RUN
    # =====================================================

    async def buy(self, product, page):

        print()
        print("============================================================")
        print("AUTO CHECKOUT (STEP 1)")
        print("============================================================")

        print("Searching for Buy Now button...")

        buy_button = page.locator("button:has-text('Buy Now')")

        await buy_button.wait_for(
            state="visible",
            timeout=5000
        )

        print("Buy Now button found.")

        await buy_button.scroll_into_view_if_needed()

        await page.wait_for_timeout(500)

        await buy_button.hover()

        await page.wait_for_timeout(500)

        await buy_button.click()
        print(page.url)
        await page.wait_for_timeout(2000)

        print("Buy Now clicked.")

        print("Waiting for purchase flow...")

        await page.wait_for_timeout(3000)

        print("============================================================")
        print("STEP 1 COMPLETE")
        print("============================================================")