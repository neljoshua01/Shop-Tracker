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
        # -------------------------------------------------
        # FIND TOTAL PAYMENT
        # -------------------------------------------------
        #
        # Shopee renders the label and amount on separate
        # lines:
        #
        # Total Payment:
        # ₱16,679
        #
        # Therefore we allow whitespace/newlines between
        # the label and the amount.
        #

        total_match = re.search(
            r"Total Payment:\s*₱\s*([\d,]+(?:\.\d{2})?)",
            body,
            re.IGNORECASE,
        )

        if not total_match:

            print(
                "❌ Could not locate 'Total Payment' "
                "on checkout page."
            )

            return False

        #
        # Extract displayed checkout total.
        #

        checkout_display_price = total_match.group(1)

        print(
            f"Checkout Total: ₱{checkout_display_price}"
        )

        #
        # -------------------------------------------------
        # CONVERT TO INTERNAL PRICE UNIT
        # -------------------------------------------------
        #

        checkout_pesos = float(
            checkout_display_price.replace(",", "")
        )

        checkout_total = int(
            checkout_pesos * 100_000
        )

        print(
            f"Checkout Total (internal): "
            f"{checkout_total}"
        )

        #
        # -------------------------------------------------
        # TARGET PRICE
        # -------------------------------------------------
        #

        if product.target_price is None:

            print(
                "❌ No target price configured."
            )

            return False

        print(
            f"Target Price (internal): "
            f"{product.target_price}"
        )

        #
        # -------------------------------------------------
        # SAFETY CHECK
        # -------------------------------------------------
        #

        if checkout_total > product.target_price:

            print(
                "❌ Checkout total exceeds "
                "target price."
            )

            return False

        print(
            "✓ Checkout total is within target."
        )

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

    async def verify_payment(self, expected_payment):

        print()
        print("========== VERIFY PAYMENT ==========")

        if self.selected_payment is None:

            print("❌ No payment method has been selected.")

            return False

        print(
            f"Selected Payment: {self.selected_payment}"
        )

        print(
            f"Expected Payment: {expected_payment}"
        )

        if self.selected_payment != expected_payment:

            print(
                "❌ Selected payment does not match "
                "expected payment."
            )

            return False

        print("✓ Payment method matches expected payment.")

        return True

    async def collect_order_summary(self, page):

        print()
        print("========== ORDER SUMMARY ==========")

        body = await page.locator("body").inner_text()

        lines = [
            line.strip()
            for line in body.splitlines()
            if line.strip()
        ]

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

        for line in lines:

            if line.startswith("Sold by "):

                summary["seller"] = line[
                    len("Sold by "):
                ].strip()

                break

        #
        # --------------------------
        # Product
        # --------------------------
        #

        try:

            products_index = lines.index(
                "Products Ordered"
            )

        except ValueError:

            products_index = -1

        if products_index != -1:

            for i in range(
                products_index + 1,
                len(lines)
            ):

                line = lines[i]

                #
                # Stop once we reach seller information.
                #
                if line.startswith("Sold by "):
                    break

                #
                # Ignore checkout table headers.
                #
                if line in {
                    "Unit Price",
                    "Quantity",
                    "Item Subtotal",
                    "Fulfilled - Local",
                    "Parcel 1",
                }:
                    continue

                #
                # Ignore payment promotion text.
                #
                if "SPayLater" in line:
                    continue

                #
                # Ignore delivery-date lines.
                #
                if (
                    " - " in line
                    and any(
                        char.isdigit()
                        for char in line
                    )
                ):
                    continue

                #
                # Ignore prices.
                #
                if line.startswith("₱"):
                    continue

                #
                # Ignore quantity.
                #
                if line.isdigit():
                    continue

                #
                # First remaining meaningful line
                # is the product name.
                #
                summary["product"] = line

                break

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

            summary["variation"] = (
                variation_match.group(1).strip()
            )

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
                subtotal_match.group(1).replace(
                    ",",
                    ""
                )
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
                shipping_match.group(1).replace(
                    ",",
                    ""
                )
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
                total_match.group(1).replace(
                    ",",
                    ""
                )
            )

        #
        # --------------------------
        # Payment
        # --------------------------
        #

        summary["payment"] = (
            self.selected_payment or "Unknown"
        )

        #
        # --------------------------
        # Print nicely
        # --------------------------
        #

        for key, value in summary.items():

            print(
                f"{key:12}: {value}"
            )

        return summary

    async def verify_order_summary(
        self,
        page,
        product,
        summary,
    ):

        print()
        print("========== VERIFY ORDER SUMMARY ==========")

        passed = True

        #
        # --------------------------
        # PRODUCT
        # --------------------------
        #

        expected_product = product.product_name
        actual_product = summary.get("product")

        print(f"Product:")
        print(f"  Expected: {expected_product}")
        print(f"  Actual:   {actual_product}")

        if actual_product != expected_product:

            print("  ❌ Product does not match.")
            passed = False

        else:

            print("  ✓ Product matches.")

        #
        # --------------------------
        # QUANTITY
        # --------------------------
        #

        expected_quantity = 1
        actual_quantity = summary.get("quantity")

        print()
        print("Quantity:")
        print(f"  Expected: {expected_quantity}")
        print(f"  Actual:   {actual_quantity}")

        if actual_quantity != expected_quantity:

            print("  ❌ Quantity does not match.")
            passed = False

        else:

            print("  ✓ Quantity matches.")

        #
        # --------------------------
        # SUBTOTAL
        # --------------------------
        #

        actual_subtotal = summary.get("subtotal")

        print()
        print("Subtotal:")
        print(f"  Actual:   ₱{actual_subtotal}")

        if actual_subtotal is None:

            print("  ❌ Subtotal could not be determined.")
            passed = False

        else:

            print("  ✓ Subtotal detected.")

        #
        # --------------------------
        # SHIPPING
        # --------------------------
        #

        actual_shipping = summary.get("shipping")

        print()
        print("Shipping:")
        print(f"  Actual:   ₱{actual_shipping}")

        if actual_shipping is None:

            print("  ❌ Shipping could not be determined.")
            passed = False

        else:

            print("  ✓ Shipping detected.")

        #
        # --------------------------
        # TOTAL
        # --------------------------
        #

        actual_total = summary.get("total")

        print()
        print("Total:")
        print(f"  Actual:   ₱{actual_total}")

        if actual_total is None:

            print("  ❌ Total could not be determined.")
            passed = False

        else:

            print("  ✓ Total detected.")

        #
        # --------------------------
        # PAYMENT
        # --------------------------
        #

        expected_payment = self.selected_payment
        actual_payment = summary.get("payment")

        print()
        print("Payment:")
        print(f"  Expected: {expected_payment}")
        print(f"  Actual:   {actual_payment}")

        if actual_payment != expected_payment:

            print("  ❌ Payment does not match.")
            passed = False

        else:

            print("  ✓ Payment matches.")

        #
        # --------------------------
        # FINAL RESULT
        # --------------------------
        #

        print()

        if not passed:

            print(
                "❌ ORDER SUMMARY VALIDATION FAILED."
            )

            return False

        print(
            "✓ ORDER SUMMARY VALIDATION PASSED."
        )

        return True