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

    def click_and_wait_for_url(
        self,
        locator,
        url_pattern: str,
        timeout: int = 10000,
    ):
        """Click a control while waiting for a matching navigation."""

        async def _click_and_wait():
            waiter = self.session.page.wait_for_url(
                url_pattern,
                timeout=timeout,
            )
            try:
                await locator.click()
                await waiter
                return True
            except Exception:
                try:
                    await waiter
                except Exception:
                    pass
                return False

        return self._submit(
            _click_and_wait(),
            timeout=(timeout / 1000) + 5,
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


    def inspect_cart_candidates(
        self,
        item_id: str,
        model_id: str,
        product_name: str,
        requested_options: dict[str, str],
    ):
        """Inspect cart identity in one browser-side DOM pass.

        Returned checkbox_index values refer to the current
        input.stardust-checkbox__input order, allowing the caller to
        resolve the Playwright locator without repeated DOM calls.
        """

        payload = {
            "item_id": str(item_id),
            "model_id": str(model_id),
            "product_name": str(product_name),
            "requested_options": {
                str(key).strip().lower(): str(value).strip().lower()
                for key, value in requested_options.items()
            },
        }

        script = """
        (payload) => {
            const checkboxSelector = "input.stardust-checkbox__input";
            const checkboxes = Array.from(document.querySelectorAll(checkboxSelector));
            const identityAttributes = [
                "data-item-id",
                "data-model-id",
                "data-product-id",
                "data-sku-id",
                "data-id",
            ];

            const normalize = (value) =>
                String(value || "").replace(/\\s+/g, " ").trim();

            const candidates = [];

            checkboxes.forEach((checkbox, checkboxIndex) => {
                let current = checkbox;
                let identityValues = [];
                let identityText = "";
                let combinedText = "";
                let bestLevel = 0;

                for (let level = 1; level <= 8 && current; level += 1) {
                    current = current.parentElement;
                    if (!current) {
                        break;
                    }

                    const levelIdentityValues = identityAttributes
                        .map((name) => current.getAttribute(name))
                        .filter(Boolean)
                        .map(String);

                    const text = normalize(current.innerText || current.textContent || "");

                    // Shopee may expose item_id and model_id on different
                    // nested cart ancestors. Preserve identity evidence
                    // across the same checkbox's ancestor chain instead of
                    // replacing it with the last matching ancestor.
                    identityValues = identityValues.concat(levelIdentityValues);
                    identityText = identityValues.join(" ");
                    combinedText = normalize(
                        [combinedText, text].filter(Boolean).join(" ")
                    );

                    if (
                        levelIdentityValues.length > 0 ||
                        text.includes(payload.item_id) ||
                        text.includes(payload.model_id)
                    ) {
                        bestLevel = level;
                    }
                }

                const itemMatch =
                    identityText.includes(payload.item_id) ||
                    combinedText.includes(payload.item_id);
                const modelMatch =
                    identityText.includes(payload.model_id) ||
                    combinedText.includes(payload.model_id);

                candidates.push({
                    checkbox_index: checkboxIndex,
                    item_match: itemMatch,
                    model_match: modelMatch,
                    identity_values: [...new Set(identityValues)],
                    text: combinedText,
                    level: bestLevel,
                });
            });

            const exactIdentityCandidates = candidates.filter(
                (candidate) =>
                    candidate.item_match &&
                    candidate.model_match
            );

            // E7 fast path: when exactly one checkbox exposes both the frozen
            // item and model identity, no variation-text scan is necessary.
            if (exactIdentityCandidates.length === 1) {
                return {
                    checkbox_count: checkboxes.length,
                    identity_candidates: candidates,
                    exact_identity_candidates: exactIdentityCandidates,
                    variation_candidates: [],
                    resolution_path: "exact_identity_fast_path",
                };
            }

            const productName = normalize(payload.product_name).toLowerCase();
            const requestedValues = Object.values(payload.requested_options)
                .map((value) => normalize(value).toLowerCase())
                .filter(Boolean);
            const variationCandidates = [];

            // Inspect each checkbox independently. This prevents a large
            // page-level ancestor (recommendations/sidebar/cart root) from
            // making every checkbox look like the requested product.
            checkboxes.forEach((checkbox, checkboxIndex) => {
                let current = checkbox;

                for (let level = 1; level <= 8 && current; level += 1) {
                    current = current.parentElement;
                    if (!current) {
                        break;
                    }

                    const checkboxesInContainer = current.querySelectorAll(
                        checkboxSelector
                    );

                    // A product-level container should resolve to one cart
                    // checkbox. Page/cart-level containers containing many
                    // checkboxes are not valid variation candidates.
                    if (checkboxesInContainer.length !== 1) {
                        continue;
                    }

                    const candidateText = normalize(
                        current.innerText || current.textContent || ""
                    ).toLowerCase();

                    const productMatch =
                        !productName || candidateText.includes(productName);

                    if (!productMatch) {
                        continue;
                    }

                    const matchedOptions = requestedValues.filter(
                        (value) => candidateText.includes(value)
                    );

                    variationCandidates.push({
                        checkbox_index: checkboxIndex,
                        matched_options: matchedOptions,
                        option_count: requestedValues.length,
                        text: candidateText,
                        level,
                    });

                    // The first matching ancestor is the most local cart
                    // container for this checkbox.
                    break;
                }
            });

            return {
                checkbox_count: checkboxes.length,
                identity_candidates: candidates,
                exact_identity_candidates: exactIdentityCandidates,
                variation_candidates: variationCandidates,
                resolution_path: "identity_and_variation_scan",
            };
        }
        """
        return self._submit(
            self.session.page.evaluate(script, payload),
            timeout=10,
        )

    def scroll_to_bottom(
        self,
    ):

        return self._submit(
            self.session.page.evaluate(
                "() => window.scrollTo(0, document.body.scrollHeight)"
            ),
            timeout=10,
        )
