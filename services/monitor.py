import asyncio

from services.comparator import ProductComparator
from services.checkout_engine import CheckoutEngine


class ProductMonitor:

    def __init__(self, page, parser, logger=None, on_product_update=None, initial_product=None, worker=None):

        self.page = page
        self.parser = parser
        self.previous = initial_product
        self.comparator = ProductComparator()
        self.checkout_engine = CheckoutEngine()
        self.checkout_started = False
        self.worker = worker
        self.logger = logger
        self.on_product_update = on_product_update
        self.running = True
        
    async def check(self):
        print("[ProductMonitor] Refresh cycle.")
        self.log("Refreshing Shopee page...")
        await self.page.reload(
            wait_until="domcontentloaded"
        )

        self.log("Parsing latest product data...")
        product = await self.parser.parse()

        print("[ProductMonitor] Product parsed.")

        #
        # Preserve user settings across refreshes
        #

        if self.previous is not None:

            product.auto_checkout = self.previous.auto_checkout
            product.target_price = self.previous.target_price
            product.target_locked = self.previous.target_locked
            product.purchased = self.previous.purchased or product.purchased

        if self.previous is None:

            self.log("First snapshot saved.")
            self.log(f"Product: {product.name}")
            self.log(f"Price : {product.current_price}")
            self.log(f"Stock : {product.stock}")

            if self.running and self.on_product_update:
                self.on_product_update(product)

            self.previous = product
            return
        
        events = self.comparator.compare(
            self.previous,
            product
        )

        #
        # Evaluate checkout once
        #

        should_checkout = self.checkout_engine.should_checkout(product)

        if should_checkout:

            self.log("⚡ AUTO CHECKOUT CONDITIONS MET")
            self.log("Checkout condition met.")

            self.checkout_started = True
            if self.worker:
                self.worker.checkout_handoff = True
                
            self.stop()
            await self.checkout_engine.buy(
                product,
                self.page
            )

            #
            # CheckoutEngine now owns the page.
            #

            if self.on_product_update:
                self.on_product_update(product)

            return

        #
        # Continue monitoring normally
        #

        self.previous = product

    async def start(self, interval=10):
        print("[ProductMonitor] Monitoring started.")
        while self.running:

            try:

                await self.check()

            except Exception as e:

                self.log(f"[ERROR] Monitoring failed: {e}")

            await asyncio.sleep(interval)

    def set_target(
        self,
        target_price,
        auto_checkout,
        target_locked
    ):

        #
        # First snapshot hasn't happened yet.
        #

        if self.previous is None:
            return

        self.previous.target_price = target_price
        self.previous.auto_checkout = auto_checkout
        self.previous.target_locked = target_locked

    def stop(self):

        self.running = False

    def log(self, message):

        if self.logger:
            self.logger(message)
        else:
            print(message)