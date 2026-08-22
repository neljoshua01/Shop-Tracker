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


class PurchasePipeline:

    def __init__(self):

        self.cart_preparer = CartPreparer()
        self.sku_monitor = SkuPriceMonitor()
        self.checkout_executor = CheckoutExecutor()

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
    ):

        print()
        print(
            "[PurchasePipeline] "
            "========== STARTING PURCHASE PIPELINE =========="
        )

        monitor_thread = None

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

                session.status = PurchaseStatus.FAILED

                return False

            # =================================================
            # 8. CHECKOUT VERIFIED
            # =================================================

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

            print(
                "[PurchasePipeline] "
                "Pipeline finished; browser session preserved."
            )