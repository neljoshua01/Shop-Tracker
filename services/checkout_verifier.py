import re


class CheckoutVerifier:

    def __init__(self):

        # Set by select_payment() once a method is actually confirmed —
        # collect_order_summary() reads this directly instead of
        # re-guessing from page text.
        self.selected_payment = None

    async def verify_price(self, page, product):

        print()
        print("========== VERIFY PRICE ==========")

        body = await page.locator("body").inner_text()

        #
        # Try to locate the final payment amount.
        #
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

    async def _find_protection_row(self, learn_more_link):
        """
        Walk up from a 'Learn more' link until reaching an ancestor
        that BOTH mentions 'Protection' in its text AND contains a
        checkbox as a descendant. Requiring both signals matters here:
        the label/description text and the actual checkbox can sit as
        SIBLINGS under a shared parent rather than one containing the
        other. Stopping at the first ancestor that merely mentions
        "protection" (text-only) can land one level too low, before
        the checkbox's sibling branch has actually joined the scope —
        which is exactly what was happening. Same two-signal,
        first-match-wins technique already proven for purchase-panel
        detection in variation_selector.py (Quantity + Buy Now).
        """
 
        current = learn_more_link
 
        for level in range(8):
 
            candidate = current.locator("xpath=..")
 
            row_text = await candidate.inner_text()
 
            has_protection_text = "protection" in row_text.lower()
            has_checkbox = await candidate.locator("input[type='checkbox']").count() > 0
 
            if has_protection_text and has_checkbox:
                return candidate
 
            current = candidate
 
        return None
 
    async def disable_protection(self, page):
 
        print()
        print("========== DISABLE EXTENDED PROTECTION ==========")
 
        #
        # Generalized AND scoped. This is the piece that was missing:
        # a page-wide "grab the first checked checkbox anywhere" search
        # doesn't just risk matching the wrong label — it risks
        # clicking a completely unrelated checkbox (e.g. something
        # shipping-related) if that happens to sit earlier in the DOM.
        # That's very likely what was opening the shipping popup on
        # every protection click. Anchoring on "Learn more" and walking
        # up to the row that mentions "Protection" keeps the search
        # confined to just that one widget, every time.
        #
        learn_more_links = page.locator("text=Learn more")
 
        link_count = await learn_more_links.count()
 
        if link_count == 0:
            print("No protection option found.")
            return True
 
        found_any = False
 
        for i in range(link_count):
 
            row = await self._find_protection_row(learn_more_links.nth(i))
 
            if row is None:
                continue
 
            found_any = True
 
            row_text = (await row.inner_text()).strip()
 
            label = next(
                (line.strip() for line in row_text.splitlines() if "protection" in line.lower()),
                "Protection option"
            )
 
            print(f"{label} found.")
 
            checkbox = row.locator("input[type='checkbox']").first
 
            if await checkbox.count() == 0:
                print(f"No checkbox found for {label} — may be a custom (non-<input>) toggle.")
                continue
 
            if not await checkbox.is_checked():
                print(f"{label} already unchecked — no action needed.")
                continue
 
            await checkbox.scroll_into_view_if_needed()
 
            await checkbox.click(force=True)
 
            print(f"✓ {label} unchecked.")
 
            await page.wait_for_timeout(1000)
 
        if not found_any:
            print("No protection option found.")
 
        return True

    async def handle_checkout_dialog(self, page):

        print()
        print("========== CHECKOUT DIALOG ==========")

        confirm = page.get_by_role(
            "button",
            name="Confirm"
        )

        try:
            await confirm.first.wait_for(
                state="visible",
                timeout=2000
            )
        except Exception:
            print("No checkout dialog.")
            return False

        print("Checkout dialog detected.")

        await confirm.first.click()

        print("✓ Checkout dialog confirmed.")

        await confirm.first.wait_for(
            state="hidden",
            timeout=5000
        )

        print("✓ Dialog closed.")

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

        # Deliberately does not click. Whether this checkout goes
        # through is decided by the Safe/Armed gate upstream, not here.

        return True

    async def select_spaylater_plan(self, page):

        print()
        print("========== SPAYLATER PLAN ==========")

        plan = page.get_by_text(
            "Buy Now Pay Later",
            exact=False
        )

        try:

            await plan.first.wait_for(
                state="visible",
                timeout=5000
            )

        except Exception:

            print("❌ Buy Now Pay Later plan not found.")

            return False

        await plan.first.click()

        print("✓ Buy Now Pay Later selected")

        await page.wait_for_timeout(500)

        return True

    async def select_payment(self, page):

        self.selected_payment = None

        print()
        print("========== SELECT PAYMENT ==========")

        #
        # One last chance for the delayed protection dialog.
        # This doesn't hurt if no dialog exists.
        #
        await self.handle_checkout_dialog(page)

        #
        # If SPayLater is already active, don't change anything.
        #
        spay_selected = page.locator(
            "button:has-text('SPayLater')"
        )

        if await spay_selected.count() > 0:

            classes = await spay_selected.first.get_attribute("class") or ""

            aria = await spay_selected.first.get_attribute("aria-pressed")

            #
            # Shopee usually marks the selected payment by CSS.
            # You may adjust this after one inspector check.
            #
            if (
                "selected" in classes.lower()
                or "active" in classes.lower()
                or aria == "true"
            ):

                print("✓ SPayLater already selected.")

                self.selected_payment = "SPayLater"

                #
                # Still verify the plan.
                #
                if not await self.select_spaylater_plan(page):

                    print("SPayLater plan setup failed.")

                    return False

                return True

        #
        # Otherwise we need to change payment.
        #
        print("SPayLater not currently selected.")

        print("Looking for payment CHANGE...")

        change = page.locator("text=CHANGE").last

        if await change.count() == 0:

            raise Exception(
                "Payment CHANGE button not found."
            )

        await change.click()

        await page.wait_for_timeout(1000)

        print("Payment options opened.")

        preferred_methods = [
            "SPayLater",
            "Cash on Delivery",
        ]

        buttons = page.locator(
            "button, div[role='button']"
        )

        count = await buttons.count()

        selected = False

        for payment in preferred_methods:

            print(f"Trying payment: {payment}")

            for i in range(count):

                btn = buttons.nth(i)

                try:

                    text = (
                        await btn.inner_text()
                    ).strip()

                except:
                    continue

                if payment not in text:
                    continue

                print(f"Found: {text}")

                try:

                    await btn.scroll_into_view_if_needed()

                    await page.wait_for_timeout(300)

                    await btn.click(timeout=1500)

                    print(f"✓ Selected {payment}")

                    if payment == "SPayLater":

                        if not await self.select_spaylater_plan(page):

                            print("SPayLater plan setup failed.")

                            continue

                    self.selected_payment = payment

                    selected = True

                    break

                except Exception as e:

                    print(f"Cannot use {payment}: {e}")

            if selected:
                break

        if not selected:

            raise Exception(
                "No supported payment method available."
            )

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
        summary["payment"] = self.selected_payment or "Unknown"

        #
        # --------------------------
        # Print nicely
        # --------------------------
        #
        for key, value in summary.items():
            print(f"{key:12}: {value}")

        return summary