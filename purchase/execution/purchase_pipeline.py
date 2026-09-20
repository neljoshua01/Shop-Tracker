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
from purchase.execution.cart_preparer import CartPreparer
from purchase.execution.checkout_executor import CheckoutExecutor
from purchase.services.sku_price_monitor import SkuPriceMonitor
from purchase.services.promotion_forensics import PromotionForensicsRecorder
from purchase.models.trigger_condition import TriggerCondition


class PurchasePipeline:

    def __init__(self):

        self.cart_preparer = CartPreparer()
        self.sku_monitor = SkuPriceMonitor()
        self.checkout_executor = CheckoutExecutor()

        self._cancelled = threading.Event()
        self._forensics = None
        self._forensic_observer_stop_requested = False

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

        # Manual monitoring stop must also stop the independent promotional
        # observer so its final observation summary is persisted before the
        # normal forensic recorder is finalized. Trigger-driven cancellation
        # does not use this method, so a successful trigger can still keep
        # observing the promotion lifecycle through LIVE -> ENDED.
        if self._forensics is not None:
            try:
                if self._forensics.session.request.trigger is TriggerCondition.PROMOTIONAL_PRICE_TARGET:
                    self._forensic_observer_stop_requested = True
                    self._forensics.stop_promotion_observation()
            except Exception as e:
                print(
                    "[PurchasePipeline] "
                    f"Forensic observer stop warning: {e}"
                )

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
    ):

        print()
        print(
            "[PurchasePipeline] "
            "========== STARTING PURCHASE PIPELINE =========="
        )

        monitor_thread = None
        forensics = PromotionForensicsRecorder.start(session)
        self._forensics = forensics

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

            # The independent promotional observer must start for every
            # promotional-price experiment, not only after a deep-discount
            # signal is seen in the purchase monitor. This guarantees forensic
            # coverage for all three required outcomes:
            #   - LIVE -> no trigger
            #   - no LIVE event -> manual stop
            #   - LIVE -> transactional trigger
            if session.request.trigger is TriggerCondition.PROMOTIONAL_PRICE_TARGET:
                forensics.start_promotion_observation()
                forensics.record_event(
                    "promotion_observation_started_for_experiment",
                    "post_trigger_observation",
                    {
                        "reason": "promotional_price_experiment_started",
                    },
                )

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

            forensics.record_event(
                "purchase_trigger_received",
                "trigger",
                {
                    "item_id": session.monitored_item_id,
                    "model_id": session.monitored_model_id,
                    "sku_identity_verified": session.monitored_sku_identity_verified,
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

            if hasattr(session, "e1_timing"):
                session.e1_timing.mark("T8")

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
            try:
                e1_path = forensics.run_dir / "e1_timing.json"
                e1_result = session.e1_timing.finalize(e1_path)
                print(
                    "[PurchasePipeline] E1 timing metrics: "
                    f"{e1_result['metrics_ms']}"
                )
            except Exception as e:
                print(
                    "[PurchasePipeline] "
                    f"E1 timing finalization warning: {e}"
                )

            if session.request.trigger is TriggerCondition.PROMOTIONAL_PRICE_TARGET:
                print(
                    "[PurchasePipeline] "
                    "Waiting for independent promotion forensic observation to finish..."
                )
                observation_timeout = 20 if self._forensic_observer_stop_requested else 135
                completed = forensics.wait_for_promotion_observation(
                    timeout=observation_timeout
                )
                print(
                    "[PurchasePipeline] "
                    "Independent promotion observation finished: "
                    f"{completed}"
                )

            PromotionForensicsRecorder.stop(session)
            self._forensics = None
            self._forensic_observer_stop_requested = False

            print(
                "[PurchasePipeline] "
                "Pipeline finished; browser session preserved."
            )