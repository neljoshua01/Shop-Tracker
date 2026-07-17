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
        self.workers = {}
        self.threads = {}

    def start(self, url):

        if url in self.threads:

            thread = self.threads[url]

            if thread.is_alive():

                print("[MonitoringService] Product already being monitored.")

                return False

        worker = MonitorWorker(
            url=url,
            logger=self.logger,
            on_product_update=self.on_product_update
        )

        thread = threading.Thread(
            target=worker.run,
            daemon=True
        )
        self.workers[url] = worker
        self.threads[url] = thread
        print("[MonitoringService] Worker created.")
        print("[MonitoringService] Starting worker thread...")
        
        thread.start()
        print("[MonitoringService] Worker thread started.")
        return True

    def stop(self, url):

        if url not in self.workers:
            return False

        worker = self.workers[url]
        thread = self.threads[url]

        worker.stop()

        if thread.is_alive():
            thread.join(timeout=5)

        del self.workers[url]
        del self.threads[url]

        print(f"[MonitoringService] Worker stopped: {url}")

        return True