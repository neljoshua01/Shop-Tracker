"""
Coordinates the purchase execution pipeline.

The pipeline prepares the cart, starts SKU monitoring,
waits for the purchase trigger, and hands control to
the checkout execution stage.
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
            if session.request.auto_checkout:
                session.status = PurchaseStatus.PREPARING
                print("[PurchasePipeline] Preparing cart...")
                self.cart_preparer.prepare(session)
                print("[PurchasePipeline] Cart preparation complete.")

            print("[PurchasePipeline] Starting SKU monitor...")
            monitor_thread = threading.Thread(
                target=self.sku_monitor.monitor,
                args=(session,),
                kwargs={"poll_interval": session.request.polling_interval},
                daemon=True,
            )
            monitor_thread.start()

            print("[PurchasePipeline] Waiting for purchase trigger...")
            triggered = self.sku_monitor.wait_for_trigger()

            if not triggered:
                print("[PurchasePipeline] Purchase trigger not received.")
                session.status = PurchaseStatus.FAILED
                return False

            print("[PurchasePipeline] ========== PURCHASE TRIGGER RECEIVED ==========")
            if on_trigger:
                on_trigger()

            print("[PurchasePipeline] Stopping SKU monitor...")
            self.sku_monitor.stop()
            monitor_thread.join(timeout=10)

            if not session.request.auto_checkout:
                session.status = PurchaseStatus.COMPLETED
                print("[PurchasePipeline] Trigger recorded; Auto Checkout is disabled.")
                return True

            session.status = PurchaseStatus.CHECKING_OUT
            print("[PurchasePipeline] Starting checkout execution...")
            checkout_success = self.checkout_executor.execute(session)

            if not checkout_success:
                print("[PurchasePipeline] Checkout execution failed.")
                session.status = PurchaseStatus.FAILED
                return False

            session.status = PurchaseStatus.COMPLETED
            print("[PurchasePipeline] Checkout page reached and verified.")
            return True

        except Exception:
            session.status = PurchaseStatus.FAILED
            raise

        finally:
            self.sku_monitor.stop()

            if monitor_thread is not None and monitor_thread.is_alive():
                monitor_thread.join(timeout=10)

            if session.browser_session is not None:
                self.cart_preparer.browser.close_session(session.browser_owner)
                session.browser_session = None
