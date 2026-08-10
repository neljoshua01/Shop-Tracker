"""
Coordinates the purchase execution pipeline.

The pipeline prepares the cart, starts SKU monitoring,
waits for the purchase trigger, and hands control to
the next execution stage.
"""

from purchase.models.purchase_session import PurchaseSession
from purchase.execution.cart_preparer import CartPreparer
from purchase.services.sku_price_monitor import SkuPriceMonitor


class PurchasePipeline:

    def __init__(self):

        self.cart_preparer = CartPreparer()
        self.sku_monitor = SkuPriceMonitor()

    def run(
        self,
        session: PurchaseSession,
    ):

        print()
        print(
            "[PurchasePipeline] "
            "========== STARTING PURCHASE PIPELINE =========="
        )

        #
        # 1. Prepare the cart.
        #
        print(
            "[PurchasePipeline] "
            "Preparing cart..."
        )

        self.cart_preparer.prepare(
            session,
        )

        print(
            "[PurchasePipeline] "
            "Cart preparation complete."
        )

        #
        # 2. Start SKU monitoring.
        #
        print()
        print(
            "[PurchasePipeline] "
            "Starting SKU monitor..."
        )

        self.sku_monitor.start(
            session,
        )

        #
        # 3. Wait for the purchase trigger.
        #
        print()
        print(
            "[PurchasePipeline] "
            "Waiting for purchase trigger..."
        )

        try:

            triggered = self.sku_monitor.wait_for_trigger()

            if not triggered:

                print(
                    "[PurchasePipeline] "
                    "Purchase trigger not received."
                )

                return False

            #
            # 4. Trigger received.
            #
            print()
            print(
                "[PurchasePipeline] "
                "========== PURCHASE TRIGGER RECEIVED =========="
            )

            print(
                "[PurchasePipeline] "
                "SKU target reached."
            )

            #
            # Checkout will be connected here later.
            #
            print(
                "[PurchasePipeline] "
                "Ready for checkout."
            )

            return True

        finally:

            #
            # Monitoring stops only after the trigger
            # or if the pipeline exits unexpectedly.
            #
            self.sku_monitor.stop()