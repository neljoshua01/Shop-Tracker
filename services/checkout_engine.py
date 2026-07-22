from services.variation_selector import VariationSelector

class CheckoutEngine:

    def __init__(self):
        self.variation_selector = VariationSelector()

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
    
    async def find_purchase_button(self, page):

        # Try normal Buy Now first
        buy_now = page.locator("button:has-text('Buy Now')")

        if await buy_now.count() > 0:
            return buy_now, "Buy Now"

        # Try Buy With Voucher
        buy_voucher = page.locator("button:has-text('Buy With Voucher')")

        if await buy_voucher.count() > 0:
            return buy_voucher, "Buy With Voucher"

        return None, None

    async def buy(self, product, page):

        print()
        print("============================================================")
        print("AUTO CHECKOUT")
        print("============================================================")

        print("Searching for purchase button...")

        buy_button, button_name = await self.find_purchase_button(page)

        if buy_button is None:
            print("❌ No purchase button found.")
            return

        await buy_button.wait_for(
            state="visible",
            timeout=5000
        )

        print(f"{button_name} button found.")

        # Select available variations FIRST
        await self.variation_selector.select_variations(page)

        # Re-locate Buy Now after Shopee updates the page
        buy_button, button_name = await self.find_purchase_button(page)

        await buy_button.scroll_into_view_if_needed()

        await page.wait_for_timeout(500)

        await buy_button.hover()

        await page.wait_for_timeout(500)

        await buy_button.click()

        print(f"{button_name} clicked.")

        print("Waiting for checkout page...")
        await page.wait_for_timeout(2000)

        print()
        print("Current URL:", page.url)
        print("Title:", await page.title())

        if "/cart" in page.url:
            print("Cart page reached.")

            checkout_button = page.locator("button:has-text('Check Out')")

            await checkout_button.wait_for(
                state="visible",
                timeout=5000
            )

            print("Checkout button found.")

            await checkout_button.click()

            print("Checkout clicked.")

            await page.wait_for_timeout(3000)

            print()
            print("Current URL:", page.url)
            print("Title:", await page.title())

        place_order = page.locator("button:has-text('Place Order')")

        if await place_order.count() > 0:
            print("Place Order detected.")
            print("Checkout page reached.")
            print("Ready to purchase.")
        else:
            print("Checkout page not reached.")