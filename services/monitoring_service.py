import threading

from services.monitor_worker import MonitorWorker


class MonitoringService:

    def __init__(
        self,
        logger=None,
        on_product_update=None
    ):

        self.logger = logger
        self.on_product_update = on_product_update
        self.worker = None
        self.thread = None

    def start(self, url):

        if self.thread and self.thread.is_alive():
            return

        self.worker = MonitorWorker(
            url=url,
            logger=self.logger,
            on_product_update=self.on_product_update
        )

        self.thread = threading.Thread(
            target=self.worker.run,
            daemon=True
        )
        print("[MonitoringService] Worker created.")
        print("[MonitoringService] Starting worker thread...")
        self.thread.start()
        print("[MonitoringService] Worker thread started.")

    def stop(self):

        if self.worker:
            self.worker.stop()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        self.worker = None
        self.thread = None