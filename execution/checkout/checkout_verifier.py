import re


class CheckoutVerifier:

    def __init__(self):
        self.selected_payment = None

    async def verify_price(self, page, product):
        print()
        print("========== VERIFY PRICE ==========")

        body = await page.locator("body").inner_text()
        total_match = re.search(
            r"Total Payment:\s*₱\s*([\d,]+(?:\.\d{2})?)",
            body,
            re.IGNORECASE,
        )
        if not total_match:
            print("❌ Could not locate 'Total Payment' on checkout page.")
            return False

        checkout_display_price = total_match.group(1)
        checkout_pesos = float(checkout_display_price.replace(",", ""))
        checkout_total = int(checkout_pesos * 100_000)

        target_price = getattr(product, "target_price", None)
        if target_price is None:
            print("❌ No target price configured.")
            return False

        if checkout_total > target_price:
            print("❌ Checkout total exceeds target price.")
            return False

        print("✓ Checkout total is within target.")
        return True

    async def _find_protection_row(self, learn_more_link):
        """
        Walk up from a 'Learn more' link until reaching an ancestor
        that mentions Protection and contains a checkbox descendant.
        """
        current = learn_more_link

        for _ in range(8):
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
                "Protection option",
            )
            print(f"{label} found.")

            checkbox = row.locator("input[type='checkbox']").first
            if await checkbox.count() == 0:
                print(f"No checkbox found for {label} — protection state cannot be safely verified.")
                return False

            if not await checkbox.is_checked():
                print(f"{label} already unchecked — no action needed.")
                continue

            await checkbox.scroll_into_view_if_needed()
            await checkbox.click(force=True)
            print(f"{label} uncheck requested.")
            await page.wait_for_timeout(1000)

            if await checkbox.is_checked():
                print(f"❌ {label} remains checked after disable attempt.")
                return False

            print(f"✓ {label} verified unchecked.")

        if not found_any:
            print("No protection option found.")

        return True

    async def handle_checkout_dialog(self, page):
        print()
        print("========== CHECKOUT DIALOG ==========")

        confirm = page.get_by_role("button", name="Confirm")
        try:
            await confirm.first.wait_for(state="visible", timeout=2000)
        except Exception:
            print("No checkout dialog.")
            return False

        print("Checkout dialog detected.")
        await confirm.first.click()
        print("✓ Checkout dialog confirmed.")
        await confirm.first.wait_for(state="hidden", timeout=5000)
        print("✓ Dialog closed.")
        return True

    async def verify_ready(self, page):
        print()
        print("========== FINAL CHECK ==========")
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
        # Deliberately does not click Place Order.
        return True

    async def select_spaylater_plan(self, page):
        print()
        print("========== SPAYLATER PLAN ==========")

        plan = page.get_by_text("Buy Now Pay Later", exact=False)
        try:
            await plan.first.wait_for(state="visible", timeout=5000)
        except Exception:
            print("❌ Buy Now Pay Later plan not found.")
            return False

        await plan.first.click()
        print("✓ Buy Now Pay Later selected")
        await page.wait_for_timeout(500)
        return True

    async def select_payment(self, page, requested_payment):
        self.selected_payment = None

        print()
        print("========== SELECT PAYMENT ==========")

        await self.handle_checkout_dialog(page)

        requested_button = page.locator(
            f"button:has-text('{requested_payment}')"
        )

        if await requested_button.count() > 0:
            classes = await requested_button.first.get_attribute("class") or ""
            aria = await requested_button.first.get_attribute("aria-pressed")

            if (
                "selected" in classes.lower()
                or "active" in classes.lower()
                or aria == "true"
            ):
                print(
                    "[CheckoutVerifier] "
                    f"✓ {requested_payment} already selected."
                )

                if requested_payment == "SPayLater":
                    if not await self.select_spaylater_plan(page):
                        print(
                            "[CheckoutVerifier] "
                            "SPayLater plan setup failed."
                        )
                        return False

                self.selected_payment = requested_payment
                return True

        print(
            "[CheckoutVerifier] "
            f"Looking for requested payment directly: {requested_payment}"
        )

        payment_button = page.locator(
            f"button[aria-label='{requested_payment}']"
        )

        if await payment_button.count() == 0:
            payment_button = page.get_by_role(
                "radio",
                name=requested_payment,
                exact=True,
            )

        if await payment_button.count() == 0:
            raise Exception(
                f"Requested payment method not found: {requested_payment}"
            )

        payment_button = payment_button.first
        aria_checked = await payment_button.get_attribute("aria-checked")
        aria_pressed = await payment_button.get_attribute("aria-pressed")
        classes = await payment_button.get_attribute("class") or ""

        print(
            "[CheckoutVerifier] "
            f"Requested payment state: aria-checked={aria_checked}, "
            f"aria-pressed={aria_pressed}"
        )

        already_selected = (
            aria_checked == "true"
            or aria_pressed == "true"
            or "selected" in classes.lower()
            or "active" in classes.lower()
        )

        if not already_selected:
            print(
                "[CheckoutVerifier] "
                f"Clicking {requested_payment} directly."
            )
            await payment_button.scroll_into_view_if_needed()
            await page.wait_for_timeout(300)
            await payment_button.click(timeout=3000)
            print(
                "[CheckoutVerifier] "
                f"✓ Selected {requested_payment}"
            )
        else:
            print(
                "[CheckoutVerifier] "
                f"✓ {requested_payment} already selected."
            )

        if requested_payment == "SPayLater":
            if not await self.select_spaylater_plan(page):
                print(
                    "[CheckoutVerifier] "
                    "SPayLater plan setup failed."
                )
                return False

        self.selected_payment = requested_payment
        await page.wait_for_timeout(1000)
        return True

    async def verify_payment(self, expected_payment):
        print()
        print("========== VERIFY PAYMENT ==========")

        if self.selected_payment is None:
            print("❌ No payment method has been selected.")
            return False

        print(f"Selected Payment: {self.selected_payment}")
        print(f"Expected Payment: {expected_payment}")

        if self.selected_payment != expected_payment:
            print("❌ Selected payment does not match expected payment.")
            return False

        print("✓ Payment method matches expected payment.")
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
            "item_discount": None,
            "voucher_discount": None,
            "shipping": None,
            "total": None,
            "payment": None,
        }

        # Seller and product are intentionally resolved independently. A
        # checkout line such as "YINGLI PC" can be the seller even when it is
        # located inside the Products Ordered section. The old parser assumed
        # the first non-metadata line was always the product, which could make
        # the seller name become the product for some checkout layouts.
        seller_candidates = []
        for line in lines:
            if line.startswith("Sold by "):
                seller = line[len("Sold by "):].strip()
                if seller:
                    seller_candidates.append(seller)
        if seller_candidates:
            summary["seller"] = seller_candidates[0]

        def _is_summary_metadata(line):
            normalized = self._normalize(line)
            if not normalized:
                return True
            if normalized in {
                "products ordered",
                "unit price",
                "quantity",
                "item subtotal",
                "fulfilled - local",
                "parcel 1",
            }:
                return True
            if normalized.startswith("sold by "):
                return True
            if "spaylater" in normalized:
                return True
            if line.startswith("₱"):
                return True
            if re.fullmatch(r"\d+", line):
                return True
            return False

        # Prefer the product text structurally associated with the variation
        # row. On Shopee checkout, the product title and its variation/quantity
        # belong to the same product block, while the seller is represented by
        # a separate "Sold by ..." line. This avoids hard-coding seller names
        # and also works when a product title contains digits or punctuation.
        variation_index = next(
            (i for i, line in enumerate(lines) if re.match(r"^Variation:\s*", line, re.IGNORECASE)),
            None,
        )

        if variation_index is not None:
            # Search backward only within the local product block. Stop at
            # structural section boundaries rather than selecting arbitrary
            # text from the whole checkout page.
            for index in range(variation_index - 1, -1, -1):
                line = lines[index]
                if line.startswith("Sold by "):
                    break
                if line in {"Products Ordered", "Unit Price", "Quantity", "Item Subtotal"}:
                    continue
                if _is_summary_metadata(line):
                    continue
                summary["product"] = line
                break

        # Fallback for layouts where Variation is not exposed in the body text.
        # Use the product section but reject known structural labels, seller
        # rows, monetary values, and quantity-only lines. Crucially, do not
        # assume the first arbitrary line is the product when a seller row is
        # present.
        if summary["product"] is None:
            try:
                products_index = lines.index("Products Ordered")
            except ValueError:
                products_index = -1

            if products_index >= 0:
                for line in lines[products_index + 1:]:
                    if line.startswith("Sold by "):
                        continue
                    if _is_summary_metadata(line):
                        continue
                    if " - " in line and any(c.isdigit() for c in line):
                        continue
                    summary["product"] = line
                    break

        variation_match = re.search(r"Variation:\s*(.+)", body)
        if variation_match:
            summary["variation"] = variation_match.group(1).strip()

        if variation_match:
            tail = body[variation_match.end():]
            quantity_match = re.search(r"\n\s*(\d+)\s*\n", tail)
            if quantity_match:
                summary["quantity"] = int(quantity_match.group(1))

        subtotal_match = re.search(
            r"Merchandise Subtotal\s*₱([\d,]+(?:\.\d{2})?)",
            body,
        )
        if subtotal_match:
            summary["subtotal"] = float(
                subtotal_match.group(1).replace(",", "")
            )

        item_discount_match = re.search(
            r"Item Discount\s*-?\s*₱\s*([\d,]+(?:\.\d{2})?)",
            body,
        )
        if item_discount_match:
            summary["item_discount"] = float(
                item_discount_match.group(1).replace(",", "")
            )

        voucher_discount_match = re.search(
            r"Voucher Discount\s*-?\s*₱\s*([\d,]+(?:\.\d{2})?)",
            body,
        )
        if voucher_discount_match:
            summary["voucher_discount"] = float(
                voucher_discount_match.group(1).replace(",", "")
            )

        shipping_match = re.search(
            r"Shipping Subtotal\s*₱([\d,]+(?:\.\d{2})?)",
            body,
        )
        if shipping_match:
            summary["shipping"] = float(
                shipping_match.group(1).replace(",", "")
            )

        total_match = re.search(
            r"Total Payment:\s*₱([\d,]+(?:\.\d{2})?)",
            body,
        )
        if total_match:
            summary["total"] = float(
                total_match.group(1).replace(",", "")
            )

        for key in (
            "product",
            "seller",
            "variation",
            "quantity",
            "subtotal",
            "item_discount",
            "voucher_discount",
            "shipping",
            "total",
            "payment",
        ):
            print(f"[CheckoutVerifier] Checkout {key}: {summary[key]}")

        return summary

    @staticmethod
    def _normalize(value):
        return " ".join(str(value or "").lower().split())

    @staticmethod
    def _verified_merchandise_upper_bound(summary):
        """Return the strongest safe upper bound supported by parsed checkout data.

        Missing discounts are not interpreted as zero. A missing discount simply
        means that no reduction can be claimed from that field. The subtotal is
        therefore retained as the conservative upper bound unless an observed
        discount can safely reduce it further.
        """
        subtotal = summary.get("subtotal")
        if subtotal is None:
            return None

        try:
            upper_bound = float(subtotal)
        except (TypeError, ValueError):
            return None

        if upper_bound < 0:
            return None

        for field in ("item_discount", "voucher_discount"):
            discount = summary.get(field)
            if discount is None:
                continue

            try:
                discount = float(discount)
            except (TypeError, ValueError):
                return None

            if discount < 0 or discount > upper_bound:
                return None

            upper_bound -= discount

        return upper_bound

    def _variation_matches(self, expected_variation, actual_variation):
        actual = self._normalize(actual_variation)
        if not actual:
            return False

        options = getattr(expected_variation, "options", {}) or {}
        if options:
            normalized_values = [
                self._normalize(value)
                for value in options.values()
                if self._normalize(value)
            ]

            if not normalized_values:
                return False

            if len(normalized_values) == 1:
                return actual == normalized_values[0]

            return all(value in actual for value in normalized_values)

        expected_name = self._normalize(
            getattr(expected_variation, "name", "")
        )
        return bool(expected_name) and expected_name == actual

    async def verify_order_summary(self, page, session, summary):
        print()
        print("[CheckoutVerifier] Verifying checkout state...")
        passed = True

        expected_product = self._normalize(session.product.product_name)
        actual_product = self._normalize(summary.get("product"))

        if not actual_product:
            print("[CheckoutVerifier] ❌ Product verification unavailable.")
            passed = False
        elif actual_product != expected_product:
            print(
                "[CheckoutVerifier] ❌ Product mismatch: "
                f"expected {session.product.product_name}, "
                f"actual {summary.get('product')}"
            )
            passed = False
        else:
            print("[CheckoutVerifier] Product verified.")

        expected_variation = session.variation
        actual_variation = summary.get("variation")
        if not self._variation_matches(expected_variation, actual_variation):
            print(
                "[CheckoutVerifier] ❌ Variation mismatch: "
                f"expected {getattr(expected_variation, 'name', None)}, "
                f"actual {actual_variation}"
            )
            passed = False
        else:
            print("[CheckoutVerifier] Variation verified.")

        expected_quantity = session.request.quantity
        if not isinstance(expected_quantity, int) or expected_quantity < 1:
            print(
                "[CheckoutVerifier] ❌ Invalid requested quantity: "
                f"{expected_quantity}"
            )
            passed = False

        actual_quantity = summary.get("quantity")
        if actual_quantity is None:
            print("[CheckoutVerifier] ❌ Checkout quantity unavailable.")
            passed = False
        elif actual_quantity != expected_quantity:
            print(
                "[CheckoutVerifier] ❌ Quantity mismatch: "
                f"expected {expected_quantity}, actual {actual_quantity}"
            )
            passed = False
        else:
            print("[CheckoutVerifier] Quantity verified.")

        seller = summary.get("seller")
        expected_seller = self._normalize(
            getattr(session.product, "shop_name", None)
        )
        if seller and expected_seller:
            if self._normalize(seller) != expected_seller:
                print(
                    "[CheckoutVerifier] ❌ Seller mismatch: "
                    f"expected {session.product.shop_name}, actual {seller}"
                )
                passed = False
            else:
                print("[CheckoutVerifier] Seller verified.")
        else:
            print(
                "[CheckoutVerifier] Seller not reliably available; "
                "informational only."
            )

        actual_subtotal = summary.get("subtotal")
        expected_unit_price = getattr(session.variation, "price", None)
        if actual_subtotal is None:
            print("[CheckoutVerifier] ❌ Checkout subtotal unavailable.")
            passed = False
        elif expected_unit_price is None:
            print(
                "[CheckoutVerifier] ❌ Selected SKU price unavailable; "
                "merchandise value cannot be verified."
            )
            passed = False
        else:
            verified_merchandise_upper_bound = self._verified_merchandise_upper_bound(summary)
            if verified_merchandise_upper_bound is None:
                print(
                    "[CheckoutVerifier] ❌ Checkout merchandise accounting "
                    "is invalid or unavailable; SKU consistency cannot be verified."
                )
                passed = False
            else:
                expected_merchandise = float(expected_unit_price) * expected_quantity

                if verified_merchandise_upper_bound > expected_merchandise:
                    print(
                        "[CheckoutVerifier] ❌ Checkout merchandise value "
                        "cannot be proven within selected SKU value: "
                        f"expected ≤ {expected_merchandise:g}, "
                        f"verified upper bound {verified_merchandise_upper_bound:g}"
                    )
                    passed = False
                else:
                    print(
                        "[CheckoutVerifier] Checkout merchandise value verified "
                        "within selected SKU value."
                    )

        actual_shipping = summary.get("shipping")
        if actual_shipping is None:
            print("[CheckoutVerifier] ❌ Checkout shipping unavailable.")
            passed = False
        else:
            print("[CheckoutVerifier] Shipping detected.")

        actual_total = summary.get("total")
        if actual_total is None:
            print("[CheckoutVerifier] ❌ Checkout total unavailable.")
            passed = False
        else:
            print("[CheckoutVerifier] Total detected.")

        target_price = session.request.target_price
        if target_price is None:
            print("[CheckoutVerifier] ❌ Configured target price unavailable.")
            passed = False
        elif actual_total is not None:
            actual_total_internal = int(
                round(float(actual_total) * 100_000)
            )
            if actual_total_internal > target_price:
                print(
                    "[CheckoutVerifier] ❌ Checkout total exceeds configured "
                    f"target: expected ≤ {target_price}, "
                    f"actual {actual_total_internal}"
                )
                passed = False
            else:
                print("[CheckoutVerifier] Checkout total is within configured target.")

        if self.selected_payment != session.request.payment_method.value:
            print(
                "[CheckoutVerifier] ❌ Payment verification state does not "
                "match the PurchaseRequest."
            )
            passed = False
        else:
            print("[CheckoutVerifier] Payment verified.")

        if not passed:
            print("[CheckoutVerifier] ❌ Checkout state verification FAILED.")
            return False

        print("[CheckoutVerifier] Checkout state verified.")
        return True