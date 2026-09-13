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


class PurchasePipeline:

    def __init__(self):
        self.cart_preparer = CartPreparer()
        self.sku_monitor = SkuPriceMonitor()
        self.checkout_executor = CheckoutExecutor()
        self._cancelled = threading.Event()

    def stop(self):
        self._cancelled.set()
        try:
            self.sku_monitor.stop()
        except Exception as e:
            print("[PurchasePipeline] Monitor stop warning: " f"{e}")

    def run(self, session: PurchaseSession, on_trigger=None):
        print()
        print("[PurchasePipeline] ========== STARTING PURCHASE PIPELINE ==========")

        monitor_thread = None
        forensics = None

        try:
            if self._cancelled.is_set():
                print("[PurchasePipeline] Pipeline already cancelled.")
                return False

            # Start the forensic run before purchase work. It attaches as soon
            # as the browser session exists and remains active through the
            # promotional monitor and any cart/checkout transition.
            forensics = PromotionForensicsRecorder.start(session)
            forensics.record_event("pipeline_started", "pipeline", {
                "status": session.status.value if hasattr(session.status, "value") else str(session.status),
            })

            # =================================================
            # 1. PREPARE CART
            # =================================================
            session.status = PurchaseStatus.PREPARING
            print("[PurchasePipeline] Preparing cart...")
            self.cart_preparer.prepare(session)

            if session.browser_session is not None:
                forensics.attach_engine(self.sku_monitor.browser.engine, session.browser_session)
                forensics.record_event("cart_prepared", "cart", {
                    "page_url": session.browser_session.page.url,
                    "item_id": session.product.item_id,
                    "model_id": session.variation.model_id,
                })
                forensics.record_phase("cart_prepared", session.browser_session.page)

            print("[PurchasePipeline] Cart preparation complete.")

            # =================================================
            # 2. START SKU MONITOR
            # =================================================
            print("[PurchasePipeline] Starting SKU monitor...")
            forensics.record_event("monitor_starting", "monitoring", {
                "poll_interval": session.request.polling_interval,
            })

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

            print("[PurchasePipeline] Waiting for purchase trigger...")
            triggered = self.sku_monitor.wait_for_trigger(cancellation_event=self._cancelled)

            if not triggered:
                if self._cancelled.is_set():
                    forensics.record_event("pipeline_cancelled", "monitoring")
                    print("[PurchasePipeline] Pipeline cancelled.")
                    return False
                forensics.record_event("trigger_not_received", "monitoring")
                print("[PurchasePipeline] Purchase trigger not received.")
                session.status = PurchaseStatus.FAILED
                return False

            # =================================================
            # 3. TRIGGER RECEIVED
            # =================================================
            print()
            print("[PurchasePipeline] ========== PURCHASE TRIGGER RECEIVED ==========")
            latest = self.sku_monitor.latest_state
            forensics.record_event("purchase_triggered", "event", {
                "item_id": latest.item_id if latest else session.product.item_id,
                "model_id": latest.model_id if latest else session.variation.model_id,
                "sku": latest.name if latest else session.variation.name,
                "price": latest.price if latest else None,
                "price_before_discount": latest.price_before_discount if latest else None,
                "promotion_id": latest.promotion_id if latest else None,
                "promotion_types": latest.promotion_types if latest else None,
                "deep_discount": latest.deep_discount if latest else None,
                "promotion_price": latest.promotion_price if latest else None,
                "promotion_event_status": latest.promotion_event_status if latest else None,
                "promotion_seconds_until_start": latest.promotion_seconds_until_start if latest else None,
                "promotion_seconds_until_end": latest.promotion_seconds_until_end if latest else None,
                "promotion_is_lpp": latest.promotion_is_lpp if latest else None,
            })

            if on_trigger:
                on_trigger()

            # =================================================
            # 4. STOP MONITORING
            # =================================================
            print("[PurchasePipeline] Stopping SKU monitor...")
            self.sku_monitor.stop()
            self._cancelled.set()

            if monitor_thread is not None and monitor_thread.is_alive():
                monitor_thread.join(timeout=10)

            if not session.request.auto_checkout:
                print()
                print("[PurchasePipeline] Auto Checkout is OFF.")
                print("[PurchasePipeline] Trigger recorded.")
                print("[PurchasePipeline] Prepared cart will remain available.")
                forensics.record_event("trigger_recorded_cart_preserved", "post_trigger", {
                    "page_url": session.browser_session.page.url if session.browser_session else None,
                })
                if session.browser_session is not None:
                    forensics.record_phase("post_trigger_cart", session.browser_session.page)
                return True

            # =================================================
            # 5. AUTO CHECKOUT ON
            # =================================================
            print()
            print("[PurchasePipeline] Auto Checkout is ON.")
            print("[PurchasePipeline] Starting checkout execution...")
            forensics.record_event("checkout_starting", "checkout")
            session.status = PurchaseStatus.CHECKING_OUT

            checkout_success = self.checkout_executor.execute(session)

            # Preserve the checkout page even when verification fails. This is
            # one of the most useful artifacts for diagnosing price, identity,
            # payment, protection, and Place Order failures.
            if session.browser_session is not None:
                forensics.record_phase("checkout_result", session.browser_session.page)
                forensics.record_event("checkout_execution_returned", "checkout", {
                    "success": checkout_success,
                    "page_url": session.browser_session.page.url,
                })

            if not checkout_success:
                forensics.record_event("checkout_failed", "checkout")
                print("[PurchasePipeline] Checkout execution failed.")
                session.status = PurchaseStatus.FAILED
                return False

            session.status = PurchaseStatus.COMPLETED
            forensics.record_event("checkout_verified", "checkout", {
                "page_url": session.browser_session.page.url if session.browser_session else None,
            })
            print()
            print("[PurchasePipeline] Checkout page reached and verified.")
            print("[PurchasePipeline] Place Order detected.")
            return True

        except Exception as e:
            if forensics is not None:
                forensics.record_event("pipeline_exception", "error", {"error": repr(e)})
            session.status = PurchaseStatus.FAILED
            raise

        finally:
            try:
                self.sku_monitor.stop()
            except Exception as e:
                print("[PurchasePipeline] Final monitor stop warning: " f"{e}")

            if monitor_thread is not None and monitor_thread.is_alive():
                monitor_thread.join(timeout=10)

            if forensics is not None:
                forensics.record_event("pipeline_finished", "final", {
                    "status": session.status.value if hasattr(session.status, "value") else str(session.status),
                    "page_url": session.browser_session.page.url if session.browser_session else None,
                })
                PromotionForensicsRecorder.stop(session)

            print("[PurchasePipeline] Pipeline finished; browser session preserved.")
