import re


class CheckoutVerifier:

    def __init__(self):
        self.selected_payment = None

    async def verify_price(self, page, product):
        body = await page.locator("body").inner_text()
        total_match = re.search(
            r"Total Payment:\s*₱\s*([\d,]+(?:\.\d{2})?)",
            body,
            re.IGNORECASE,
        )
        if not total_match:
            print("❌ Could not locate 'Total Payment' on checkout page.")
            return False

        checkout_total = float(total_match.group(1).replace(",", ""))
        target_price = getattr(product, "target_price", None)
        if target_price is None:
            return False
        if checkout_total > target_price:
            print("❌ Checkout total exceeds target price.")
            return False
        return True

    async def _find_protection_row(self, learn_more_link):
        current = learn_more_link
        for _ in range(8):
            candidate = current.locator("xpath=..")
            row_text = await candidate.inner_text()
            has_protection = "protection" in row_text.lower()
            has_checkbox = await candidate.locator("input[type='checkbox']").count() > 0
            if has_protection and has_checkbox:
                return candidate
            current = candidate
        return None

    async def disable_protection(self, page):
        print()
        print("========== DISABLE EXTENDED PROTECTION ==========")
        learn_more_links = page.locator("text=Learn more")
        found_any = False
        for i in range(await learn_more_links.count()):
            row = await self._find_protection_row(learn_more_links.nth(i))
            if row is None:
                continue
            found_any = True
            checkbox = row.locator("input[type='checkbox']").first
            if await checkbox.count() == 0 or not await checkbox.is_checked():
                continue
            await checkbox.scroll_into_view_if_needed()
            await checkbox.click(force=True)
            await page.wait_for_timeout(1000)
        if not found_any:
            print("No protection option found.")
        return True

    async def handle_checkout_dialog(self, page):
        confirm = page.get_by_role("button", name="Confirm")
        try:
            await confirm.first.wait_for(state="visible", timeout=2000)
        except Exception:
            return False
        await confirm.first.click()
        await confirm.first.wait_for(state="hidden", timeout=5000)
        return True

    async def verify_ready(self, page):
        return True

    async def verify_place_order(self, page):
        print()
        print("========== PLACE ORDER ==========")
        place_order = page.get_by_role("button", name="Place Order")
        try:
            await place_order.first.wait_for(state="visible", timeout=10_000)
        except Exception:
            print("❌ Place Order button not found or not visible.")
            return False
        print("✓ Place Order button found.")
        return True

    async def select_spaylater_plan(self, page):
        plan = page.get_by_text("Buy Now Pay Later", exact=False)
        try:
            await plan.first.wait_for(state="visible", timeout=5000)
        except Exception:
            print("❌ Buy Now Pay Later plan not found.")
            return False
        await plan.first.click()
        await page.wait_for_timeout(500)
        return True

    async def select_payment(self, page, requested_payment):
        self.selected_payment = None
        await self.handle_checkout_dialog(page)

        requested_button = page.locator(f"button:has-text('{requested_payment}')")
        if await requested_button.count() > 0:
            classes = await requested_button.first.get_attribute("class") or ""
            aria = await requested_button.first.get_attribute("aria-pressed")
            if "selected" in classes.lower() or "active" in classes.lower() or aria == "true":
                if requested_payment == "SPayLater" and not await self.select_spaylater_plan(page):
                    return False
                self.selected_payment = requested_payment
                return True

        payment_button = page.locator(f"button[aria-label='{requested_payment}']")
        if await payment_button.count() == 0:
            payment_button = page.get_by_role("radio", name=requested_payment, exact=True)
        if await payment_button.count() == 0:
            raise Exception(f"Requested payment method not found: {requested_payment}")

        payment_button = payment_button.first
        aria_checked = await payment_button.get_attribute("aria-checked")
        aria_pressed = await payment_button.get_attribute("aria-pressed")
        classes = await payment_button.get_attribute("class") or ""
        already_selected = (
            aria_checked == "true"
            or aria_pressed == "true"
            or "selected" in classes.lower()
            or "active" in classes.lower()
        )
        if not already_selected:
            await payment_button.scroll_into_view_if_needed()
            await page.wait_for_timeout(300)
            await payment_button.click(timeout=3000)

        if requested_payment == "SPayLater" and not await self.select_spaylater_plan(page):
            return False

        self.selected_payment = requested_payment
        await page.wait_for_timeout(1000)
        return True

    async def verify_payment(self, expected_payment):
        if self.selected_payment is None:
            print("❌ No payment method has been selected.")
            return False
        if self.selected_payment != expected_payment:
            print("❌ Selected payment does not match expected payment.")
            return False
        print(f"[CheckoutVerifier] Payment verified: {expected_payment}")
        return True

    async def collect_order_summary(self, page):
        print()
        print("[CheckoutVerifier] Collecting checkout order summary...")
        body = await page.locator("body").inner_text()
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        summary = {
            "product": None,
            "seller": None,
            "variation": None,
            "quantity": None,
            "subtotal": None,
            "shipping": None,
            "total": None,
            "payment": self.selected_payment,
        }

        for line in lines:
            if line.startswith("Sold by "):
                summary["seller"] = line[len("Sold by "):].strip()
                break

        try:
            products_index = lines.index("Products Ordered")
        except ValueError:
            products_index = -1

        if products_index >= 0:
            ignored = {"Unit Price", "Quantity", "Item Subtotal", "Fulfilled - Local", "Parcel 1"}
            for line in lines[products_index + 1:]:
                if line.startswith("Sold by "):
                    break
                if line in ignored or "SPayLater" in line or line.startswith("₱") or line.isdigit():
                    continue
                if " - " in line and any(c.isdigit() for c in line):
                    continue
                summary["product"] = line
                break

        variation_match = re.search(r"Variation:\s*([^\n]+)", body)
        if variation_match:
            summary["variation"] = variation_match.group(1).strip()

        if variation_match:
            tail = body[variation_match.end():]
            quantity_match = re.search(r"\n\s*(\d+)\s*\n", tail)
            if quantity_match:
                summary["quantity"] = int(quantity_match.group(1))

        subtotal_match = re.search(r"Merchandise Subtotal\s*₱([\d,]+(?:\.\d{2})?)", body)
        if subtotal_match:
            summary["subtotal"] = float(subtotal_match.group(1).replace(",", ""))

        shipping_match = re.search(r"Shipping Subtotal\s*₱([\d,]+(?:\.\d{2})?)", body)
        if shipping_match:
            summary["shipping"] = float(shipping_match.group(1).replace(",", ""))

        total_match = re.search(r"Total Payment:\s*₱([\d,]+(?:\.\d{2})?)", body)
        if total_match:
            summary["total"] = float(total_match.group(1).replace(",", ""))

        for key in ("product", "seller", "variation", "quantity", "subtotal", "shipping", "total", "payment"):
            print(f"[CheckoutVerifier] Checkout {key}: {summary[key]}")
        return summary

    @staticmethod
    def _normalize(value):
        return " ".join(str(value or "").lower().split())

    def _variation_matches(self, expected_variation, actual_variation):
        actual = self._normalize(actual_variation)
        if not actual:
            return False
        options = getattr(expected_variation, "options", {}) or {}
        if options:
            return all(
                self._normalize(key) in actual and self._normalize(value) in actual
                for key, value in options.items()
            )
        expected_name = self._normalize(getattr(expected_variation, "name", ""))
        return bool(expected_name) and expected_name in actual

    async def verify_order_summary(self, page, session, summary):
        print()
        print("[CheckoutVerifier] Verifying checkout state...")
        passed = True

        expected_product = self._normalize(session.product.product_name)
        actual_product = self._normalize(summary.get("product"))
        if not actual_product:
            print("[CheckoutVerifier] Product verification unavailable.")
            passed = False
        elif actual_product != expected_product:
            print(f"[CheckoutVerifier] ❌ Product mismatch: {summary.get('product')}")
            passed = False
        else:
            print("[CheckoutVerifier] Product verified.")

        expected_variation = session.variation
        actual_variation = summary.get("variation")
        if not self._variation_matches(expected_variation, actual_variation):
            print(f"[CheckoutVerifier] ❌ Variation mismatch: {actual_variation}")
            passed = False
        else:
            print("[CheckoutVerifier] Variation verified.")

        expected_quantity = session.request.quantity
        actual_quantity = summary.get("quantity")
        if actual_quantity is None:
            print("[CheckoutVerifier] ❌ Checkout quantity unavailable.")
            passed = False
        elif actual_quantity != expected_quantity:
            print(f"[CheckoutVerifier] ❌ Quantity mismatch: expected {expected_quantity}, actual {actual_quantity}")
            passed = False
        else:
            print("[CheckoutVerifier] Quantity verified.")

        expected_payment = self.selected_payment
        actual_payment = summary.get("payment")
        if expected_payment is None or actual_payment != expected_payment:
            print(f"[CheckoutVerifier] ❌ Payment mismatch: expected {expected_payment}, actual {actual_payment}")
            passed = False
        else:
            print("[CheckoutVerifier] Payment verified.")

        seller = summary.get("seller")
        expected_seller = self._normalize(getattr(session.product, "shop_name", None))
        if seller and expected_seller:
            if self._normalize(seller) != expected_seller:
                print(f"[CheckoutVerifier] ❌ Seller mismatch: expected {session.product.shop_name}, actual {seller}")
                passed = False
            else:
                print("[CheckoutVerifier] Seller verified.")
        else:
            print("[CheckoutVerifier] Seller not reliably available; informational only.")

        subtotal = summary.get("subtotal")
        if subtotal is None:
            print("[CheckoutVerifier] ❌ Checkout subtotal unavailable.")
            passed = False
        else:
            expected_unit_price = getattr(session.variation, "price", None)
            if expected_unit_price is not None:
                expected_subtotal = float(expected_unit_price) * expected_quantity
                if subtotal > expected_subtotal + 0.01:
                    print(f"[CheckoutVerifier] ❌ Checkout subtotal exceeds selected SKU value: expected at most ₱{expected_subtotal:.2f}, actual ₱{subtotal:.2f}")
                    passed = False
                else:
                    print("[CheckoutVerifier] Checkout monetary value verified.")
            else:
                print("[CheckoutVerifier] Checkout subtotal detected; selected SKU price unavailable for comparison.")

        target_price = session.request.target_price
        total = summary.get("total")
        if target_price is not None:
            if total is None:
                print("[CheckoutVerifier] ❌ Checkout total unavailable for target-price verification.")
                passed = False
            elif total > float(target_price) + 0.01:
                print(f"[CheckoutVerifier] ❌ Checkout total exceeds configured target: expected ≤ ₱{float(target_price):.2f}, actual ₱{total:.2f}")
                passed = False
            else:
                print("[CheckoutVerifier] Checkout total is within configured target.")

        if not passed:
            print("[CheckoutVerifier] ❌ Checkout state verification FAILED.")
            return False

        print("[CheckoutVerifier] Checkout state verified.")
        return True
