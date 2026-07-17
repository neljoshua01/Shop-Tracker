import asyncio

from services.comparator import ProductComparator


class ProductMonitor:

    def __init__(self, page, parser, logger=None, on_product_update=None):

        self.page = page
        self.parser = parser
        self.previous = None
        self.comparator = ProductComparator()
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

        if self.running and self.on_product_update:
            self.on_product_update(product)

        if self.previous is None:

            self.log("First snapshot saved.")
            self.log(f"Product: {product.name}")
            self.log(f"Price : {product.current_price}")
            self.log(f"Stock : {product.stock}")

            self.previous = product
            return

        events = self.comparator.compare(
            self.previous,
            product
        )

        if events:

            print("\n" + "=" * 60)
            print("CHANGES DETECTED")
            print("=" * 60)

            for event in events:

                self.log(
                    f"{event.field}: {event.old_value} → {event.new_value}"
            )
        else:

            self.log("No changes detected.")

        self.previous = product

    async def start(self, interval=10):
        print("[ProductMonitor] Monitoring started.")
        while self.running:

            try:

                await self.check()

            except Exception as e:

                self.log(f"[ERROR] Monitoring failed: {e}")

            await asyncio.sleep(interval)

    def stop(self):

        self.running = False

    def log(self, message):

        if self.logger:
            self.logger(message)
        else:
            print(message)