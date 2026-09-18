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

    def capture_pdp_purchase_controls(
        self,
        labels: list[str],
        timeout: int = 10000,
    ):
        """
        Capture the rendered PDP purchase-control DOM immediately before
        purchase interaction.

        This is diagnostic-only. It does not click, remove, or mutate any
        page element.
        """

        normalized_labels = tuple(
            " ".join(str(label).strip().lower().split())
            for label in labels
            if str(label).strip()
        )

        async def _capture():
            elements = await self.session.page.locator(
                "button, [role='button'], a"
            ).all()

            snapshot = []

            for element in elements:
                text = (await element.inner_text()).strip()

                if not text:
                    continue

                normalized_text = " ".join(text.lower().split())

                if not any(
                    label in normalized_text
                    for label in normalized_labels
                ):
                    continue

                rect = await element.evaluate(
                    """el => {
                        const r = el.getBoundingClientRect();
                        return {
                            x: r.x,
                            y: r.y,
                            width: r.width,
                            height: r.height
                        };
                    }"""
                )

                snapshot.append({
                    "tag": await element.evaluate("el => el.tagName"),
                    "text": text[:80],
                    "cls": (
                        await element.get_attribute("class")
                    ) or "",
                    "disabled": await element.get_attribute("disabled"),
                    "aria_disabled": await element.get_attribute(
                        "aria-disabled"
                    ),
                    "visible": await element.is_visible(),
                    "enabled": await element.is_enabled(),
                    "rect": rect,
                })

            return snapshot

        return self._submit(
            _capture(),
            timeout=(timeout / 1000) + 5,
        )

    def click_visible_button_by_labels(
        self,
        labels: list[str],
        timeout: int = 10000,
    ):
        """
        Locate a PDP purchase CTA using the rendered page and perform a real
        Playwright click.

        Shopee may render the CTA as a <button>, [role=button], or as text
        inside another clickable container. Discovery therefore uses two
        Playwright strategies:

        1. enumerate interactive controls;
        2. fall back to exact rendered text.

        The final interaction is always locator.click(force=True). No
        page-context Element.click() or DOM removal is used.
        """

        normalized_labels = tuple(
            " ".join(str(label).strip().lower().split())
            for label in labels
            if str(label).strip()
        )

        async def _click():
            navigations = []

            def _record_navigation(frame):
                if frame == self.session.page.main_frame:
                    navigations.append(frame.url)

            self.session.page.on("framenavigated", _record_navigation)

            # The PDP purchase controls can be below the current viewport and
            # can be lazily materialized. Move to the purchase area before
            # deciding that the control does not exist.
            await self.session.page.evaluate(
                "() => window.scrollTo(0, document.body.scrollHeight)"
            )
            await self.session.page.wait_for_timeout(500)

            controls = self.session.page.locator(
                "button, [role='button'], a"
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

            if candidates:
                # Prefer the last matching rendered control. Sticky purchase
                # controls are commonly appended after the main PDP controls.
                index, control, text = candidates[-1]

                await control.scroll_into_view_if_needed()
                await control.click(force=True, timeout=3000)

                try:
                    await page_wait_for_click_settle(self.session.page)
                finally:
                    self.session.page.remove_listener(
                        "framenavigated",
                        _record_navigation,
                    )

                return {
                    "found": True,
                    "clicked": True,
                    "strategy": "interactive_control",
                    "index": index,
                    "text": text,
                    "tag": await control.evaluate("el => el.tagName"),
                    "role": await control.get_attribute("role"),
                    "forced": True,
                    "navigations": list(navigations),
                }

            # Fallback: the visible CTA text may be inside a non-button
            # clickable container. Exact text discovery is still a native
            # Playwright locator action.
            for label in normalized_labels:
                text_locator = self.session.page.get_by_text(
                    label,
                    exact=True,
                )

                text_count = await text_locator.count()

                for index in range(text_count):
                    target = text_locator.nth(index)

                    if not await target.is_visible():
                        continue

                    await target.scroll_into_view_if_needed()
                    await target.click(force=True, timeout=3000)

                    try:
                        await page_wait_for_click_settle(self.session.page)
                    finally:
                        self.session.page.remove_listener(
                            "framenavigated",
                            _record_navigation,
                        )

                    return {
                        "found": True,
                        "clicked": True,
                        "strategy": "exact_rendered_text",
                        "index": index,
                        "text": await target.inner_text(),
                        "forced": True,
                        "navigations": list(navigations),
                    }

            self.session.page.remove_listener(
                "framenavigated",
                _record_navigation,
            )

            return {
                "found": False,
                "clicked": False,
                "reason": (
                    "No visible Buy Now control or exact rendered CTA text "
                    "was found."
                ),
                "navigations": list(navigations),
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


async def page_wait_for_click_settle(page):
    """Allow immediate redirect chains to emit their navigation events."""
    await page.wait_for_timeout(750)
