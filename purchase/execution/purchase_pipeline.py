"""
Coordinates the purchase execution pipeline.

The pipeline always prepares the requested product in the Shopee cart,
then monitors the selected SKU.

Auto Checkout only changes what happens AFTER a purchase trigger:

    Auto Checkout OFF:
        Trigger is recorded and monitoring stops.
        The prepared cart/session remains available.

    Auto Checkout ON:
        Trigger stops monitoring and starts CheckoutExecutor.
        CheckoutExecutor proceeds only up to Place Order detection.
"""

import threading

from purchase.models.purchase_session import PurchaseSession
from purchase.models.purchase_status import PurchaseStatus
from purchase.models.ime_state import IMEState
from purchase.models.execution_decision import ExecutionDecision
from purchase.execution.cart_preparer import CartPreparer
from purchase.execution.checkout_executor import CheckoutExecutor
from purchase.services.sku_price_monitor import SkuPriceMonitor
from purchase.services.promotion_forensics import PromotionForensicsRecorder


class PurchasePipeline:

    def __init__(self):

        self.cart_preparer = CartPreparer()
        self.sku_monitor = SkuPriceMonitor()
        self.checkout_executor = CheckoutExecutor()
        self.execution_decision: ExecutionDecision | None = None

        self._cancelled = threading.Event()

    # =====================================================
    # STOP
    # =====================================================

    def stop(self):
        """
        Stop the SKU monitor.

        IMPORTANT:
        This does NOT close the purchase browser session.

        The prepared cart belongs to the purchase session and must
        remain available after monitoring stops.
        """

        self._cancelled.set()

        try:
            self.sku_monitor.stop()

        except Exception as e:

            print(
                "[PurchasePipeline] "
                f"Monitor stop warning: {e}"
            )

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        session: PurchaseSession,
        on_trigger=None,
        ime_state: IMEState | None = None,
    ):

        print()
        print(
            "[PurchasePipeline] "
            "========== STARTING PURCHASE PIPELINE =========="
        )

        monitor_thread = None
        self.execution_decision = None
        session.execution_decision = None
        forensics = PromotionForensicsRecorder.start(session)

        # Register the forensic callback before opening/preparing the browser
        # session. BrowserEngine will bind the owner callback to the newly
        # created BrowserSession, allowing capture of the complete
        # PDP -> Add-to-Cart -> Cart -> Checkout response sequence.
        forensics.attach_engine(self.cart_preparer.browser.engine)
        forensics.record_event("pipeline_started", "startup")

        try:

            if self._cancelled.is_set():

                print(
                    "[PurchasePipeline] "
                    "Pipeline already cancelled."
                )

                return False

            # =================================================
            # 1. PREPARE CART
            # =================================================

            session.status = PurchaseStatus.PREPARING
            forensics.record_event("cart_preparation_started", "cart")

            print(
                "[PurchasePipeline] "
                "Preparing cart..."
            )

            #
            # IMPORTANT:
            #
            # Cart preparation ALWAYS happens regardless of
            # Auto Checkout.
            #
            self.cart_preparer.prepare(session)

            if session.browser_session is not None:
                forensics.bind_session(session.browser_session)
                forensics.record_phase(
                    "cart_prepared",
                    session.browser_session.page,
                )

            forensics.record_event(
                "cart_preparation_completed",
                "cart",
                {
                    "item_id": session.product.item_id,
                    "model_id": session.variation.model_id,
                    "sku": ",".join(str(v) for v in session.request.options.values()),
                    "quantity": session.request.quantity,
                },
            )

            print(
                "[PurchasePipeline] "
                "Cart preparation complete."
            )

            # =================================================
            # 2. START SKU MONITOR
            # =================================================

            print(
                "[PurchasePipeline] "
                "Starting SKU monitor..."
            )

            forensics.record_event("sku_monitor_started", "pdp")

            monitor_thread = threading.Thread(
                target=self.sku_monitor.monitor,
                args=(session,),
                kwargs={
                    "poll_interval": session.request.polling_interval,
                    "cancellation_event": self._cancelled,
                },
                daemon=True,
            )

            monitor_thread.start()

            # =================================================
            # 3. WAIT FOR TRIGGER
            # =================================================

            print(
                "[PurchasePipeline] "
                "Waiting for purchase trigger..."
            )

            triggered = self.sku_monitor.wait_for_trigger(
                cancellation_event=self._cancelled,
            )

            if not triggered:

                if self._cancelled.is_set():

                    print(
                        "[PurchasePipeline] "
                        "Pipeline cancelled."
                    )

                    return False

                print(
                    "[PurchasePipeline] "
                    "Purchase trigger not received."
                )

                session.status = PurchaseStatus.FAILED

                return False

            # =================================================
            # 4. TRIGGER RECEIVED
            # =================================================

            print()
            print(
                "[PurchasePipeline] "
                "========== PURCHASE TRIGGER RECEIVED =========="
            )

            current_ime_state = ime_state or session.ime_state
            latest_state = self.sku_monitor.latest_state

            if current_ime_state is not IMEState.EXECUTION_READY:
                print(
                    "[PurchasePipeline] "
                    f"IME state is {current_ime_state}; execution is not ready."
                )
                return False

            if latest_state is None:
                print(
                    "[PurchasePipeline] "
                    "No latest SKU state is available for execution decision."
                )
                return False

            self.execution_decision = ExecutionDecision(
                item_id=latest_state.item_id,
                model_id=latest_state.model_id,
                promotion_id=latest_state.promotion_id,
                target_price=session.request.target_price,
                execution_state=current_ime_state,
            )
            session.execution_decision = self.execution_decision

            forensics.record_event(
                "purchase_trigger_received",
                "trigger",
                {
                    "item_id": session.monitored_item_id,
                    "model_id": session.monitored_model_id,
                    "sku_identity_verified": session.monitored_sku_identity_verified,
                    "ime_state": current_ime_state.value,
                    "execution_decision": {
                        "item_id": self.execution_decision.item_id,
                        "model_id": self.execution_decision.model_id,
                        "promotion_id": self.execution_decision.promotion_id,
                        "target_price": self.execution_decision.target_price,
                        "execution_state": self.execution_decision.execution_state.value,
                    },
                },
            )

            if on_trigger:

                on_trigger()

            # =================================================
            # 5. STOP MONITORING
            # =================================================

            print(
                "[PurchasePipeline] "
                "Stopping SKU monitor..."
            )

            self.sku_monitor.stop()

            #
            # Wake the pipeline if it is waiting.
            #
            self._cancelled.set()

            if (
                monitor_thread is not None
                and monitor_thread.is_alive()
            ):

                monitor_thread.join(
                    timeout=10,
                )

            # =================================================
            # 6. AUTO CHECKOUT OFF
            # =================================================

            if not session.request.auto_checkout:

                print()
                print(
                    "[PurchasePipeline] "
                    "Auto Checkout is OFF."
                )

                print(
                    "[PurchasePipeline] "
                    "Trigger recorded."
                )

                print(
                    "[PurchasePipeline] "
                    "Prepared cart will remain available."
                )

                #
                # IMPORTANT:
                #
                # Do NOT close the browser session here.
                #
                # Do NOT remove the prepared cart.
                #
                # The cart is intentionally left visible for
                # monitoring/manual action.
                #

                return True

            # =================================================
            # 7. AUTO CHECKOUT ON
            # =================================================

            print()
            print(
                "[PurchasePipeline] "
                "Auto Checkout is ON."
            )

            print(
                "[PurchasePipeline] "
                "Starting checkout execution..."
            )

            forensics.record_event("checkout_execution_started", "cart")

            session.status = PurchaseStatus.CHECKING_OUT

            checkout_success = (
                self.checkout_executor.execute(
                    session,
                )
            )

            if not checkout_success:

                print(
                    "[PurchasePipeline] "
                    "Checkout execution failed."
                )

                forensics.record_event(
                    "checkout_execution_failed",
                    "checkout",
                )
                session.status = PurchaseStatus.FAILED

                return False

            # =================================================
            # 8. CHECKOUT VERIFIED
            # =================================================

            forensics.record_event(
                "checkout_execution_completed",
                "checkout",
                {
                    "item_id": session.product.item_id,
                    "model_id": session.variation.model_id,
                },
            )

            session.status = PurchaseStatus.COMPLETED

            print()
            print(
                "[PurchasePipeline] "
                "Checkout page reached and verified."
            )

            print(
                "[PurchasePipeline] "
                "Place Order detected."
            )

            #
            # CheckoutExecutor intentionally stops here.
            # It does NOT click Place Order.
            #

            return True

        except Exception:

            session.status = PurchaseStatus.FAILED

            raise

        finally:

            #
            # Always stop monitoring.
            #
            try:

                self.sku_monitor.stop()

            except Exception as e:

                print(
                    "[PurchasePipeline] "
                    f"Final monitor stop warning: {e}"
                )

            #
            # Give the monitor thread time to finish.
            #
            if (
                monitor_thread is not None
                and monitor_thread.is_alive()
            ):

                monitor_thread.join(
                    timeout=10,
                )

            #
            # IMPORTANT:
            #
            # DO NOT close session.browser_session here.
            #
            # The browser session owns the prepared cart.
            #
            # Closing it here was the reason the cart/profile
            # disappeared after the pipeline completed.
            #
            # Session cleanup should be handled by the higher-level
            # purchase-profile lifecycle, not by this pipeline.
            #

            # Record the terminal pipeline lifecycle event before finalizing
            # the recorder. This covers normal exits such as a safe checkout
            # stop when the live promotional price is no longer available.
            try:
                forensics.record_event(
                    "pipeline_finished",
                    "final",
                    {
                        "status": getattr(session.status, "value", str(session.status)),
                        "browser_session_preserved": session.browser_session is not None,
                    },
                )
            except Exception as e:
                print(
                    "[PurchasePipeline] "
                    f"Forensics terminal event warning: {e}"
                )

            # Finalize forensic capture on every normal pipeline exit.
            # The recorder isolates cleanup failures so they cannot suppress
            # final_summary.json.
            PromotionForensicsRecorder.stop(session)

            print(
                "[PurchasePipeline] "
                "Pipeline finished; browser session preserved."
            )