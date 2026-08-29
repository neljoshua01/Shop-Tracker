from execution.browser.browser_action import BrowserActions
from core.runtime.async_runtime import AsyncRuntime
from execution.checkout.checkout_verifier import CheckoutVerifier
from core.runtime.safety_gate import RuntimeSafetyGate


class CheckoutExecutor:

    def __init__(self, safety_gate=None):
        self.safety_gate = safety_gate or RuntimeSafetyGate.instance()

    def is_final_action_authorized(self):
        try:
            return self.safety_gate.is_final_action_authorized() is True
        except Exception:
            return False

    def execute(self, session):
        print("[CheckoutExecutor] ========== STARTING CHECKOUT ==========")
        browser_session = session.browser_session
        if browser_session is None:
            print("[CheckoutExecutor] Browser session not available.")
            return False

        page = browser_session.page
        actions = BrowserActions(browser_session)

        print(f"[CheckoutExecutor] Current URL: {page.url}")

        if "/cart" not in page.url:
            print("[CheckoutExecutor] Returning existing session to cart.")
            actions.goto("https://shopee.ph/cart")
            if "/cart" not in page.url:
                print("[CheckoutExecutor] Cart page was not reached.")
                return False

        print("[CheckoutExecutor] Cart page confirmed.")
        print("[CheckoutExecutor] Waiting for cart UI...")
        actions.wait_for_timeout(3000)

        item_id = str(session.product.item_id)
        model_id = str(session.variation.model_id)
        print(f"[CheckoutExecutor] Target Item ID: {item_id}")
        print(f"[CheckoutExecutor] Target Model ID: {model_id}")

        checkbox_inputs = actions.find_all("input.stardust-checkbox__input")
        checkbox_count = actions.count(checkbox_inputs)
        print(f"[CheckoutExecutor] Cart checkboxes found: {checkbox_count}")
        if checkbox_count == 0:
            print("[CheckoutExecutor] No cart item checkboxes found.")
            return False

        target_checkbox = None
        target_container = None

        for index in range(checkbox_count):
            checkbox = checkbox_inputs.nth(index)
            current = checkbox
            for level in range(1, 9):
                current = actions.parent(current)
                if current is None:
                    break
                identity_values = []
                for attribute_name in (
                    "data-item-id",
                    "data-model-id",
                    "data-product-id",
                    "data-sku-id",
                    "data-id",
                ):
                    value = actions.attribute(current, attribute_name)
                    if value:
                        identity_values.append(str(value))
                identity_text = " ".join(identity_values)
                container_text = actions.text(current) or ""
                item_match = item_id in identity_text or item_id in container_text
                model_match = model_id in identity_text or model_id in container_text
                if item_match:
                    print(f"[CheckoutExecutor] Target item identity found at parent level {level}.")
                    if model_match:
                        print("[CheckoutExecutor] Target item + model identity matched.")
                    else:
                        print("[CheckoutExecutor] Target item matched; model ID not exposed at this level.")
                    target_checkbox = checkbox
                    target_container = current
                    break
            if target_checkbox is not None:
                break

        if target_checkbox is None:
            print("[CheckoutExecutor] Stable cart identity not found.")
            print("[CheckoutExecutor] Trying product-name fallback...")
            product_locator = actions.find_all(f"text={session.product.product_name}")
            product_count = actions.count(product_locator)
            print(f"[CheckoutExecutor] Product-name matches: {product_count}")
            if product_count > 0:
                current = actions.first(product_locator)
                for _ in range(8):
                    current = actions.parent(current)
                    if current is None:
                        break
                    checkbox_locator = actions.find_all(
                        "input.stardust-checkbox__input",
                        parent=current,
                    )
                    if actions.count(checkbox_locator) > 0:
                        target_checkbox = actions.first(checkbox_locator)
                        target_container = current
                        print("[CheckoutExecutor] Target cart item resolved using product-name fallback.")
                        break

        if target_checkbox is None:
            print("[CheckoutExecutor] Target product could not be resolved inside the cart.")
            return False

        print("[CheckoutExecutor] Target cart item resolved.")
        aria_checked = actions.attribute(target_checkbox, "aria-checked")
        print(f"[CheckoutExecutor] aria-checked before: {aria_checked}")

        if aria_checked == "true":
            print("[CheckoutExecutor] Target item is already selected.")
        else:
            checkbox_parent = actions.parent(target_checkbox)
            checkbox_ui = actions.find_all(".stardust-checkbox__box", parent=checkbox_parent)
            if actions.count(checkbox_ui) == 0:
                print("[CheckoutExecutor] Visible checkbox UI not found.")
                return False
            actions.click(actions.first(checkbox_ui))
            print("[CheckoutExecutor] Target checkbox clicked.")
            actions.wait_for_timeout(500)

        aria_checked = actions.attribute(target_checkbox, "aria-checked")
        print(f"[CheckoutExecutor] aria-checked after: {aria_checked}")
        if aria_checked != "true":
            print("[CheckoutExecutor] Target item was NOT selected.")
            return False
        print("[CheckoutExecutor] Target item selected successfully.")

        checkout_buttons = actions.find_all("button:has-text('Check Out')")
        checkout_count = actions.count(checkout_buttons)
        print(f"[CheckoutExecutor] Check Out buttons found: {checkout_count}")
        if checkout_count == 0:
            print("[CheckoutExecutor] Check Out button not found.")
            return False

        print("[CheckoutExecutor] Check Out button found.")
        actions.click(actions.first(checkout_buttons))
        print("[CheckoutExecutor] Check Out clicked.")
        actions.wait_for_timeout(3000)
        print(f"[CheckoutExecutor] Current URL after checkout: {page.url}")

        if "/checkout" not in page.url:
            print("[CheckoutExecutor] Checkout page was not reached.")
            return False
        print("[CheckoutExecutor] Checkout page reached.")

        requested_payment = session.request.payment_method.value
        print(f"[CheckoutExecutor] Requested payment: {requested_payment}")
        checkout_verifier = CheckoutVerifier()

        payment_selected = AsyncRuntime.instance().submit(
            checkout_verifier.select_payment(page, requested_payment)
        ).result(timeout=15)
        if not payment_selected:
            print("[CheckoutExecutor] Configured payment could not be selected.")
            return False

        payment_verified = AsyncRuntime.instance().submit(
            checkout_verifier.verify_payment(requested_payment)
        ).result(timeout=15)
        if not payment_verified:
            print("[CheckoutExecutor] Configured payment verification failed.")
            return False
        print(f"[CheckoutExecutor] Payment verified: {requested_payment}")

        protection_disabled = AsyncRuntime.instance().submit(
            checkout_verifier.disable_protection(page)
        ).result(timeout=15)
        if not protection_disabled:
            print("[CheckoutExecutor] Protection handling failed.")
            return False
        print("[CheckoutExecutor] Protection state verified.")

        # Allow checkout totals to settle after any protection change before
        # collecting the monetary state used for final verification.
        actions.wait_for_timeout(1000)

        summary = AsyncRuntime.instance().submit(
            checkout_verifier.collect_order_summary(page)
        ).result(timeout=15)

        state_verified = AsyncRuntime.instance().submit(
            checkout_verifier.verify_order_summary(page, session, summary)
        ).result(timeout=15)
        if not state_verified:
            print("[CheckoutExecutor] Checkout state verification failed.")
            return False

        verified = AsyncRuntime.instance().submit(
            checkout_verifier.verify_place_order(page)
        ).result(timeout=15)
        if not verified:
            print("[CheckoutExecutor] Place Order button was not detected.")
            return False

        print("[CheckoutExecutor] Place Order button detected.")
        if not self.is_final_action_authorized():
            print("[CheckoutExecutor] SAFE: final action authorization denied; Place Order will not be clicked.")
            print("[CheckoutExecutor] Checkout verification complete.")
            return True

        print("[CheckoutExecutor] ARMED: final action authorized.")

        # Re-resolve the final action only after every checkout verification
        # has passed and runtime authorization has been confirmed. This keeps
        # SAFE/ARMED authorization as the final gate immediately before the
        # irreversible action.
        place_order = page.get_by_role("button", name="Place Order").first
        if actions.count(place_order) == 0:
            print("[CheckoutExecutor] ARMED: Place Order button is no longer available; action aborted.")
            return False

        try:
            actions.click(place_order)
        except Exception as e:
            print(f"[CheckoutExecutor] ARMED: Place Order click failed: {e}")
            return False

        print("[CheckoutExecutor] ARMED: Place Order clicked.")
        print("[CheckoutExecutor] Checkout verification complete.")
        return True
