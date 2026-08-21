from execution.browser.browser_connector import BrowserConnector
from services.page_parser import PageParser
from monitoring.services.product_monitor import ProductMonitor
from core.runtime.async_runtime import AsyncRuntime


class MonitorWorker:

    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    IDLE = "IDLE"
    ERROR = "ERROR"

    def __init__(
        self,
        url,
        logger=None,
        on_product_update=None,
        on_event=None,
        on_state_change=None,
        on_error=None,
        initial_product=None,
    ):
        self.runtime = AsyncRuntime.instance()
        self.url = url
        self.logger = logger
        self.on_product_update = on_product_update
        self.on_event = on_event
        self.on_state_change = on_state_change
        self.on_error = on_error
        self.initial_product = initial_product
        self.browser = None
        self.session = None
        self.page = None
        self.parser = None
        self.monitor = None
        self.checkout_handoff = False
        self.state = self.IDLE

    def _set_state(self, state, error=None):
        self.state = state
        if self.on_state_change:
            self.on_state_change(state, error)

    def run(self):
        self._set_state(self.STARTING)
        print("[MonitorWorker] Worker started.")
        try:
            self.browser = BrowserConnector()
            self.browser.connect()
            print("[MonitorWorker] Browser connected.")

            self.session = self.browser.open_session(self, self.url)
            self.page = self.session.page
            print("[MonitorWorker] Monitoring tab ready.")

            self.parser = PageParser(self.page)
            self.monitor = ProductMonitor(
                self.page,
                self.parser,
                logger=self.logger,
                on_product_update=self.on_product_update,
                on_event=self.on_event,
                on_error=self.on_error,
                initial_product=self.initial_product,
                worker=self,
            )
            print("[MonitorWorker] ProductMonitor initialized.")
            self._set_state(self.RUNNING)

            future = self.runtime.submit(self.monitor.start(interval=5))
            future.result()
        except Exception as exc:
            self._set_state(self.ERROR, exc)
            if self.logger:
                self.logger(f"[ERROR] Monitoring worker failed: {exc}")
            if self.on_error:
                self.on_error(exc)
        finally:
            if self.monitor is not None:
                self.monitor.stop()
            if not self.checkout_handoff and self.browser is not None:
                try:
                    self.browser.close_session(self)
                except Exception as exc:
                    if self.logger:
                        self.logger(f"[ERROR] Browser cleanup failed: {exc}")
            if self.state != self.ERROR:
                self._set_state(self.IDLE)

    def set_target(self, target_price, auto_checkout, target_locked):
        if self.monitor:
            self.monitor.set_target(target_price, auto_checkout, target_locked)

    def stop(self):
        self._set_state(self.STOPPING)
        if self.monitor:
            self.monitor.stop()
