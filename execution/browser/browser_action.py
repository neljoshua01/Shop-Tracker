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

    def evaluate(
        self,
        expression: str,
        arg=None,
        timeout: int = 10000,
    ):
        """Evaluate JavaScript in the active page through the runtime."""
        return self._submit(
            self.session.page.evaluate(expression, arg),
            timeout=(timeout / 1000) + 5,
        )

    def wait_for_url(
        self,
        url: str,
        timeout: int = 10000,
    ):
        """Wait for the active page to reach a URL pattern."""
        return self._submit(
            self.session.page.wait_for_url(
                url,
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

    def click_visible_button_by_labels(
        self,
        labels: list[str],
        timeout: int = 10000,
    ):
        """
        Find a visible purchase control by rendered text and perform a real
        Playwright click.

        Shopee can render the PDP CTA as either a <button> or an element with
        role="button". Discovery therefore covers both forms. The final
        interaction remains Playwright locator.click(force=True), which lets
        Playwright perform the browser-level click even when a transient
        overlay overlaps the control.

        The method deliberately does not remove page elements or dispatch
        Element.click() from page JavaScript.
        """

        normalized_labels = tuple(
            " ".join(str(label).strip().lower().split())
            for label in labels
            if str(label).strip()
        )

        async def _click():
            controls = self.session.page.locator(
                "button, [role='button']"
            )
            count = await controls.count()

            candidates = []

            for index in range(count):
                control = controls.nth(index)

                if not await control.is_visible():
                    continue

                text = (await control.inner_text()).strip()
                normalized_text = " ".join(text.lower().split())

                if not normalized_text:
                    continue

                if not any(
                    label == normalized_text
                    or label in normalized_text
                    for label in normalized_labels
                ):
                    continue

                disabled = await control.get_attribute("disabled")
                aria_disabled = await control.get_attribute("aria-disabled")

                if disabled is not None or aria_disabled == "true":
                    continue

                candidates.append((index, control, text))

            if not candidates:
                return {
                    "found": False,
                    "clicked": False,
                    "reason": (
                        "No visible enabled button/role=button matched "
                        "the requested labels."
                    ),
                }

            index, control, text = candidates[-1]

            await control.scroll_into_view_if_needed()
            await control.click(force=True, timeout=3000)

            return {
                "found": True,
                "clicked": True,
                "index": index,
                "text": text,
                "tag": await control.evaluate("el => el.tagName"),
                "role": await control.get_attribute("role"),
                "forced": True,
            }

        return self._submit(
            _click(),
            timeout=(timeout / 1000) + 5,
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

    def scroll_into_view(
        self,
        locator,
    ):
        """Ensure a known interactive control is in the viewport."""
        return self._submit(
            locator.scroll_into_view_if_needed(),
            timeout=10,
        )

    def dom_click(
        self,
        locator,
    ):
        """Dispatch the element's native DOM click handler."""
        return self._submit(
            locator.evaluate("el => el.click()"),
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
