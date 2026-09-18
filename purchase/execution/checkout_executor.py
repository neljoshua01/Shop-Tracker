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

    def execute(self, session, forensics=None):
        print("[CheckoutExecutor] ========== STARTING CHECKOUT ==========")
        browser_session = session.browser_session
        if browser_session is None:
            print("[CheckoutExecutor] Browser session not available.")
            return False

        page = browser_session.page
        actions = BrowserActions(browser_session)

        print(f"[CheckoutExecutor] Current URL: {page.url}")\n\n        # Phase 1: the executor receives an already initialized checkout.\n        # It never returns to /cart or searches cart DOM state.\n        if "/checkout" not in page.url:\n            print("[CheckoutExecutor] Expected a direct checkout page.")\n            return False\n\n        print("[CheckoutExecutor] Direct checkout page confirmed.")\n        if forensics is not None:\n            forensics.record_event("checkout_page_reached", "checkout",\n                {"url": page.url, "cart_flow_enabled": False})\n\n        checkout_verifier = CheckoutVerifier()\n        initial_summary = AsyncRuntime.instance().submit(\n            checkout_verifier.collect_order_summary(page)\n        ).result(timeout=15)\n        if forensics is not None:\n            forensics.record_event("checkout_price_observed", "checkout", {\n                "observation": "initial",\n                "total": initial_summary.get("total"),\n                "subtotal": initial_summary.get("subtotal"),\n                "item_discount": initial_summary.get("item_discount"),\n                "voucher_discount": initial_summary.get("voucher_discount"),\n            })\n\n        decision = getattr(session, "execution_decision", None)\n        if decision is None:\n            print("[CheckoutExecutor] Execution decision is missing.")\n            return False\n        if decision.item_id != session.product.item_id:\n            print("[CheckoutExecutor] Execution decision item_id mismatch.")\n            return False\n        if decision.model_id != session.variation.model_id:\n            print("[CheckoutExecutor] Execution decision model_id mismatch.")\n            return False\n        if decision.quantity != session.request.quantity:\n            print("[CheckoutExecutor] Execution decision quantity mismatch.")\n            return False\n\n        print(\n            "[CheckoutExecutor] "\n            f"Execution identity verified: item={decision.item_id}, "\n            f"model={decision.model_id}, quantity={decision.quantity}"\n        )\n        requested_payment = session.request.payment_method.value
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

        intermediate_summary = AsyncRuntime.instance().submit(\n            checkout_verifier.collect_order_summary(page)\n        ).result(timeout=15)\n        if forensics is not None:\n            forensics.record_event("checkout_price_observed", "checkout", {\n                "observation": "post_payment_setup",\n                "total": intermediate_summary.get("total"),\n                "subtotal": intermediate_summary.get("subtotal"),\n                "item_discount": intermediate_summary.get("item_discount"),\n                "voucher_discount": intermediate_summary.get("voucher_discount"),\n            })\n            if (\n                initial_summary.get("total") is not None\n                and intermediate_summary.get("total") is not None\n                and initial_summary.get("total") != intermediate_summary.get("total")\n            ):\n                forensics.record_event("checkout_price_changed", "checkout", {\n                    "from_total": initial_summary.get("total"),\n                    "to_total": intermediate_summary.get("total"),\n                })\n        summary = AsyncRuntime.instance().submit(
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
