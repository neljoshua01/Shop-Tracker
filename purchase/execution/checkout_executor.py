from execution.browser.browser_action import BrowserActions
from core.runtime.async_runtime import AsyncRuntime
from execution.checkout.checkout_verifier import CheckoutVerifier
from core.runtime.safety_gate import RuntimeSafetyGate
from purchase.services.post_order_tracker import PostOrderTracker
from purchase.services.monitored_order_identity import MonitoredOrderIdentityInspector
from purchase.services.successful_purchase_identity import SuccessfulPurchaseIdentityInspector


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
        print("[CheckoutExecutor] Waiting for cart UI readiness...")
        try:
            actions.wait_for_selector(
                "input.stardust-checkbox__input",
                timeout=10000,
            )
        except Exception as e:
            print(f"[CheckoutExecutor] Cart UI readiness wait failed: {e}")
            return False

        item_id = str(session.product.item_id)
        model_id = str(session.variation.model_id)
        print(f"[CheckoutExecutor] Target Item ID: {item_id}")
        print(f"[CheckoutExecutor] Target Model ID: {model_id}")

        requested_options = {
            str(key).strip().lower(): str(value).strip().lower()
            for key, value in session.request.options.items()
        }

        cart_inspection = actions.inspect_cart_candidates(
            item_id=item_id,
            model_id=model_id,
            product_name=session.product.product_name,
            requested_options=requested_options,
        )

        checkbox_count = int(cart_inspection.get("checkbox_count", 0))
        print(f"[CheckoutExecutor] Cart checkboxes found: {checkbox_count}")
        if checkbox_count == 0:
            print("[CheckoutExecutor] No cart item checkboxes found.")
            return False

        checkbox_inputs = actions.find_all("input.stardust-checkbox__input")
        identity_candidates = cart_inspection.get("identity_candidates", [])
        variation_candidates = cart_inspection.get("variation_candidates", [])

        target_checkbox_index = None

        # Preserve the existing identity rule: an item-id match is sufficient
        # when Shopee does not expose the model-id at the same container level.
        for candidate in identity_candidates:
            if candidate.get("item_match"):
                target_checkbox_index = candidate.get("checkbox_index")
                level = candidate.get("level")
                print(
                    "[CheckoutExecutor] Target item identity found at "
                    f"parent level {level}."
                )
                if candidate.get("model_match"):
                    print("[CheckoutExecutor] Target item + model identity matched.")
                else:
                    print(
                        "[CheckoutExecutor] Target item matched; "
                        "model ID not exposed at this level."
                    )
                break

        if target_checkbox_index is None:
            print("[CheckoutExecutor] Stable cart identity not found.")
            print("[CheckoutExecutor] Trying exact variation fallback...")

            exact_variation_candidates = [
                candidate
                for candidate in variation_candidates
                if candidate.get("option_count", 0) > 0
                and len(candidate.get("matched_options", []))
                == candidate.get("option_count")
            ]

            # Deduplicate repeated DOM matches that point to the same checkbox.
            unique_candidates = {}
            for candidate in exact_variation_candidates:
                index = candidate.get("checkbox_index")
                if index is not None:
                    unique_candidates[index] = candidate
            exact_variation_candidates = list(unique_candidates.values())

            print(
                "[CheckoutExecutor] Exact variation candidates: "
                f"{len(exact_variation_candidates)}"
            )

            if len(exact_variation_candidates) == 1:
                candidate = exact_variation_candidates[0]
                target_checkbox_index = candidate["checkbox_index"]
                print(
                    "[CheckoutExecutor] Target cart item resolved using "
                    "exact variation fallback."
                )
            elif len(exact_variation_candidates) > 1:
                print(
                    "[CheckoutExecutor] Cart identity is ambiguous; "
                    "multiple exact variation matches found."
                )
                return False
            else:
                print("[CheckoutExecutor] Exact cart identity could not be verified.")
                print(
                    "[CheckoutExecutor] Checkout aborted safely; "
                    "no cart item was selected."
                )
                return False

        if target_checkbox_index is None:
            print("[CheckoutExecutor] Target product could not be resolved inside the cart.")
            return False

        target_checkbox = checkbox_inputs.nth(int(target_checkbox_index))
        print("[CheckoutExecutor] Target cart item resolved.")
        if target_checkbox is None:
            print("[CheckoutExecutor] Target product could not be resolved inside the cart.")
            return False

        print("[CheckoutExecutor] Target cart item resolved.")
        if hasattr(session, "e1_timing"):
            session.e1_timing.mark("T9")
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
            try:
                actions.wait_for_attribute(
                    target_checkbox,
                    "aria-checked",
                    "true",
                    timeout=500,
                )
            except Exception as e:
                print(
                    "[CheckoutExecutor] Target checkbox state did not settle "
                    f"within the fast-path timeout: {e}"
                )

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
        if hasattr(session, "e1_timing"):
            session.e1_timing.mark("T10")
        checkout_result = actions.click_and_wait_for_url(
            actions.first(checkout_buttons),
            "**/checkout**",
            timeout=15000,
        )
        print("[CheckoutExecutor] Check Out clicked.")
        print(
            "[CheckoutExecutor] Checkout navigation wait: "
            f"{checkout_result}"
        )
        print(f"[CheckoutExecutor] Current URL after checkout: {page.url}")

        if "/checkout" not in page.url:
            print("[CheckoutExecutor] Checkout page was not reached.")
            return False
        if hasattr(session, "e1_timing"):
            session.e1_timing.mark("T11")
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

        place_order = page.get_by_role("button", name="Place Order").first
        if actions.count(place_order) == 0:
            print("[CheckoutExecutor] ARMED: Place Order button is no longer available; action aborted.")
            return False

        async def validate_created_order(_navigation):
            if session.monitored_order_identity_verified:
                return

            print("[CheckoutExecutor] STEP 1: payment continuation reached.")
            print("[CheckoutExecutor] STEP 1: validating monitored product against My Purchase order list...")

            inspector = MonitoredOrderIdentityInspector()
            identity = await inspector.inspect(page, session)
            if identity is None:
                print("[CheckoutExecutor] STEP 1: monitored-to-order identity validation FAILED.")
                return

            session.monitored_order_id = identity.order_id
            session.monitored_checkout_id = identity.checkout_id
            session.monitored_order_identity_verified = True

            print("[CheckoutExecutor] STEP 1: monitored-to-order identity VALIDATED.")
            print(f"[CheckoutExecutor] STEP 1: Order ID {identity.order_id} belongs to the monitored product.")

            if session.successful_purchase_identity_verified:
                return

            print("[CheckoutExecutor] STEP 2: waiting for the validated order to reach To Ship...")
            successful_purchase_inspector = SuccessfulPurchaseIdentityInspector()
            successful_purchase = await successful_purchase_inspector.inspect(page, session)
            if successful_purchase is None:
                print("[CheckoutExecutor] STEP 2: successful-purchase identity validation FAILED or timed out.")
                return

            session.successful_purchase_identity_verified = True
            print("[CheckoutExecutor] STEP 2: successful-purchase identity VALIDATED.")
            print(
                "[CheckoutExecutor] STEP 2: Order ID "
                f"{successful_purchase.order_id} is the monitored product in To Ship."
            )

        post_order_tracker = PostOrderTracker(on_state=validate_created_order)
        post_order_tracker.start(page)

        try:
            actions.click(place_order)
        except Exception as e:
            post_order_tracker.stop()
            print(f"[CheckoutExecutor] ARMED: Place Order click failed: {e}")
            return False

        print("[CheckoutExecutor] ARMED: Place Order clicked.")
        print("[CheckoutExecutor] STEP 7E: Post-order tracking started.")

        post_order_result = post_order_tracker.wait()

        print()
        print("[CheckoutExecutor] ========== STEP 7E RESULT ==========")
        print(
            "[CheckoutExecutor] "
            f"Completion detected: {post_order_result.completed}"
        )
        print(
            "[CheckoutExecutor] "
            f"Tracking timeout: {post_order_result.timed_out}"
        )
        print(
            "[CheckoutExecutor] "
            f"Elapsed: {post_order_result.elapsed_seconds:.2f}s"
        )
        print(
            "[CheckoutExecutor] "
            f"Post-order navigations observed: {len(post_order_result.navigations)}"
        )
        print("[CheckoutExecutor] =========================================")

        if post_order_result.timed_out:
            print(
                "[CheckoutExecutor] STEP 7E: Tracking ended by timeout; "
                "no post-order action was performed by the application."
            )
        elif post_order_result.completed:
            print("[CheckoutExecutor] STEP 7E: Purchase completion state observed.")
        elif post_order_result.stopped:
            print("[CheckoutExecutor] STEP 7E: Tracking was stopped.")

        print("[CheckoutExecutor] Checkout verification complete.")
        return True
