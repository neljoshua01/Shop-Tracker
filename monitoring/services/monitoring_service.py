import threading

from monitoring.services.monitor_worker import MonitorWorker


class MonitoringService:

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"

    def __init__(
        self,
        logger=None,
        on_product_update=None,
        on_event=None,
        on_state_change=None,
        on_error=None,
    ):
        self.logger = logger
        self.on_product_update = on_product_update
        self.on_event = on_event
        self.on_state_change = on_state_change
        self.on_error = on_error
        self.workers = {}
        self.threads = {}
        self.worker_states = {}
        self.state = self.IDLE

    def _set_state(self, state, url=None, error=None):
        self.worker_states[url] = state if url else self.state
        if url:
            other_active = any(
                worker_url != url and value in (self.STARTING, self.RUNNING, self.STOPPING)
                for worker_url, value in self.worker_states.items()
            )
            if state == self.ERROR:
                aggregate = self.RUNNING if other_active else self.ERROR
            elif state == self.STOPPING:
                aggregate = self.RUNNING if other_active else self.STOPPING
            else:
                active = [
                    value
                    for value in self.worker_states.values()
                    if value in (self.STARTING, self.RUNNING, self.STOPPING)
                ]
                aggregate = (
                    self.RUNNING
                    if any(value == self.RUNNING for value in active)
                    else self.STARTING
                    if active
                    else self.IDLE
                )
        else:
            aggregate = state
        if aggregate != self.state:
            self.state = aggregate
            if self.on_state_change:
                self.on_state_change(self.state, url, error)

    def _worker_state_changed(self, url, state, error=None):
        self.worker_states[url] = state
        self._set_state(state, url=url, error=error)

    def _worker_event(self, url, event, product=None):
        if self.on_event:
            self.on_event(url, event, product)

    def _worker_error(self, url, error):
        if self.on_error:
            self.on_error(url, error)

    def start(self, url, initial_product=None):
        if url in self.threads:
            thread = self.threads[url]
            if thread.is_alive():
                print("[MonitoringService] Product already being monitored.")
                return False

        self._set_state(self.STARTING, url=url)

        worker = MonitorWorker(
            url=url,
            logger=self.logger,
            on_product_update=self.on_product_update,
            on_event=lambda event, product=None: self._worker_event(url, event, product),
            on_state_change=lambda state, error=None: self._worker_state_changed(url, state, error),
            on_error=lambda error: self._worker_error(url, error),
            initial_product=initial_product,
        )

        thread = threading.Thread(
            target=worker.run,
            daemon=True,
            name=f"MonitorWorker:{url}",
        )
        self.workers[url] = worker
        self.threads[url] = thread
        self.worker_states[url] = self.STARTING
        print("[MonitoringService] Worker created.")
        print("[MonitoringService] Starting worker thread...")

        thread.start()
        print("[MonitoringService] Worker thread started.")
        return True

    def set_target(self, url, target_price, auto_checkout, target_locked):
        worker = self.workers.get(url)
        if worker:
            worker.set_target(target_price, auto_checkout, target_locked)

    def stop(self, url):
        if url not in self.workers:
            return False

        self._set_state(self.STOPPING, url=url)
        worker = self.workers[url]
        thread = self.threads[url]
        worker.stop()

        if thread.is_alive():
            thread.join(timeout=5)

        del self.workers[url]
        del self.threads[url]
        self.worker_states.pop(url, None)

        self.state = self.RUNNING if self.threads else self.IDLE
        if self.on_state_change:
            self.on_state_change(self.state, url, None)

        print(f"[MonitoringService] Worker stopped: {url}")
        return True
