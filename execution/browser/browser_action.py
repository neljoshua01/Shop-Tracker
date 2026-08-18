"""
High-level browser operations used by the execution layer.
"""

from execution.browser.browser_session import BrowserSession
from core.runtime.async_runtime import AsyncRuntime


class BrowserActions:

    def __init__(
        self,
        session: BrowserSession,
    ):

        self.session = session
        self.runtime = AsyncRuntime.instance()

    def wait_for_selector(
        self,
        selector: str,
        timeout: int = 10000,
    ):

        return self._submit(
            self.session.page.wait_for_selector(
                selector,
                timeout=timeout,
            ),
            timeout=(timeout / 1000) + 5,
        )

    def _submit(
        self,
        coro,
        timeout: float,
    ):

        future = self.runtime.submit(coro)

        return future.result(timeout=timeout)

    def wait_for_timeout(
        self,
        milliseconds: int,
    ):

        return self._submit(
            self.session.page.wait_for_timeout(
                milliseconds,
            ),
            timeout=(milliseconds / 1000) + 5,
        )

    def reload(
        self,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ):

        return self._submit(
            self.session.page.reload(
                wait_until=wait_until,
                timeout=timeout,
            ),
            timeout=(timeout / 1000) + 5,
        )

    def request(
        self,
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        params: dict | None = None,
        timeout: int = 30000,
    ):
        """
        Performs an HTTP request through the existing
        Playwright browser context.

        The request uses the same browser context as the
        current session, preserving the browser's cookies
        and authentication state.

        The visible page is not navigated.
        """

        async def _request():

            response = await self.session.context.request.fetch(
                url,
                method=method,
                headers=headers,
                params=params,
                timeout=timeout,
            )

            return response

        return self._submit(
            _request(),
            timeout=(timeout / 1000) + 5,
        )

    def goto(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ):

        return self._submit(
            self.session.page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout,
            ),
            timeout=(timeout / 1000) + 5,
        )

    def find_all(
        self,
        selector: str,
        parent=None,
    ):

        if parent is None:
            return self.session.page.locator(selector)

        return parent.locator(selector)

    def count(
        self,
        locator,
    ) -> int:

        return self._submit(
            locator.count(),
            timeout=10,
        )

    def text(
        self,
        locator,
    ) -> str:

        return self._submit(
            locator.inner_text(),
            timeout=10,
        ).strip()

    def attribute(
        self,
        locator,
        name: str,
    ) -> str | None:
        return self._submit(
        locator.get_attribute(name),
        timeout=10,
    )

    def click(
        self,
        locator,
    ):

        return self._submit(
            locator.click(),
            timeout=10,
        )

    def force_click(
        self,
        locator,
    ):
        """Click a known interactive control despite transient overlays."""
        return self._submit(
            locator.click(force=True),
            timeout=10,
        )

    def first(
        self,
        locator,
    ):
        return locator.first

    def parent(
        self,
        locator,
    ):
        return locator.locator("..")

    def scroll_to_bottom(
        self,
    ):

        return self._submit(
            self.session.page.evaluate(
                "() => window.scrollTo(0, document.body.scrollHeight)"
            ),
            timeout=10,
        )
