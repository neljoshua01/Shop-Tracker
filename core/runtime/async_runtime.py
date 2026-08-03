import asyncio
import threading


class AsyncRuntime:
    """
    Owns the application's asyncio event loop.

    Everything asynchronous (monitoring, checkout,
    notifications) will eventually run here.
    """

    _instance = None

    def __init__(self):
        self.loop = asyncio.new_event_loop()

        self.thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="AsyncRuntime"
        )

        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    @classmethod
    def instance(cls):

        if cls._instance is None:
            cls._instance = cls()

        return cls._instance

    def submit(self, coro):
        """
        Schedule a coroutine onto the runtime.
        """
        return asyncio.run_coroutine_threadsafe(
            coro,
            self.loop
        )