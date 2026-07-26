import re

class CheckoutVerifier:

    async def verify_price(self, page, product):

        print()
        print("========== VERIFY PRICE ==========")

        body = await page.locator("body").inner_text()

        #
        # Try to locate the final payment amount.
        #
        import re

        matches = re.findall(r"₱[\d,]+(?:\.\d{2})?", body)

        if not matches:
            print("❌ Could not locate any prices on checkout page.")
            return False

        #
        # Usually the last peso amount is the final payment.
        #
        final_price = matches[-1]

        print(f"Checkout Total: {final_price}")

        checkout_total = float(
            final_price.replace("₱", "").replace(",", "")
        )

        print(f"Target Price : {product.target_price}")

        if checkout_total > product.target_price:
            print("❌ Checkout total exceeds target.")
            return False

        print("✓ Checkout total is within target.")

        return True

    async def disable_protection(self, page):

        print()
        print("========== DISABLE EXTENDED PROTECTION ==========")

        body = await page.locator("body").inner_text()

        if "Extended Protection" not in body and "Merchandise Protection" not in body:
            print("No protection found.")
            return True

        print("Protection detected.")

        checkbox = page.locator(
            "input[type='checkbox'][checked]"
        ).first

        if await checkbox.count() == 0:
            print("Protection already disabled.")
            return True

        await checkbox.scroll_into_view_if_needed()

        await checkbox.click(force=True)

        print("✓ Protection disabled.")

        await page.wait_for_timeout(1000)

        return True
    
    async def handle_shipping_popup(self, page):

        print()
        print("========== SHIPPING POPUP ==========")

        try:

            confirm = page.get_by_role(
                "button",
                name="Confirm"
            )

            if await confirm.count() == 0:
                print("No shipping confirmation required.")
                return True

            await confirm.first.click()

            print("✓ Shipping confirmed.")

            await page.wait_for_timeout(800)

        except Exception:

            print("No shipping popup.")

        return True

    async def verify_ready(self, page):

        print()
        print("========== FINAL CHECK ==========")

        return True
    
    async def verify_place_order(self, page):

        print()
        print("========== PLACE ORDER ==========")

        place_order = page.get_by_role(
            "button",
            name="Place Order"
        )

        if await place_order.count() == 0:
            print("❌ Place Order button not found.")
            return False

        if not await place_order.first.is_visible():
            print("❌ Place Order button is not visible.")
            return False

        print("✓ Place Order button found.")

        return True
    
    async def select_payment(self, page):

        print()
        print("========== SELECT PAYMENT ==========")

        #
        # Open payment selector
        #
        change = page.locator("text=CHANGE").last

        await change.click()

        await page.wait_for_timeout(1000)

        print("Payment options opened.")

        #
        # Payment priority
        #
        preferred_methods = [
            "ShopeePay Balance",
            "Cash on Delivery",
        ]

        #
        # Search available buttons
        #
        buttons = page.locator("button, div[role='button']")

        count = await buttons.count()

        selected = False

        for payment in preferred_methods:

            print(f"Trying payment: {payment}")

            for i in range(count):

                btn = buttons.nth(i)

                try:
                    text = (await btn.inner_text()).strip()
                except:
                    continue

                if payment not in text:
                    continue

                print(f"Found: {text}")

                #
                # Try selecting it
                #
                try:

                    await btn.scroll_into_view_if_needed()

                    await page.wait_for_timeout(300)

                    await btn.click(timeout=1500)

                    print(f"✓ Selected {payment}")

                    selected = True

                    break

                except Exception:

                    print(f"Cannot use {payment}")

            if selected:
                break

        if not selected:

            raise Exception(
                "No supported payment method available."
            )

        #
        # Give Shopee time to update
        #
        await page.wait_for_timeout(1000)

        return True

    async def collect_order_summary(self, page):

        print()
        print("========== ORDER SUMMARY ==========")

        body = await page.locator("body").inner_text()

        summary = {
            "product": None,
            "seller": None,
            "variation": None,
            "quantity": None,
            "subtotal": None,
            "shipping": None,
            "total": None,
            "payment": None,
        }

        #
        # --------------------------
        # Seller
        # --------------------------
        #
        seller_match = re.search(
            r"Item Subtotal\s+(.+?)\s+\|",
            body,
            re.S
        )

        if seller_match:
            summary["seller"] = seller_match.group(1).strip()

        #
        # --------------------------
        # Product
        # --------------------------
        #
        product_match = re.search(
            r"chat now\s+([^\n]+)",
            body
        )

        if product_match:
            summary["product"] = product_match.group(1).strip()
        #
        # --------------------------
        # Variation
        # --------------------------
        #
        variation_match = re.search(
            r"Variation:\s*(.+)",
            body
        )

        if variation_match:
            summary["variation"] = variation_match.group(1).strip()

        #
        # --------------------------
        # Quantity
        # --------------------------
        #
        quantity_match = re.search(
            r"Variation:.*?\n.*?\n.*?\n(\d+)\n",
            body,
            re.S
        )

        if quantity_match:
            summary["quantity"] = int(
                quantity_match.group(1)
            )

        #
        # --------------------------
        # Merchandise Subtotal
        # --------------------------
        #
        subtotal_match = re.search(
            r"Merchandise Subtotal\s*₱([\d,]+)",
            body
        )

        if subtotal_match:
            summary["subtotal"] = float(
                subtotal_match.group(1).replace(",", "")
            )

        #
        # --------------------------
        # Shipping
        # --------------------------
        #
        shipping_match = re.search(
            r"Shipping Subtotal\s*₱([\d,]+)",
            body
        )

        if shipping_match:
            summary["shipping"] = float(
                shipping_match.group(1).replace(",", "")
            )

        #
        # --------------------------
        # Total
        # --------------------------
        #
        total_match = re.search(
            r"Total Payment:\s*₱([\d,]+)",
            body
        )

        if total_match:
            summary["total"] = float(
                total_match.group(1).replace(",", "")
            )

        #
        # --------------------------
        # Payment
        # --------------------------
        #
        if "Cash on Delivery" in body:
            summary["payment"] = "Cash on Delivery"

        elif "ShopeePay Balance" in body:
            summary["payment"] = "ShopeePay"

        #
        # --------------------------
        # Print nicely
        # --------------------------
        #
        for key, value in summary.items():
            print(f"{key:12}: {value}")

        return summary