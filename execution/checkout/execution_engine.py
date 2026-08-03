from services.variation_selector import VariationSelector
from execution.checkout.checkout_verifier import CheckoutVerifier
from core.config.config_service import ConfigService
from notifier.discord import DiscordNotifier

class CheckoutEngine:

    def __init__(self):
        self.variation_selector = VariationSelector()
        self.checkout_verifier = CheckoutVerifier()
        self.config_service = ConfigService()

        config = self.config_service.load()

        self.notifier = DiscordNotifier(
            config["discord_webhook"]
        )

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

            #
            # Verify checkout state
            #
            if not await self.checkout_verifier.verify_price(
                page,
                product
            ):
                return

            if not await self.checkout_verifier.disable_protection(page):
                return
            
            await self.checkout_verifier.handle_checkout_dialog(page)

            if not await self.checkout_verifier.select_payment(page):
                return
            
            order_summary = await self.checkout_verifier.collect_order_summary(page)
            order_summary["url"] = product.url
            order_summary["target_price"] = product.target_price
            
            if not await self.checkout_verifier.verify_ready(page):
                return
            
            if not await self.checkout_verifier.verify_place_order(page):
                return

            result = await self.execute_purchase(
                page,
                order_summary
            )

            print()
            print("========== PURCHASE RESULT ==========")
            print(f"Status : {result['status']}")
        else:
            print("Checkout page not reached.")

    async def execute_purchase(self, page, summary):

        print()
        print("========== ARMED MODE ==========")

        config = self.config_service.load()

        if not config["armed_mode"]:

            print("SAFE MODE")
            print("Sending Discord notification...")

            await self.notifier.send_dry_run(summary)

            print("Place Order skipped.")

            return {
                "status": "dry_run",
                "summary": summary
            }

        print("ARMED MODE ENABLED")
        print("Submitting order...")

        place_order = page.locator(
            "button:has-text('Place Order')"
        )

        await place_order.wait_for(
            state="visible",
            timeout=5000
        )

        await place_order.click()
        print("Place Order clicked.")

        print("Waiting for purchase result...")

        await page.wait_for_timeout(5000)

        success = await self.verify_purchase_result(page)

        return {
            "status": "submitted" if success else "failed",
            "summary": summary
        }

    async def verify_purchase_result(self, page):

        print()
        print("========== VERIFY PURCHASE RESULT ==========")

        print("Current URL:")
        print(page.url)

        print()

        print("Page Title:")
        print(await page.title())

        print()

        body = await page.locator("body").inner_text()

        print("Page Preview:")
        print(body[:1000])

        #
        # Temporary
        #
        return True